"""
mongo_client.py
===============
Extraction layer for wearable telemetry (MongoDB).

Demonstrates the responsibility:
    "Extract data from databases (e.g., MongoDB)"
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import List, Optional

import pandas as pd

try:
    from pymongo import MongoClient, ASCENDING
except ImportError:                          # pragma: no cover
    MongoClient = None
    ASCENDING = 1

logger = logging.getLogger(__name__)


class MongoTelemetryClient:
    """Read-only client for the wellness_telemetry MongoDB."""

    def __init__(self, uri: str, database: str) -> None:
        if MongoClient is None:
            raise RuntimeError("pymongo not installed in this environment.")
        self._client = MongoClient(uri, serverSelectionTimeoutMS=5_000)
        self._db = self._client[database]

    @classmethod
    def from_env(cls) -> "MongoTelemetryClient":
        uri = os.getenv(
            "MONGO_URI",
            "mongodb://wellness_admin:change_me_in_prod@localhost:27017/",
        )
        db = os.getenv("MONGO_DATABASE", "wellness_telemetry")
        return cls(uri=uri, database=db)

    # ------------------------------------------------------------------ #
    # Domain queries
    # ------------------------------------------------------------------ #
    def fetch_daily_activity(
        self,
        user_id: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """Daily steps + distance + calories."""
        q: dict = {}
        if user_id:
            q["user_id"] = user_id
        if since:
            q["date"] = {"$gte": since}
        docs = list(self._db.daily_activity.find(q, {"_id": 0}))
        logger.info("Fetched %d daily_activity docs", len(docs))
        return pd.DataFrame(docs)

    def fetch_sleep_records(self, days: int = 30) -> pd.DataFrame:
        """Recent sleep stages aggregated by night."""
        since = datetime.utcnow() - timedelta(days=days)
        docs = list(
            self._db.sleep_records.find(
                {"sleep_start": {"$gte": since}}, {"_id": 0}
            )
        )
        logger.info("Fetched %d sleep_records docs (last %d days)", len(docs), days)
        return pd.DataFrame(docs)

    def fetch_heart_rate(self, user_id: str, day: datetime) -> pd.DataFrame:
        """Minute-resolution HR for a single user/day."""
        start = datetime(day.year, day.month, day.day)
        end = start + timedelta(days=1)
        cur = self._db.heart_rate.find(
            {"user_id": user_id, "timestamp": {"$gte": start, "$lt": end}},
            {"_id": 0},
        ).sort("timestamp", ASCENDING)
        return pd.DataFrame(list(cur))

    # ------------------------------------------------------------------ #
    # Aggregation pipelines — show off real Mongo skill
    # ------------------------------------------------------------------ #
    def avg_daily_steps_by_user(self) -> pd.DataFrame:
        pipeline: List[dict] = [
            {"$group": {
                "_id": "$user_id",
                "avg_steps":  {"$avg": "$steps"},
                "days_tracked": {"$sum": 1},
            }},
            {"$project": {
                "user_id": "$_id",
                "avg_steps": {"$round": ["$avg_steps", 0]},
                "days_tracked": 1,
                "_id": 0,
            }},
            {"$sort": {"avg_steps": -1}},
        ]
        return pd.DataFrame(list(self._db.daily_activity.aggregate(pipeline)))

    def detect_duplicate_sleep_records(self) -> pd.DataFrame:
        """Engineering bug detector — flags duplicate nightly records."""
        pipeline = [
            {"$group": {
                "_id": {"user_id": "$user_id", "sleep_start": "$sleep_start"},
                "count": {"$sum": 1},
                "ids":   {"$push": "$record_id"},
            }},
            {"$match": {"count": {"$gt": 1}}},
        ]
        return pd.DataFrame(list(self._db.sleep_records.aggregate(pipeline)))

    def close(self) -> None:
        self._client.close()
