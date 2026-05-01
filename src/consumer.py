"""
Consumer Kafka pe Pi — primește comenzi de la Angular
și le transmite către producer prin queue.
"""
import logging
import os
from confluent_kafka import Consumer
import logging_config
import utils

class ConsumerClass:
    def __init__(self, bootstrap_server, topic, group_id, command_queue=None):
        self.bootstrap_server = bootstrap_server
        self.topic = topic
        self.group_id = group_id
        self.command_queue = command_queue  # ← queue shared cu producer
        self.consumer = Consumer({
            "bootstrap.servers": bootstrap_server,
            "group.id": self.group_id,
            "auto.offset.reset": "latest",
        })

    def consume_messages(self):
        self.consumer.subscribe([self.topic])
        logging.info(f"[Consumer Pi] Abonat la topic: {self.topic}")

        try:
            while True:
                msg = self.consumer.poll(1.0)
                if msg is None:
                    continue
                if msg.error():
                    logging.error(f"[Consumer Pi] Eroare: {msg.error()}")
                    continue

                decoded = msg.value().decode("utf-8")
                logging.info(f"[Consumer Pi] Comandă primită: {decoded}")

                if decoded == "confirm_revenire" and self.command_queue:
                    self.command_queue.put("confirm_revenire")
                    logging.info("[Consumer Pi] Comandă pusă în queue ✅")

        except KeyboardInterrupt:
            pass
        finally:
            self.consumer.close()