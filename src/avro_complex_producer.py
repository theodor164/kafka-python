import logging
import os
from uuid import uuid4

from confluent_kafka.schema_registry.avro import AvroSerializer
from confluent_kafka.serialization import (
    MessageField,
    SerializationContext,
    StringSerializer,
)

import logging_config
import utils
from admin import Admin
from producer import ProducerClass
from schema_registry_client import SchemaClient
from confluent_kafka import KafkaException
from datetime import datetime


def build_message(user_id, name, age, email, street, city, postcode, country, sports):
    return {
        "userId": user_id,
        "createdAt": int(datetime.now().timestamp() * 1000),  # timestamp-millis
        "actionType": "CREATE",
        "basicInfo": {"full_name": name, "age": age, "email": email},
        "address": {
            "street": street,
            "city": city,
            "postcode": postcode,
            "country": country,
        },
        "interests": [
            {"category": "SPORTS", "description": sport.strip()}
            for sport in sports.split(",")
        ],
        "preferences": {
            "newsletterSubscribed": True,
            "preferredLanguage": "en",
            "darkMode": False,
        },
    }


def delivery_report(err, msg):
    if err is not None:
        logging.error(f"Delivery failed for record for {msg.key()} with error {err}")
        return
    logging.info(
        f"Successfully produced record: key - {msg.key()}, topic - {msg.topic}, partition - {msg.partition()}, offset - {msg.offset()}"
    )


class AvroProducer(ProducerClass):
    def __init__(
        self,
        bootstrap_server,
        topic,
        schema_registry_client,
        schema_str,
        compression_type=None,
        message_size=None,
        batch_size=None,
        waiting_time=None,
    ):
        super().__init__(
            bootstrap_server,
            topic,
            compression_type,
            message_size,
            batch_size,
            waiting_time,
        )
        self.schema_registry_client = schema_registry_client
        self.schema_str = schema_str
        self.avro_serializer = AvroSerializer(schema_registry_client, schema_str)
        self.string_serializer = StringSerializer("utf-8")

    def send_message(self, key=None, value=None):
        try:
            if value:
                byte_value = self.avro_serializer(
                    value, SerializationContext(topic, MessageField.VALUE)
                )
            else:
                byte_value = None
            self.producer.produce(
                topic=self.topic,
                key=self.string_serializer(str(key)),
                value=byte_value,
                headers={"correlation_id": str(uuid4())},
                on_delivery=delivery_report,
            )
            logging.info("Message Successfully Produce by the Producer")
        except KafkaException as e:
            kafka_error = e.args[0]
            if kafka_error.MSG_SIZE_TOO_LARGE:
                logging.error(
                    f"{e} , Current Message size is {len(value) / (1024 * 1024)} MB"
                )
        except Exception as e:
            logging.error(f"Error while sending message: {e}")


if __name__ == "__main__":
    utils.load_env()
    logging_config.configure_logging()

    bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS")
    topic = os.environ.get("KAFKA_TOPIC")
    schema_registry_url = os.environ.get("SCHEMA_REGISTRY_URL")
    schema_type = "AVRO"

    # Create Topic
    admin = Admin(bootstrap_servers)
    admin.create_topic(topic, 2)  # second parameter is for number of partitions

    # Register the Schema
    with open("./schemas/complex_schema.avsc") as avro_schema_file:
        avro_schema = avro_schema_file.read()

    schema_client = SchemaClient(schema_registry_url, topic, avro_schema, schema_type)
    schema_client.set_compatibility("BACKWARD")
    schema_client.register_schema()

    # fetch schema_str from Schema Registry
    schema_str = schema_client.get_schema_str()
    # Produce messages
    producer = AvroProducer(
        bootstrap_servers,
        topic,
        schema_client.schema_registry_client,
        schema_str,
        compression_type="snappy",
        message_size=3 * 1024 * 1024,
        batch_size=10_00_00,  # in bytes, 1 MB
        waiting_time=10_000,  # in milliseconds, 10 seconds
    )

    try:
        while True:
            action = (
                input(
                    "Enter 'insert' to add  a new record or 'delete' to publish tombstone: "
                )
                .strip()
                .lower()
            )
            if action == "insert":
                user_id = int(input("Enter User ID: "))
                name = input("Enter Full Name: ").strip()
                age = int(input("Enter Age: "))
                email = input("Enter Email: ").strip()
                street = input("Enter Street Address: ").strip()
                city = input("Enter City: ").strip()
                postcode = input("Enter Postcode: ").strip()
                country = input("Enter Country: ").strip()
                sports = input("Enter Sports Interests (comma-separated): ").strip()

                msg = build_message(
                    user_id, name, age, email, street, city, postcode, country, sports
                )
                producer.send_message(key=user_id, value=msg)
            elif action == "delete":
                message_id = int(input("Enter User Id to delete: "))
                producer.send_message(key=user_id)
    except KeyboardInterrupt:
        pass

    producer.commit()
