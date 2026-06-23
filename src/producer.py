"""
Producer multi-senzor cu intervale independente per sursă.
"""
import readBMX280
import readMQ
import readMPU6050
import readCCS811
import logging
import os
import time
import json
import queue
import threading
import datetime

from confluent_kafka import Producer
from http_receiver import dht11_queue, start_http_receiver

import logging_config
import utils
from admin import Admin
from alert_manager import AlertManager
from consumer import ConsumerClass
from readPersonDetector import PersonDetector
from readLegoDetector import LegoDetector
from readMotionDetector import MotionDetector
# sus, după import-uri
from shared_camera import SharedCamera

# ── Inițializare globală ─────────────────────────────────────
command_queue = queue.Queue()
alert_manager = AlertManager()

# ── Intervale per senzor (secunde) ──────────────────────────
INTERVAL_BME280  = 30
INTERVAL_LEGO    = 3
INTERVAL_MQ9     = 10
INTERVAL_MQ135   = 15
INTERVAL_MPU6050 = 0.1
INTERVAL_CCS811  = 10
INTERVAL_DHT11_ESP = 30   # nu e folosit direct — ESP trimite când vrea
INTERVAL_CAMERA = 5 

# ── Producer Class ───────────────────────────────────────────
class ProducerClass:
    def __init__(self, bootstrap_servers, topic):
        self.topic = topic
        self._lock = threading.Lock()
        self.producer = Producer({
            "bootstrap.servers": bootstrap_servers,
            "partitioner": "random",
            "linger.ms": 0,       # ← în loc de 100
            "retries": 5,
            "retry.backoff.ms": 500,
        })

    def send(self, sensor_type: str, payload: dict):
        payload["sensor_type"] = sensor_type
        message = json.dumps(payload)
        with self._lock:
            try:
                self.producer.produce(
                    self.topic,
                    value=message.encode("utf-8"),
                    key=sensor_type.encode("utf-8"),
                    callback=self._delivery_report,
                )
                self.producer.poll(0)
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

# ── Thread-uri ───────────────────────────────────────────────

def thread_bme280(producer: ProducerClass, stop_event: threading.Event):
    logging.info(f"[BME280] Thread pornit, interval={INTERVAL_BME280}s")
    while not stop_event.is_set():
        data = readBMX280.readSensorData()
        if data:
            producer.send("bme280", data)
        stop_event.wait(INTERVAL_BME280)

def thread_lego(producer: ProducerClass, stop_event: threading.Event):
    model_path = os.path.join(os.path.dirname(__file__), "Camera pi3", "models", "best.pt")
    detector = LegoDetector(model_path)
    logging.info(f"[LEGO] Thread pornit, interval={INTERVAL_LEGO}s")
    last_occupied = None
    try:
        while not stop_event.is_set():
            occupied = detector.is_occupied()
            alert_manager._occupied = occupied   # ← lipsea această linie
            if occupied != last_occupied:
                producer.send("lego", {
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "lego_count": 1 if occupied else 0,
                })
                last_occupied = occupied
            stop_event.wait(INTERVAL_LEGO)
    finally:
        detector.stop()
def thread_mq_sensors(producer: ProducerClass, stop_event: threading.Event):
    logging.info("[MQ] Thread pornit")
    while not stop_event.is_set():
        v_mq9, v_mq135 = readMQ.readMQBoth()
        if v_mq9 is not None:
            co_ppm = max(0.0, round((v_mq9 / 3.3) * 1000, 2))
            producer.send("mq9", {
                "sensor_type": "mq9",
                "timestamp":   datetime.datetime.now().isoformat(),
                "voltage":     round(v_mq9, 4),
                "co_ppm":      co_ppm,
            })
        if v_mq135 is not None and v_mq135 > 0.01:
            air_ppm = max(0.0, round(400 + (v_mq135 / 3.3) * 600, 2))
            producer.send("mq135", {
                "sensor_type": "mq135",
                "timestamp":   datetime.datetime.now().isoformat(),
                "voltage":     round(v_mq135, 4),
                "air_quality_ppm": air_ppm,
            })
        stop_event.wait(10)

def thread_mpu6050(producer: ProducerClass, stop_event: threading.Event):
    logging.info("[MPU-6050] Thread pornit")
    
    FAST_INTERVAL = 0.15   # 20ms pentru detectare seism
    SEND_INTERVAL = 0.5    # 500ms pentru Kafka/dashboard
    last_send = 0

    while not stop_event.is_set():
        data = readMPU6050.readMPU6050()
        now = time.time()

        if data:
            # Detectare alertă la fiecare 20ms
            alert_manager.process_mpu6050(data)

            # Trimite în Kafka doar la fiecare 500ms
            if now - last_send >= SEND_INTERVAL:
                producer.send("mpu6050", data)
                producer.send("alert", {
                    "sensor_type": "alert",
                    "timestamp": datetime.datetime.now().isoformat(),
                    "state": alert_manager.get_state(),
                })
                last_send = now

        stop_event.wait(FAST_INTERVAL)

def thread_ccs811(producer: ProducerClass, stop_event: threading.Event):
    logging.info(f"[CCS811] Thread pornit, interval={INTERVAL_CCS811}s")
    while not stop_event.is_set():
        data = readCCS811.readCCS811()
        if data:
            producer.send("ccs811", data)
            alert_manager._last_tvoc = data.get("tvoc_ppb", 0)
            alert_manager.process_air_quality(0, 0, 0)
            producer.send("alert", {
                "sensor_type": "alert",
                "timestamp":   data["timestamp"],
                "state":       alert_manager.get_state(),
            })
        stop_event.wait(INTERVAL_CCS811)

def thread_motion_detector(producer: ProducerClass, stop_event: threading.Event):
    detector = MotionDetector(
        threshold_pixel=25,
        threshold_motion=500,
        resolution=(640, 480),
    )
    detector.start()
    logging.info(f"[Motion] Thread pornit, interval={INTERVAL_CAMERA}s")
    try:
        while not stop_event.is_set():
            data = detector.detect()
            if data["motion_detected"]:
                logging.info(f"[Motion] Mișcare! {data['motion_pixels']} pixeli")
                producer.send("motion", data)
            stop_event.wait(INTERVAL_CAMERA)
    finally:
        detector.stop()
      

def thread_dht11_esp(producer, stop_event):
    """
    Citește din queue-ul populat de http_receiver
    și trimite datele în Kafka.
    """
    import logging
    logging.info("[DHT11-ESP] Thread pornit, așteaptă date de la ESP8266")
    while not stop_event.is_set():
        try:
            data = dht11_queue.get(timeout=1)
            # Adaugă timestamp server-side dacă lipsește
            if "timestamp" not in data:
                data["timestamp"] = datetime.datetime.now().isoformat()
            producer.send("dht11_esp", data)
        except queue.Empty:
            continue
        except Exception as e:
            logging.error(f"[DHT11-ESP] Eroare: {e}")

def thread_commands(producer: ProducerClass, stop_event: threading.Event):
    logging.info("[Commands] Thread pornit")
    while not stop_event.is_set():
        try:
            command = command_queue.get(timeout=0.1)  # ← 0.1s în loc de 1s
            if command == "confirm_revenire":
                result = alert_manager.confirm_revenire()
                logging.info(f"[Commands] confirm_revenire → {result}")
            elif command == "force_reset":
                result = alert_manager.force_reset()
                logging.warning("[Commands] Force reset executat!")
            # ← trimite imediat starea nouă
            producer.send("alert", {
                "sensor_type": "alert",
                "timestamp":   datetime.datetime.now().isoformat(),
                "state":       alert_manager.get_state(),
            })
        except queue.Empty:
            continue

def thread_kafka_consumer(stop_event: threading.Event):
    bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS")
    topic    = os.environ.get("KAFKA_TOPIC_CONSUMER")
    group_id = os.environ.get("CONSUMER_GROUP_ID", "consumer-group-id-1")
    consumer = ConsumerClass(bootstrap_servers, topic, group_id, command_queue)
    logging.info("[Kafka Consumer] Thread pornit")
    consumer.consume_messages()

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

    start_http_receiver(port=5002)

    threads = [
        threading.Thread(target=thread_bme280,         args=(producer, stop_event), daemon=True, name="bme280"),
        threading.Thread(target=thread_mpu6050,         args=(producer, stop_event), daemon=True, name="mpu6050"),
        threading.Thread(target=thread_ccs811,          args=(producer, stop_event), daemon=True, name="ccs811"),
        threading.Thread(target=thread_kafka_consumer,  args=(stop_event,),          daemon=True, name="kafka_consumer"),
        threading.Thread(target=thread_dht11_esp,       args=(producer, stop_event),daemon=True,name="dht11_esp"),
        # threading.Thread(target=thread_person_detector,args=(producer, stop_event),  daemon=True,name="camera"),
        threading.Thread(target=thread_lego, args=(producer, stop_event), daemon=True, name="lego"),
        threading.Thread(target=thread_mq_sensors, args=(producer, stop_event), daemon=True, name="mq"),
        threading.Thread(target=thread_commands, args=(producer, stop_event), daemon=True, name="commands"),
        threading.Thread(target=thread_motion_detector, args=(producer, stop_event), daemon=True, name="motion"),
         threading.Thread(target=thread_lego,            args=(producer, stop_event, shared_cam), daemon=True, name="lego"),
    threading.Thread(target=thread_motion_detector, args=(producer, stop_event, shared_cam), daemon=True, name="motion"),
    ]

    for t in threads:
        t.start()

    def _startup_message():
        time.sleep(2)
        from actuators import lcd_write, deactivate_all
        lcd_write("Se initializeaza", "Va rugam asteptati")
        time.sleep(30)
        deactivate_all()

    threading.Thread(target=_startup_message, daemon=True).start()

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