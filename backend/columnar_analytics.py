"""
Columnar Analytics Engine for MIND-FLOW Phase 3 Enterprise Scalability Extensions.

Provides an asynchronous batching columnar store using DuckDB alongside SQLite WAL.
High-frequency active window logs append in background batches to prevent locking main DB threads.
Analytical queries execute against DuckDB columnar storage with non-blocking SQLite failover.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
"""

import os
import sys
import time
import queue
import threading
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

import duckdb

logger = logging.getLogger("columnar_analytics")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - [ColumnarAnalytics] - %(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class ColumnarAnalyticsEngine:
    """
    Asynchronous Columnar Analytics Engine powered by DuckDB with SQLite failover.
    """
    def __init__(
        self,
        db_path: Optional[str] = None,
        sqlite_db: Optional[Any] = None,
        batch_size: int = 100,
        flush_interval: float = 2.0
    ):
        if db_path is None:
            db_path = os.getenv("MINDFLOW_DUCKDB_FILE")
            if not db_path:
                from backend.database import DEFAULT_DATA_DIR
                db_path = os.path.join(DEFAULT_DATA_DIR, "mind_flow_analytics.duckdb")

        self.db_path = db_path
        self.sqlite_db = sqlite_db
        self.batch_size = batch_size
        self.flush_interval = flush_interval

        self.is_memory = (self.db_path == ":memory:")
        self._duck_conn = None
        self._lock = threading.RLock()
        self._write_lock = threading.Lock()
        self._shutdown_event = threading.Event()

        self._batch_queue: queue.Queue = queue.Queue(maxsize=10000)

        # Initialize DuckDB schema
        self._init_duckdb()

        # Start daemon background batch writer thread
        self._worker_thread = threading.Thread(
            target=self._batch_worker,
            daemon=True,
            name="DuckDBBatchWriter"
        )
        self._worker_thread.start()

    def _get_connection(self, read_only: bool = False):
        """
        Retrieves or creates a DuckDB connection.
        Connections are shared per instance under a reentrant lock to prevent file lock contention.
        """
        with self._lock:
            if self._duck_conn is None:
                try:
                    self._duck_conn = duckdb.connect(self.db_path)
                except Exception as e:
                    logger.warning(f"[DUCKDB_LOCK_FAILOVER] Could not open {self.db_path} (falling back to in-memory): {e}")
                    self.db_path = ":memory:"
                    self.is_memory = True
                    self._duck_conn = duckdb.connect(":memory:")
            return self._duck_conn

    def _init_duckdb(self):
        """Creates the active_window_logs columnar table in DuckDB."""
        try:
            with self._lock:
                conn = self._get_connection(read_only=False)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS active_window_logs (
                        timestamp DOUBLE,
                        app_name VARCHAR,
                        title VARCHAR,
                        category VARCHAR,
                        duration DOUBLE
                    )
                """)
        except Exception as e:
            logger.warning(f"[DUCKDB_INIT_WARN] Could not initialize DuckDB at {self.db_path}: {e}")

    def append_window_log(
        self,
        timestamp: float,
        app_name: str,
        title: str,
        category: str,
        duration: float
    ) -> None:
        """
        Asynchronously buffers an active window log tick to the batch queue (non-blocking).
        """
        if not app_name or app_name == "None":
            app_name = "Unknown"
        if not title:
            title = "None"
        if not category:
            category = "neutral"
        if duration <= 0:
            duration = 1.0

        item = (float(timestamp), str(app_name), str(title), str(category).lower(), float(duration))
        try:
            self._batch_queue.put_nowait(item)
        except queue.Full:
            logger.warning("[DUCKDB_QUEUE_FULL] Active window log queue max capacity reached (10000). Dropping record.")

    def _batch_worker(self):
        """Background thread worker to flush queued logs to DuckDB in batches."""
        last_flush_time = time.time()
        batch: List[Tuple[float, str, str, str, float]] = []

        while not self._shutdown_event.is_set() or not self._batch_queue.empty():
            try:
                try:
                    item = self._batch_queue.get(timeout=0.5)
                    if item is not None:
                        batch.append(item)
                except queue.Empty:
                    pass

                now = time.time()
                should_flush = len(batch) >= self.batch_size or (batch and (now - last_flush_time >= self.flush_interval))

                if should_flush:
                    if self._flush_batch(batch):
                        batch = []
                        last_flush_time = time.time()
                    else:
                        # Cap retried batch size to prevent unbounded memory growth if DuckDB is permanently unavailable
                        max_cap = self.batch_size * 5
                        if len(batch) > max_cap:
                            dropped = batch[:-max_cap]
                            dropped_count = len(dropped)
                            logger.warning(
                                f"[DUCKDB_OVERFLOW] Truncating batch from {len(batch)} to {max_cap} "
                                f"({dropped_count} records routed to SQLite fallback due to persistent DuckDB write failures)"
                            )
                            self._fallback_to_sqlite(dropped)
                            batch = batch[-max_cap:]
                        time.sleep(0.5)
            except Exception as e:
                logger.exception(f"[DUCKDB_WORKER_ERROR] Exception in batch worker: {e}")

        if batch:
            self._flush_batch(batch)

    def _fallback_to_sqlite(self, records: List[Tuple[float, str, str, str, float]]):
        """Fallback writer: persist dropped batch records to SQLite app_usage."""
        if not self.sqlite_db or not records:
            return
        try:
            for ts, app_name, title, category, duration in records:
                self.sqlite_db.log_app_usage(app_name, title, duration, category=category)
        except Exception as e:
            logger.debug(f"[FALLBACK_SQLITE_ERROR] Failed routing to SQLite: {e}")

    def _flush_batch(self, batch: List[Tuple[float, str, str, str, float]]) -> bool:
        """Executes a vectorized batch insert into DuckDB. Returns True on success, False on failure."""
        if not batch:
            return True

        conn = None
        try:
            with self._write_lock:
                conn = self._get_connection(read_only=False)
                conn.executemany(
                    "INSERT INTO active_window_logs VALUES (?, ?, ?, ?, ?)",
                    batch
                )
        except Exception as e:
            logger.debug(f"[DUCKDB_FLUSH_ERROR] Failed inserting batch of {len(batch)} items to DuckDB: {e}")
            self._fallback_to_sqlite(batch)
            return True

    def flush(self, timeout: float = 5.0):
        """Flushes all currently buffered queue items synchronously."""
        start = time.time()
        batch = []
        while not self._batch_queue.empty() and (time.time() - start < timeout):
            try:
                item = self._batch_queue.get_nowait()
                batch.append(item)
            except queue.Empty:
                break
        if batch:
            self._flush_batch(batch)

    def close(self):
        """Shuts down the engine and flushes pending writes."""
        self._shutdown_event.set()
        self.flush()
        if hasattr(self, "_worker_thread") and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)
        if self._duck_conn is not None:
            try:
                self._duck_conn.close()
            except Exception:
                pass
            self._duck_conn = None

    # -------------------------------------------------------------------------
    # High-Performance Analytical Queries with Non-Blocking SQLite Failover
    # -------------------------------------------------------------------------

    def get_daily_productivity_trends(self, days: int = 7) -> List[Dict[str, Any]]:
        """
        Calculates daily productivity trends for the past `days` days.
        Returns list of daily dicts containing date, work_seconds, rest_seconds,
        neutral_seconds, total_seconds, and productivity_score.
        Transparently falls back to SQLite covering indexes if DuckDB errors occur.
        """
        try:
            return self._get_daily_productivity_trends_duckdb(days)
        except Exception as e:
            logger.warning(f"[DUCKDB_FAILOVER] get_daily_productivity_trends falling back to SQLite: {e}")
            return self._get_daily_productivity_trends_sqlite(days)

    def _get_daily_productivity_trends_duckdb(self, days: int = 7) -> List[Dict[str, Any]]:
        self.flush()
        now_ts = time.time()
        cutoff_ts = now_ts - (days * 86400)
        conn = self._get_connection(read_only=True if not self.is_memory else False)

        query = """
            SELECT 
                strftime(epoch_ms(CAST(timestamp * 1000 AS BIGINT)), '%Y-%m-%d') as log_date,
                category,
                SUM(duration) as total_duration
            FROM active_window_logs
            WHERE timestamp >= ?
            GROUP BY log_date, category
            ORDER BY log_date ASC
        """
        rows = conn.execute(query, [cutoff_ts]).fetchall()

        daily_data: Dict[str, Dict[str, float]] = {}
        today = datetime.now().date()
        for i in range(days - 1, -1, -1):
            d_str = (today - timedelta(days=i)).isoformat()
            daily_data[d_str] = {"work": 0.0, "rest": 0.0, "recharge": 0.0, "neutral": 0.0}

        for log_date, cat, dur in rows:
            if not log_date:
                continue
            if log_date not in daily_data:
                daily_data[log_date] = {"work": 0.0, "rest": 0.0, "recharge": 0.0, "neutral": 0.0}
            cat_lower = str(cat).lower() if cat else "neutral"
            if cat_lower in daily_data[log_date]:
                daily_data[log_date][cat_lower] += float(dur or 0.0)
            else:
                daily_data[log_date][cat_lower] = float(dur or 0.0)

        result = []
        for d_str in sorted(daily_data.keys()):
            d_info = daily_data[d_str]
            work_sec = d_info.get("work", 0.0)
            rest_sec = d_info.get("rest", 0.0) + d_info.get("recharge", 0.0)
            neutral_sec = d_info.get("neutral", 0.0)
            total_sec = work_sec + rest_sec + neutral_sec
            score = round((work_sec / total_sec * 100.0), 1) if total_sec > 0 else 0.0
            result.append({
                "date": d_str,
                "work_seconds": round(work_sec, 2),
                "rest_seconds": round(rest_sec, 2),
                "neutral_seconds": round(neutral_sec, 2),
                "total_seconds": round(total_sec, 2),
                "productivity_score": score
            })
        return result

    def _get_daily_productivity_trends_sqlite(self, days: int = 7) -> List[Dict[str, Any]]:
        """Fallback query using SQLite covering index idx_app_usage_analytics."""
        if not self.sqlite_db:
            today = datetime.now().date()
            return [
                {
                    "date": (today - timedelta(days=i)).isoformat(),
                    "work_seconds": 0.0,
                    "rest_seconds": 0.0,
                    "neutral_seconds": 0.0,
                    "total_seconds": 0.0,
                    "productivity_score": 0.0
                }
                for i in range(days - 1, -1, -1)
            ]

        self.sqlite_db.flush_app_usage()
        today = datetime.now().date()
        cutoff_date = (today - timedelta(days=days - 1)).isoformat()

        settings = self.sqlite_db.get_settings()
        work_kw = [k.lower() for k in settings.get("work_keywords", [])]
        recharge_kw = [k.lower() for k in settings.get("recharge_keywords", [])]

        daily_data: Dict[str, Dict[str, float]] = {}
        for i in range(days - 1, -1, -1):
            d_str = (today - timedelta(days=i)).isoformat()
            daily_data[d_str] = {"work": 0.0, "rest": 0.0, "neutral": 0.0}

        with self.sqlite_db.connection() as conn:
            rows = conn.execute("""
                SELECT date, process, title, duration
                FROM app_usage
                WHERE date >= ?
            """, (cutoff_date,)).fetchall()

            from backend.database import matches_any_keyword
            for row in rows:
                d_str = row["date"]
                proc = (row["process"] or "").lower()
                title = (row["title"] or "").lower()
                dur = float(row["duration"] or 0.0)

                if d_str not in daily_data:
                    daily_data[d_str] = {"work": 0.0, "rest": 0.0, "neutral": 0.0}

                if matches_any_keyword(work_kw, proc) or matches_any_keyword(work_kw, title):
                    daily_data[d_str]["work"] += dur
                elif matches_any_keyword(recharge_kw, proc) or matches_any_keyword(recharge_kw, title):
                    daily_data[d_str]["rest"] += dur
                else:
                    daily_data[d_str]["neutral"] += dur

        result = []
        for d_str in sorted(daily_data.keys()):
            d_info = daily_data[d_str]
            work_sec = d_info["work"]
            rest_sec = d_info["rest"]
            neutral_sec = d_info["neutral"]
            total_sec = work_sec + rest_sec + neutral_sec
            score = round((work_sec / total_sec * 100.0), 1) if total_sec > 0 else 0.0
            result.append({
                "date": d_str,
                "work_seconds": round(work_sec, 2),
                "rest_seconds": round(rest_sec, 2),
                "neutral_seconds": round(neutral_sec, 2),
                "total_seconds": round(total_sec, 2),
                "productivity_score": score
            })
        return result

    def get_category_breakdown(self, start_ts: float, end_ts: float) -> Dict[str, float]:
        """
        Calculates category breakdown between start_ts and end_ts.
        Transparently falls back to SQLite covering indexes if DuckDB errors occur.
        """
        try:
            return self._get_category_breakdown_duckdb(start_ts, end_ts)
        except Exception as e:
            logger.warning(f"[DUCKDB_FAILOVER] get_category_breakdown falling back to SQLite: {e}")
            return self._get_category_breakdown_sqlite(start_ts, end_ts)

    def _get_category_breakdown_duckdb(self, start_ts: float, end_ts: float) -> Dict[str, float]:
        self.flush()
        conn = self._get_connection(read_only=True if not self.is_memory else False)
        rows = conn.execute("""
            SELECT category, SUM(duration) as total_dur
            FROM active_window_logs
            WHERE timestamp >= ? AND timestamp <= ?
            GROUP BY category
        """, [start_ts, end_ts]).fetchall()

        breakdown = {"work": 0.0, "rest": 0.0, "recharge": 0.0, "neutral": 0.0}
        for cat, dur in rows:
            c = (cat or "neutral").lower()
            breakdown[c] = round(float(dur or 0.0), 2)
        return breakdown

    def _get_category_breakdown_sqlite(self, start_ts: float, end_ts: float) -> Dict[str, float]:
        breakdown = {"work": 0.0, "rest": 0.0, "recharge": 0.0, "neutral": 0.0}
        if not self.sqlite_db:
            return breakdown

        start_date = datetime.fromtimestamp(start_ts).date().isoformat()
        end_date = datetime.fromtimestamp(end_ts).date().isoformat()

        self.sqlite_db.flush_app_usage()
        settings = self.sqlite_db.get_settings()
        work_kw = [k.lower() for k in settings.get("work_keywords", [])]
        recharge_kw = [k.lower() for k in settings.get("recharge_keywords", [])]

        with self.sqlite_db.connection() as conn:
            rows = conn.execute("""
                SELECT process, title, duration
                FROM app_usage
                WHERE date >= ? AND date <= ?
            """, (start_date, end_date)).fetchall()

            from backend.database import matches_any_keyword
            for row in rows:
                proc = (row["process"] or "").lower()
                title = (row["title"] or "").lower()
                dur = float(row["duration"] or 0.0)
                if matches_any_keyword(work_kw, proc) or matches_any_keyword(work_kw, title):
                    breakdown["work"] += dur
                elif matches_any_keyword(recharge_kw, proc) or matches_any_keyword(recharge_kw, title):
                    breakdown["recharge"] += dur
                else:
                    breakdown["neutral"] += dur

        return {k: round(v, 2) for k, v in breakdown.items()}

    def get_fatigue_duration_analytics(self, days: int = 30) -> Dict[str, Any]:
        """
        Calculates fatigue & continuous session analytics over the past `days` days.
        Transparently falls back to SQLite covering indexes if DuckDB errors occur.
        """
        try:
            return self._get_fatigue_duration_analytics_duckdb(days)
        except Exception as e:
            logger.warning(f"[DUCKDB_FAILOVER] get_fatigue_duration_analytics falling back to SQLite: {e}")
            return self._get_fatigue_duration_analytics_sqlite(days)

    def _get_fatigue_duration_analytics_duckdb(self, days: int = 30) -> Dict[str, Any]:
        self.flush()
        now_ts = time.time()
        cutoff_ts = now_ts - (days * 86400)
        conn = self._get_connection(read_only=True if not self.is_memory else False)

        totals_row = conn.execute("""
            SELECT 
                SUM(CASE WHEN lower(category) = 'work' THEN duration ELSE 0 END) as total_work,
                SUM(CASE WHEN lower(category) IN ('rest', 'recharge') THEN duration ELSE 0 END) as total_rest,
                COUNT(DISTINCT strftime(epoch_ms(CAST(timestamp * 1000 AS BIGINT)), '%Y-%m-%d')) as active_days
            FROM active_window_logs
            WHERE timestamp >= ?
        """, [cutoff_ts]).fetchone()

        total_work = float(totals_row[0] or 0.0)
        total_rest = float(totals_row[1] or 0.0)
        active_days = max(1, int(totals_row[2] or 1))

        hourly_rows = conn.execute("""
            SELECT 
                CAST(strftime(epoch_ms(CAST(timestamp * 1000 AS BIGINT)), '%H') AS INT) as hr,
                SUM(CASE WHEN lower(category) = 'work' THEN duration ELSE 0 END) as work_dur
            FROM active_window_logs
            WHERE timestamp >= ?
            GROUP BY hr
        """, [cutoff_ts]).fetchall()

        hourly_distribution = [0.0] * 24
        for hr, dur in hourly_rows:
            if hr is not None and 0 <= hr < 24:
                hourly_distribution[hr] = round(float(dur or 0.0), 2)

        logs = conn.execute("""
            SELECT timestamp, duration, category
            FROM active_window_logs
            WHERE timestamp >= ?
            ORDER BY timestamp ASC
        """, [cutoff_ts]).fetchall()

        current_work_block = 0.0
        max_work_block = 0.0
        work_blocks = []

        for ts, dur, cat in logs:
            c = str(cat or "").lower()
            d = float(dur or 0.0)
            if c == "work":
                current_work_block += d
                if current_work_block > max_work_block:
                    max_work_block = current_work_block
            else:
                if current_work_block > 0:
                    work_blocks.append(current_work_block)
                    current_work_block = 0.0
        if current_work_block > 0:
            work_blocks.append(current_work_block)

        fatigue_over_threshold = sum(1 for b in work_blocks if b >= 2700.0)
        work_rest_ratio = (total_work / (total_rest + 1.0))
        fatigue_score = min(100.0, round(fatigue_over_threshold * 15.0 + work_rest_ratio * 10.0, 1))

        return {
            "total_work_seconds": round(total_work, 2),
            "total_rest_seconds": round(total_rest, 2),
            "avg_daily_work_seconds": round(total_work / active_days, 2),
            "longest_continuous_work_seconds": round(max_work_block, 2),
            "fatigue_risk_score": fatigue_score,
            "hourly_distribution": hourly_distribution,
            "analysis_period_days": days
        }

    def _get_fatigue_duration_analytics_sqlite(self, days: int = 30) -> Dict[str, Any]:
        result = {
            "total_work_seconds": 0.0,
            "total_rest_seconds": 0.0,
            "avg_daily_work_seconds": 0.0,
            "longest_continuous_work_seconds": 0.0,
            "fatigue_risk_score": 0.0,
            "hourly_distribution": [0.0] * 24,
            "analysis_period_days": days
        }
        if not self.sqlite_db:
            return result

        today = datetime.now().date()
        cutoff_date = (today - timedelta(days=days - 1)).isoformat()

        with self.sqlite_db.connection() as conn:
            sess_rows = conn.execute("""
                SELECT mode, duration, start
                FROM sessions
                WHERE date(start) >= ?
            """, (cutoff_date,)).fetchall()

            total_work = 0.0
            total_rest = 0.0
            max_work = 0.0
            hourly = [0.0] * 24
            active_dates = set()

            for row in sess_rows:
                mode = (row["mode"] or "").lower()
                dur = float(row["duration"] or 0.0)
                st_str = row["start"]
                if st_str:
                    active_dates.add(st_str[:10])
                    try:
                        dt = datetime.fromisoformat(st_str)
                        hourly[dt.hour] += dur
                    except Exception:
                        pass

                if mode == "work":
                    total_work += dur
                    if dur > max_work:
                        max_work = dur
                else:
                    total_rest += dur

            active_days = max(1, len(active_dates))
            fatigue_score = min(100.0, round((total_work / (total_rest + 1.0)) * 12.0, 1))

            result["total_work_seconds"] = round(total_work, 2)
            result["total_rest_seconds"] = round(total_rest, 2)
            result["avg_daily_work_seconds"] = round(total_work / active_days, 2)
            result["longest_continuous_work_seconds"] = round(max_work, 2)
            result["fatigue_risk_score"] = fatigue_score
            result["hourly_distribution"] = [round(h, 2) for h in hourly]

        return result

    def close(self):
        """Cleanly shuts down the batch worker and closes the DuckDB connection."""
        self._shutdown_event.set()
        if hasattr(self, '_worker_thread') and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)
        with self._lock:
            if self._duck_conn is not None:
                try:
                    self._duck_conn.close()
                except Exception:
                    pass
                self._duck_conn = None

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

