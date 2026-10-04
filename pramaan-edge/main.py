"""
PRAMAAN Edge Simulator — Phase 1 skeleton
Simulates edge device behaviour: generates synthetic observation records,
implements store-and-forward queue, hash-chain, bytes counter.
Phase 6 will add real ONNX detector and full scenario playback.
"""
import asyncio
import hashlib
import hmac
import json
import os
import time
import logging
from dataclasses import dataclass, field, asdict
from typing import Optional
import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [EDGE-SIM] %(message)s")
logger = logging.getLogger(__name__)

API_URL = os.getenv("API_URL", "http://localhost:8000")
SIM_INTERVAL = int(os.getenv("SIM_INTERVAL_SECONDS", "60"))
SECRET_KEY = os.getenv("SECRET_KEY", "dev_secret_key_change_in_prod")
SIMULATED = os.getenv("SIMULATED", "true").lower() == "true"

# ─── Bytes counter ────────────────────────────────────────────────────────────

class BytesCounter:
    def __init__(self):
        self.sent = 0
        self.start_time = time.time()

    def add(self, n: int):
        self.sent += n

    @property
    def streaming_equivalent(self) -> int:
        """Design estimate: ~2 Mbps per camera stream."""
        mins_online = (time.time() - self.start_time) / 60
        cameras = 2  # simulated cameras per edge
        return int(cameras * 2 * 1024 * 1024 / 8 * mins_online * 60)

    def report(self) -> dict:
        return {
            "bytes_sent": self.sent,
            "streaming_equivalent": self.streaming_equivalent,
            "savings_pct": max(0, (1 - self.sent / max(self.streaming_equivalent, 1)) * 100),
            "note": "Design estimate — hypothesis, not measured",
        }


# ─── Hash chain ───────────────────────────────────────────────────────────────

def sign_record(record: dict, prev_hash: str, secret: str) -> dict:
    """Sign a record and chain it to the previous hash."""
    payload = json.dumps(record, sort_keys=True, default=str)
    current_hash = hashlib.sha256(f"{prev_hash}:{payload}".encode()).hexdigest()
    signature = hmac.new(secret.encode(), current_hash.encode(), hashlib.sha256).hexdigest()
    return {
        **record,
        "prev_hash": prev_hash,
        "hash": current_hash,
        "signature": signature,
        "simulated": SIMULATED,
    }


# ─── Store-and-forward queue ─────────────────────────────────────────────────

@dataclass
class QueueItem:
    record: dict
    attempts: int = 0


class StoreForwardQueue:
    def __init__(self):
        self._queue: list[QueueItem] = []
        self._lock = asyncio.Lock()

    async def enqueue(self, record: dict):
        async with self._lock:
            self._queue.append(QueueItem(record=record))
            logger.info(f"Queue depth: {len(self._queue)}")

    async def flush(self, client: httpx.AsyncClient) -> int:
        """Attempt to send all queued records. Returns count sent."""
        sent = 0
        async with self._lock:
            remaining = []
            for item in self._queue:
                try:
                    resp = await client.post(
                        f"{API_URL}/ingest/records",
                        json={"records": [item.record]},
                        timeout=5.0,
                    )
                    if resp.status_code == 200:
                        sent += 1
                    else:
                        item.attempts += 1
                        remaining.append(item)
                except Exception:
                    item.attempts += 1
                    remaining.append(item)
            self._queue = remaining
        return sent

    @property
    def depth(self) -> int:
        return len(self._queue)


# ─── Synthetic observation generator ─────────────────────────────────────────

def generate_observation(zone_id: str, device_id: str, scenario: str = "normal") -> dict:
    """Generate a synthetic observation record. MockDetector reads ground-truth."""
    import random, datetime
    ts = datetime.datetime.utcnow().isoformat() + "Z"

    if scenario == "ghost":
        persons = random.randint(2, 5)
    elif scenario == "offline":
        persons = 0
    else:
        persons = random.randint(18, 28)

    return {
        "device_id": device_id,
        "zone_id": zone_id,
        "ts": ts,
        "persons": persons,
        "items": {},
        "feed_ok": scenario != "offline",
        "model_version": "mock-v1.2.0",
        "simulated": True,
    }


# ─── Main loop ────────────────────────────────────────────────────────────────

async def main():
    logger.info(f"PRAMAAN Edge Simulator starting — API: {API_URL}, interval: {SIM_INTERVAL}s")
    logger.info(f"SIMULATED={SIMULATED} — all records carry simulated=true flag")

    counter = BytesCounter()
    queue = StoreForwardQueue()
    prev_hash = "genesis"
    online = True

    async with httpx.AsyncClient() as client:
        # Wait for API to be ready
        for _ in range(30):
            try:
                r = await client.get(f"{API_URL}/health", timeout=2.0)
                if r.status_code == 200:
                    logger.info("API is ready.")
                    break
            except Exception:
                pass
            await asyncio.sleep(2)

        while True:
            try:
                # Generate observation
                raw = generate_observation("zone-sim-01", "edge-sim-01", "normal")
                record = sign_record(raw, prev_hash, SECRET_KEY)
                prev_hash = record["hash"]

                payload_bytes = len(json.dumps(record).encode())
                counter.add(payload_bytes)

                if online:
                    await queue.enqueue(record)
                    sent = await queue.flush(client)
                    if sent > 0:
                        logger.info(f"Sent {sent} record(s). Bytes today: {counter.sent:,}. Queue: {queue.depth}")
                else:
                    await queue.enqueue(record)
                    logger.info(f"OFFLINE — queued. Queue depth: {queue.depth}")

                # Print bandwidth report every 10 cycles
                if int(time.time()) % (SIM_INTERVAL * 10) < SIM_INTERVAL:
                    logger.info(f"Bandwidth report: {counter.report()}")

            except Exception as e:
                logger.error(f"Error in main loop: {e}")

            await asyncio.sleep(SIM_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
