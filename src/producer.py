"""
Producer multi-senzor cu intervale independente per sursă.
Fiecare senzor rulează pe propriul thread cu propriul interval.
"""
import readBMX280
import readLegoDetector  # wrapper peste LegoDetector
import logging
import os
import time
import json
import threading

# Import nou în listă
import readMQ

import readMPU6050

import readCCS811

from confluent_kafka import Producer

import logging_config
import utils
from admin import Admin


# ── Intervale per senzor (secunde) ──────────────────────────
INTERVAL_BME280   = 30
INTERVAL_LEGO     = 3
# ────────────────────────────────────────────────────────────

# Intervale
INTERVAL_MQ9   = 10   # CO se poate schimba rapid
INTERVAL_MQ135 = 15   # calitate aer — mai lentă

INTERVAL_MPU6050 = 5  # mișcarea se schimbă rapid

INTERVAL_CCS811 = 10

class ProducerClass:
    def __init__(self, bootstrap_servers, topic):
        self.topic = topic
        self._lock = threading.Lock()  # confluent_kafka Producer NU e thread-safe
        self.producer = Producer({
            "bootstrap.servers": bootstrap_servers,
            "partitioner": "random",
            # Micro-batching: așteaptă max 100ms să acumuleze mesaje
            "linger.ms": 100,
            # Retry automat la erori tranzitorii
            "retries": 5,
            "retry.backoff.ms": 500,
        })

    def send(self, sensor_type: str, payload: dict):
        """Adaugă sensor_type și trimite mesajul thread-safe."""
        payload["sensor_type"] = sensor_type
        message = json.dumps(payload)

        with self._lock:
            try:
                self.producer.produce(
                    self.topic,
                    value=message.encode("utf-8"),
                    key=sensor_type.encode("utf-8"),  # key = tip senzor → același consumer
                    callback=self._delivery_report,
                )
                self.producer.poll(0)  # procesează callbacks fără blocare
            except Exception as e:
                logging.error(f"[{sensor_type}] Eroare send: {e}")

    @staticmethod
    def _delivery_report(err, msg):
        if err:
            logging.error(f"Delivery failed: {err}")
        else:
            logging.debug(f"Livrat → {msg.topic()} [partition {msg.partition()}]")

    def flush(self):
        with self._lock:
            self.producer.flush()


# ── Thread-uri independente per senzor ──────────────────────

def thread_ccs811(producer: ProducerClass, stop_event: threading.Event):
    logging.info(f"[CCS811] Thread pornit, interval={INTERVAL_CCS811}s")
    while not stop_event.is_set():
        data = readCCS811.readCCS811()
        if data:
            producer.send("ccs811", data)
        stop_event.wait(INTERVAL_CCS811)


def thread_mpu6050(producer: ProducerClass, stop_event: threading.Event):
    logging.info(f"[MPU-6050] Thread pornit, interval={INTERVAL_MPU6050}s")
    while not stop_event.is_set():
        data = readMPU6050.readMPU6050()
        if data:
            producer.send("mpu6050", data)
        stop_event.wait(INTERVAL_MPU6050)

# Thread MQ-9
def thread_mq9(producer: ProducerClass, stop_event: threading.Event):
    logging.info(f"[MQ-9] Thread pornit, interval={INTERVAL_MQ9}s")
    while not stop_event.is_set():
        data = readMQ.readMQ9()
        if data:
            producer.send("mq9", data)
        stop_event.wait(INTERVAL_MQ9)

# Thread MQ-135
def thread_mq135(producer: ProducerClass, stop_event: threading.Event):
    logging.info(f"[MQ-135] Thread pornit, interval={INTERVAL_MQ135}s")
    while not stop_event.is_set():
        data = readMQ.readMQ135()
        if data:
            producer.send("mq135", data)
        stop_event.wait(INTERVAL_MQ135)

def thread_bme280(producer: ProducerClass, stop_event: threading.Event):
    """Citește temperatura/umiditate/presiune la fiecare INTERVAL_BME280 secunde."""
    logging.info(f"[BME280] Thread pornit, interval={INTERVAL_BME280}s")
    while not stop_event.is_set():
        data = readBMX280.readSensorData()  # returnează dict sau None
        if data:
            producer.send("bme280", data)
        stop_event.wait(INTERVAL_BME280)  # wait() în loc de sleep() → oprire imediată


def thread_lego(producer: ProducerClass, stop_event: threading.Event):
    model_path = os.path.join(os.path.dirname(__file__), "Camera pi3", "models", "best.pt")
    detector = readLegoDetector.LegoDetector(model_path)
    logging.info(f"[LEGO] Thread pornit, interval={INTERVAL_LEGO}s")

    last_count = -1  # trimitem doar când se schimbă contorul

    try:
        while not stop_event.is_set():
            count = detector.get_count()

            if count != last_count:  # ← OPTIMIZARE: nu spam dacă nu s-a schimbat nimic
                producer.send("lego", {
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "lego_count": count,
                })
                last_count = count

            stop_event.wait(INTERVAL_LEGO)
    finally:
        detector.stop()


# ── Entry point ──────────────────────────────────────────────

if __name__ == "__main__":
    utils.load_env()
    logging_config.configure_logging()

    bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS")
    topic = os.environ.get("KAFKA_TOPIC_PRODUCER")

    admin = Admin(bootstrap_servers)
    admin.create_topic(topic)

    producer = ProducerClass(bootstrap_servers, topic)
    stop_event = threading.Event()

    threads = [
        threading.Thread(target=thread_bme280, args=(producer, stop_event), daemon=True, name="bme280"),
        threading.Thread(target=thread_lego,   args=(producer, stop_event), daemon=True, name="lego"),
        # threading.Thread(target=thread_pir, ...) ← adaugi ușor senzori noi
        threading.Thread(target=thread_mq9,    args=(producer, stop_event), daemon=True, name="mq9"),    # ← nou
        threading.Thread(target=thread_mq135,  args=(producer, stop_event), daemon=True, name="mq135"),  # ← nou
        threading.Thread(target=thread_mpu6050, args=(producer, stop_event), daemon=True, name="mpu6050"),
        threading.Thread(target=thread_ccs811, args=(producer, stop_event), daemon=True, name="ccs811"),
    ]

    for t in threads:
        t.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Oprire gracefully...")
        stop_event.set()

    for t in threads:
        t.join(timeout=5)

    producer.flush()
    logging.info("Producer oprit.")