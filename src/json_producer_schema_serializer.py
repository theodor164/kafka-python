"""The Producer code will Serialize the JSON message.

by getting the schema from the Schema Registry
CANNOT test - https://github.com/redpanda-data/redpanda/issues/14462
Redpanda does not support JSON Schema Registry
"""
import logging
import os

import logging_config
import utils
from admin import Admin
from producer import ProducerClass
from schema_registry_client import SchemaClient
from confluent_kafka.schema_registry.json_schema import JSONSerializer
from confluent_kafka.serialization import SerializationContext, MessageField
from confluent_kafka.schema_registry import SchemaRegistryClient


class User:
    def __init__(self, first_name, middle_name, last_name, age):
        self.first_name = first_name
        self.middle_name = middle_name
        self.last_name = last_name
        self.age = age


def user_to_dict(user):
    """Return a dictionary representation of a User instance  for
    serialization."""
    return dict(
        first_name=user.first_name,
        middle_name=user.middle_name,
        last_name=user.last_name,
        age=user.age,
    )


class JSONProducer(ProducerClass):
    def __init__(self, bootstrap_server, topic, schema_registry_url, json_schema):
        super().__init__(bootstrap_server, topic)
        self.schema_registry_client = SchemaRegistryClient({"url": schema_registry_url})
        self.json_serializer = JSONSerializer(
            schema_str=json_schema,
            schema_registry_client=self.schema_registry_client,
        )

    def send_message(self, message_dict):
        try:
            # Convert message to JSON string and serialize
            # message_json = self.value_serializer(message_dict)
            serialized_message = self.json_serializer(
                message_dict,
                SerializationContext(self.topic, MessageField.VALUE),
            )
            self.producer.produce(self.topic, serialized_message)
            logging.info(f"Message Sent: {serialized_message}")
        except Exception as e:
            logging.error(f"Error sending message: {e}")


if __name__ == "__main__":
    utils.load_env()
    logging_config.configure_logging()

    bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS")
    topic = os.environ.get("KAFKA_TOPIC_PRODUCER")
    schema_registry_url = os.environ.get("SCHEMA_REGISTRY_URL")

    """
    Reading using read() function, because SchemaClient register_schema
    function required schema in form of string
    """
    with open("./schemas/schema.json") as json_schema_file:
        json_schema = json_schema_file.read()

    admin = Admin(bootstrap_servers)
    admin.create_topic(topic)

    # Can not test in REDPANDA, Because REDPANDA version 23 does not support JSON
    # https://github.com/redpanda-data/redpanda/issues/14462
    # It's now supported in 24.2
    # https://github.com/redpanda-data/redpanda/issues/6220#issuecomment-2401662572
    schema_client = SchemaClient(schema_registry_url, topic, json_schema, "JSON")
    schema_client.register_schema()

    producer = JSONProducer(bootstrap_servers, topic, schema_registry_url, json_schema)

    try:
        while True:
            first_name = input("Enter first name: ")
            middle_name = input("Enter middle name: ")
            last_name = input("Enter last name: ")
            age = int(input("Enter age: "))
            user = User(
                first_name=first_name,
                middle_name=middle_name,
                last_name=last_name,
                age=age,
            )
            producer.send_message(user_to_dict(user))
    except KeyboardInterrupt:
        pass

    producer.commit()
