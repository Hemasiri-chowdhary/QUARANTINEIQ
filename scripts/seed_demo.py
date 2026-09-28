import json
import os
import sys
from datetime import datetime, timedelta

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.database import models
from backend.database.session import Base, SessionLocal, engine
from backend.hindsight import client as hindsight_client
from backend.hindsight.memory_format import normalize_memory


def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def add_run(db, test, status, now, days_ago, hours_ago=0, failure_type=None, error_message=None, duration=500, retry_count=0, retry_success=False, sha="demo"):
    db.add(models.CIRun(
        test_id=test.id,
        commit_sha=sha,
        status=status,
        failure_type=failure_type,
        error_message=error_message,
        duration=duration,
        retry_count=retry_count,
        retry_success=retry_success,
        timestamp=now - timedelta(days=days_ago, hours=hours_ago),
    ))


def seed_demo_data():
    db = SessionLocal()
    now = datetime.utcnow()
    try:
        tests_data = [
            {"name": "test_payment_timeout", "service": "payment-service", "repository": "org/payment", "status": models.TestStatus.quarantined},
            {"name": "test_payment_retry", "service": "payment-service", "repository": "org/payment", "status": models.TestStatus.active},
            {"name": "test_auth_token_refresh", "service": "identity-service", "repository": "org/identity", "status": models.TestStatus.active},
            {"name": "test_checkout_retry", "service": "checkout-service", "repository": "org/checkout", "status": models.TestStatus.quarantined},
            {"name": "test_order_consistency", "service": "order-service", "repository": "org/order", "status": models.TestStatus.disabled},
            {"name": "test_notification_delivery", "service": "notification-service", "repository": "org/notification", "status": models.TestStatus.active},
        ]
        tests = []
        for item in tests_data:
            test = models.Test(**item, created_at=now - timedelta(days=45), source="demo", external_key=f"demo:{item["name"]}")
            db.add(test)
            tests.append(test)
        db.commit()
        for test in tests:
            db.refresh(test)
        test_map = {test.name: test for test in tests}

        payment = test_map["test_payment_timeout"]
        for i in range(10):
            add_run(db, payment, "passed", now, days_ago=22, hours_ago=i, duration=120, sha=f"pay-pass-{i}")
        for i in range(5):
            add_run(db, payment, "failed", now, days_ago=16, hours_ago=i, failure_type="timeout", error_message="Payment gateway timeout after 5000ms", duration=5000, retry_count=1, retry_success=False, sha=f"pay-fail-{i}")
        payment_decision = models.Decision(
            test_id=payment.id,
            agent_recommendation=models.DecisionType.investigate,
            agent_reason="Repeated timeout failures plus a related retry-logic change warrant investigation before quarantine.",
            human_decision=models.DecisionType.quarantine,
            human_reason="The team quarantined the test to unblock CI while investigating the retry path.",
            timestamp=now - timedelta(days=14),
        )
        db.add(payment_decision)
        db.commit()
        db.refresh(payment_decision)
        db.add(models.Commit(sha="pay-retry-001", message="Update payment retry logic to fail fast", files_changed="payment/retry.py,payment/gateway.py", author="payments-team", timestamp=now - timedelta(days=10)))
        db.add(models.Incident(service="payment-service", title="Payment processing degraded", description="Customers saw failed payments instead of retries.", root_cause="Retry logic was modified to fail fast, exposing gateway latency that the quarantined test was already detecting.", timestamp=now - timedelta(days=2)))
        payment_outcome = models.Outcome(decision_id=payment_decision.id, outcome=models.OutcomeType.real_regression, notes="The timeout failure was a real signal of a retry-handling regression that later contributed to a payment incident.", timestamp=now - timedelta(days=1))
        db.add(payment_outcome)

        retry = test_map["test_payment_retry"]
        for i in range(8):
            add_run(db, retry, "passed" if i != 1 else "failed", now, days_ago=i + 1, failure_type="timeout" if i == 1 else None, error_message="Payment gateway timeout after retry" if i == 1 else None, duration=900 if i == 1 else 400, retry_count=1 if i == 1 else 0, retry_success=True, sha=f"pay-retry-{i}")

        auth = test_map["test_auth_token_refresh"]
        for i in range(6):
            add_run(db, auth, "passed", now, days_ago=i + 1, duration=300, sha=f"auth-{i}")
        db.add(models.Commit(sha="identity-auth-001", message="Refresh token expiry handling", files_changed="identity/auth.py", author="identity-team", timestamp=now - timedelta(days=4)))

        checkout = test_map["test_checkout_retry"]
        for i in range(8):
            failed = i in {1, 4, 6}
            add_run(db, checkout, "failed" if failed else "passed", now, days_ago=i + 1, failure_type="transient_503" if failed else None, error_message="Checkout dependency returned 503" if failed else None, duration=1200 if failed else 500, retry_count=2 if failed else 0, retry_success=failed, sha=f"checkout-{i}")
        checkout_decision = models.Decision(
            test_id=checkout.id,
            agent_recommendation=models.DecisionType.quarantine,
            agent_reason="Failures recover on retry and there is no matching product code change in the current evidence.",
            human_decision=models.DecisionType.investigate,
            human_reason="The team kept the test under observation to confirm the transient dependency pattern.",
            timestamp=now - timedelta(days=3),
        )
        db.add(checkout_decision)
        db.flush()
        db.add(models.Incident(service="checkout-service", title="Checkout dependency saturation", description="A dependency intermittently returned 503s during a traffic burst.", root_cause="Transient downstream capacity pressure.", timestamp=now - timedelta(days=5)))
        checkout_outcome = models.Outcome(decision_id=checkout_decision.id, outcome=models.OutcomeType.genuinely_flaky, notes="The failures recovered on retry and were caused by transient downstream 503s, not a product regression.", timestamp=now - timedelta(days=2))
        db.add(checkout_outcome)

        order = test_map["test_order_consistency"]
        for i in range(3):
            add_run(db, order, "passed", now, days_ago=i + 1, duration=700, sha=f"order-{i}")
        db.add(models.Commit(sha="order-consistency-001", message="Refine order consistency assertions", files_changed="order/consistency.py", author="order-team", timestamp=now - timedelta(days=8)))

        notification = test_map["test_notification_delivery"]
        for i in range(5):
            failed = i == 3
            add_run(db, notification, "failed" if failed else "passed", now, days_ago=i + 1, failure_type="queue_lag" if failed else None, error_message="Notification queue exceeded latency budget" if failed else None, duration=800 if failed else 350, retry_count=1 if failed else 0, retry_success=failed, sha=f"notify-{i}")
        db.add(models.Commit(sha="notify-queue-001", message="Adjust notification queue backoff", files_changed="notification/queue.py", author="notifications-team", timestamp=now - timedelta(days=3)))

        db.commit()
        db.refresh(payment_outcome)
        db.refresh(checkout_outcome)

        experiences = [
            {
                "experience_id": "seed:test_payment_timeout:v1",
                "memory_marker": "quarantineiq-v1-payment-regression",
                "test": payment.name,
                "service": payment.service,
                "repository": payment.repository,
                "failure_type": "timeout",
                "evidence": "Five timeout failures followed a payment retry-logic change; a later payment incident matched the same subsystem.",
                "decision": "investigate",
                "reason": "Repeated timeout failures plus related payment-service changes warranted investigation before quarantine.",
                "human_decision": "quarantine",
                "outcome": "real_regression",
                "lesson": "Intermittent payment timeout failures following retry-logic changes should be investigated before quarantine.",
                "timestamp": payment_outcome.timestamp.isoformat(),
            },
            {
                "experience_id": "seed:test_checkout_retry:v1",
                "memory_marker": "quarantineiq-v1-checkout-flaky",
                "test": checkout.name,
                "service": checkout.service,
                "repository": checkout.repository,
                "failure_type": "transient_503",
                "evidence": "Checkout failures recovered on retry during a downstream dependency capacity event.",
                "decision": "quarantine",
                "reason": "The observed failures were transient and self-recovering without a related product code change.",
                "human_decision": "investigate",
                "outcome": "genuinely_flaky",
                "lesson": "Transient downstream 503s that consistently recover on retry can be genuine flakiness rather than a product regression.",
                "timestamp": checkout_outcome.timestamp.isoformat(),
            },
        ]
    finally:
        db.close()

    for experience in experiences:
        _retain_if_needed(experience)

    print("Demo data seeded successfully.")
    print("Tests: 6 | Quarantined: 2 | Active: 3 | Disabled: 1")


def _retain_if_needed(experience):
    try:
        if not hindsight_client.hindsight_health():
            print("WARNING: Hindsight unavailable; demo memory not retained.")
            return
        marker = experience["memory_marker"]
        existing = hindsight_client.recall_experiences(query=marker, limit=10)
        if any(marker in json.dumps(normalize_memory(item), ensure_ascii=False) for item in existing):
            print(f"Hindsight memory already present: {marker}")
            return
        hindsight_client.retain_experience(experience)
        print(f"Hindsight memory retained: {marker}")
    except hindsight_client.HindsightError as exc:
        print(f"WARNING: Hindsight retention failed: {exc}")


if __name__ == "__main__":
    print("Resetting database...")
    reset_database()
    print("Seeding demo data...")
    seed_demo_data()
