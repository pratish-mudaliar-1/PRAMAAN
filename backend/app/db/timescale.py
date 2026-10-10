"""app/db/timescale.py — TimescaleDB hypertable creation, continuous aggregates and policies.

These DDL statements are executed AFTER Alembic creates the base tables.
They are idempotent (IF NOT EXISTS / OR REPLACE).
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


HYPERTABLE_SQL = """
SELECT create_hypertable(
    'observation',
    'minute_ts',
    if_not_exists => TRUE,
    chunk_time_interval => INTERVAL '1 day'
);
"""

# Continuous aggregate: 5-minute window
CAGG_5MIN_SQL = """
CREATE MATERIALIZED VIEW IF NOT EXISTS observation_5min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('5 minutes', minute_ts) AS bucket,
    device_id,
    zone_id,
    AVG(persons_p90)       AS avg_persons_p90,
    MAX(persons_max)       AS peak_persons,
    AVG(feed_health)       AS avg_feed_health,
    COUNT(*)               AS sample_count
FROM observation
GROUP BY 1, 2, 3
WITH NO DATA;
"""

CAGG_5MIN_POLICY_SQL = """
SELECT add_continuous_aggregate_policy(
    'observation_5min',
    start_offset => INTERVAL '2 hours',
    end_offset   => INTERVAL '5 minutes',
    schedule_interval => INTERVAL '5 minutes',
    if_not_exists => TRUE
);
"""

# Continuous aggregate: hourly
CAGG_HOURLY_SQL = """
CREATE MATERIALIZED VIEW IF NOT EXISTS observation_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', minute_ts) AS bucket,
    device_id,
    zone_id,
    AVG(persons_p90)       AS avg_persons_p90,
    MAX(persons_max)       AS peak_persons,
    AVG(feed_health)       AS avg_feed_health,
    COUNT(*)               AS sample_count
FROM observation
GROUP BY 1, 2, 3
WITH NO DATA;
"""

CAGG_HOURLY_POLICY_SQL = """
SELECT add_continuous_aggregate_policy(
    'observation_hourly',
    start_offset => INTERVAL '3 hours',
    end_offset   => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);
"""

# Compression policy: compress chunks older than 7 days
COMPRESSION_SQL = """
ALTER TABLE observation SET (
    timescaledb.compress,
    timescaledb.compress_orderby = 'minute_ts DESC',
    timescaledb.compress_segmentby = 'device_id, zone_id'
);
"""

COMPRESSION_POLICY_SQL = """
SELECT add_compression_policy(
    'observation',
    INTERVAL '7 days',
    if_not_exists => TRUE
);
"""

# Retention policy: configurable, default 365 days
def retention_policy_sql(retention_days: int = 365) -> str:
    return f"""
SELECT add_retention_policy(
    'observation',
    INTERVAL '{retention_days} days',
    if_not_exists => TRUE
);
"""


async def apply_timescale_policies(
    conn: AsyncConnection,
    *,
    retention_days: int = 365,
    skip_compression: bool = False,
) -> None:
    """Apply hypertable, continuous aggregates, compression and retention policies.

    Call this once after the Alembic migration that creates the observation table.
    All statements are idempotent.
    """
    await conn.execute(text(HYPERTABLE_SQL))
    await conn.execute(text(CAGG_5MIN_SQL))
    await conn.execute(text(CAGG_5MIN_POLICY_SQL))
    await conn.execute(text(CAGG_HOURLY_SQL))
    await conn.execute(text(CAGG_HOURLY_POLICY_SQL))
    if not skip_compression:
        try:
            await conn.execute(text(COMPRESSION_SQL))
        except Exception:  # noqa: BLE001
            pass  # compression already set
        await conn.execute(text(COMPRESSION_POLICY_SQL))
    await conn.execute(text(retention_policy_sql(retention_days)))
