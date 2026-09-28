import json
import sys
from urllib.request import Request, urlopen

BACKEND = "http://127.0.0.1:8001"
HINDSIGHT = "http://localhost:8888"


def req(url, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if body is not None else {}
    request = Request(url, data=data, method=method, headers=headers)
    with urlopen(request, timeout=45) as response:
        raw = response.read().decode("utf-8")
        return response.status, json.loads(raw) if raw else {}


def check(name, fn):
    try:
        status, payload = fn()
        if not 200 <= status < 300:
            raise RuntimeError(f"HTTP {status}: {payload}")
        print(f"[PASS] {name}")
        return payload
    except Exception as exc:
        print(f"[FAIL] {name}: {exc}")
        return None


def main():
    failures = 0
    if check("Backend health", lambda: req(f"{BACKEND}/health")) is None:
        failures += 1

    hindsight = check("Hindsight health", lambda: req(f"{HINDSIGHT}/health"))
    if hindsight is None or hindsight.get("status") != "healthy":
        failures += 1

    status = check("V3 system status", lambda: req(f"{BACKEND}/api/status"))
    if status is None:
        failures += 1

    tests = check("Test inventory", lambda: req(f"{BACKEND}/api/tests"))
    if tests is None or len(tests) < 6:
        failures += 1

    for name, path in [
        ("Patterns", "/api/patterns"),
        ("Activity", "/api/activity"),
        ("Decision challenges", "/api/decision-challenges"),
        ("GitHub status", "/api/github/status"),
    ]:
        if check(name, lambda p=path: req(f"{BACKEND}{p}")) is None:
            failures += 1

    without = check("Without-memory investigation", lambda: req(f"{BACKEND}/api/demo/without-memory", "POST"))
    if without is None:
        failures += 1

    if hindsight is not None and hindsight.get("status") == "healthy":
        compare = check("With-memory comparison", lambda: req(f"{BACKEND}/api/demo/compare", "POST"))
        if compare is None:
            failures += 1
        else:
            without_score = compare["without_memory"]["attention_score"]["score"]
            with_score = compare["with_memory"]["attention_score"]["score"]
            memory_hits = len(compare["with_memory"].get("historical_evidence", []))
            print(f"       without-memory score: {without_score}")
            print(f"       with-memory score:    {with_score}")
            print(f"       recalled memories:    {memory_hits}")
            if memory_hits == 0:
                failures += 1
                print("[FAIL] Hindsight returned no historical evidence for the seeded demo")
            if with_score < without_score:
                failures += 1
                print("[FAIL] Memory-aware score should not be lower than the stateless demo score")

    print("\nV3 verification passed." if failures == 0 else f"\nV3 verification failed: {failures} check(s).")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
