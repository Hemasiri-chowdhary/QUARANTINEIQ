import asyncio
import json
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from hindsight_client import Hindsight

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

BASE_URL = os.getenv("HINDSIGHT_URL", "http://localhost:8888").rstrip("/")
BANK_ID = os.getenv("HINDSIGHT_BANK_ID", "quarantineiq-experiences")


async def main():
    client = Hindsight(base_url=BASE_URL)
    experience = {
        "experience_id": "verify:quarantineiq:v3",
        "memory_marker": "quarantineiq-v3-verification",
        "test": "test_payment_timeout",
        "service": "payment-service",
        "failure_type": "timeout",
        "evidence": "Payment gateway timeout after 5000ms; retry logic had recently changed.",
        "decision": "investigate",
        "reason": "Repeated timeout failures after a retry change warranted investigation.",
        "human_decision": "quarantine",
        "outcome": "real_regression",
        "lesson": "Timeout failures following retry-logic changes should be investigated before quarantine.",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    try:
        print(f"Hindsight: {BASE_URL}")
        print(f"Bank: {BANK_ID}")
        print("Retaining memory with aretain()...")
        response = await client.aretain(
            bank_id=BANK_ID,
            content=json.dumps(experience, ensure_ascii=False),
            context="QuarantineIQ verification experience",
            document_id=experience["experience_id"],
            metadata={"memory_marker": experience["memory_marker"], "source": "quarantineiq-test"},
        )
        print(f"RETAIN RESPONSE: {response}")
        print("RETAIN: SUCCESS")

        print("Recalling memory with arecall()...")
        recall = await client.arecall(
            bank_id=BANK_ID,
            query="payment timeout retry logic regression quarantine",
            limit=5,
        )
        results = getattr(recall, "results", []) or []
        print(f"RECALL RESULTS: {len(results)}")
        for index, result in enumerate(results, 1):
            print(f"[{index}] {getattr(result, 'text', result)}")
        if not results:
            raise SystemExit("RECALL: FAILED — no memory returned")
        print("RECALL: SUCCESS")
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
