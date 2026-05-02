"""
data_ingestion/sources/stream_connector.py
Consumes events from a Kafka topic and yields RawDocuments.
"""
import json
import uuid
from typing import Iterator

from kafka import KafkaConsumer

from data_ingestion.sources.base import BaseSourceConnector, RawDocument


class KafkaStreamConnector(BaseSourceConnector):
    def __init__(
        self,
        topic: str,
        bootstrap_servers: str,
        group_id: str = "llmops-ingestion",
        text_field: str = "text",
        timeout_ms: int = 10_000,
    ):
        self.topic = topic
        self.bootstrap_servers = bootstrap_servers
        self.group_id = group_id
        self.text_field = text_field
        self.timeout_ms = timeout_ms

    def validate_connection(self) -> bool:
        try:
            consumer = KafkaConsumer(bootstrap_servers=self.bootstrap_servers)
            consumer.topics()
            consumer.close()
            return True
        except Exception:
            return False

    def fetch(self, max_messages: int = 1000, **kwargs) -> Iterator[RawDocument]:
        consumer = KafkaConsumer(
            self.topic,
            bootstrap_servers=self.bootstrap_servers,
            group_id=self.group_id,
            auto_offset_reset="earliest",
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            consumer_timeout_ms=self.timeout_ms,
        )
        count = 0
        for message in consumer:
            if count >= max_messages:
                break
            payload = message.value
            content = payload.get(self.text_field, json.dumps(payload))
            yield RawDocument(
                id=payload.get("id", str(uuid.uuid4())),
                content=content,
                source=f"kafka://{self.topic}",
                source_type="stream",
                metadata={"partition": message.partition, "offset": message.offset},
            )
            count += 1
        consumer.close()
