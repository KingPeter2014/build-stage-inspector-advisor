"""
data_ingestion/sources/sql_connector.py
Pulls records from any SQLAlchemy-compatible database.
"""
import hashlib
from typing import Iterator

import pandas as pd
from sqlalchemy import create_engine, text

from data_ingestion.sources.base import BaseSourceConnector, RawDocument


class SQLConnector(BaseSourceConnector):
    def __init__(self, dsn: str, query: str, text_columns: list[str], id_column: str | None = None):
        self.dsn = dsn
        self.query = query
        self.text_columns = text_columns
        self.id_column = id_column
        self._engine = create_engine(dsn)

    def validate_connection(self) -> bool:
        try:
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    def fetch(self, **kwargs) -> Iterator[RawDocument]:
        df = pd.read_sql(self.query, self._engine)
        for _, row in df.iterrows():
            content = " ".join(str(row[col]) for col in self.text_columns if col in row)
            doc_id = str(row[self.id_column]) if self.id_column else hashlib.md5(content.encode()).hexdigest()
            yield RawDocument(
                id=doc_id,
                content=content,
                source=self.dsn,
                source_type="structured",
                metadata={col: row[col] for col in row.index if col not in self.text_columns},
            )
