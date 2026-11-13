"""Supplementary exact-match behavior check; does not change the hidden grader."""
import json
from pathlib import Path
import subprocess
import sys

root = Path("/research/five-rounds/expense_app/round-4")
records = [
    {"id": 1, "amount_cents": 100, "category": "food", "date": "2024-02-29"},
    {"id": 2, "amount_cents": 200, "category": "Food", "date": "2024-02-29"},
]
results = {}
for version in ("input", "output"):
    db = Path("/tmp") / (version + "-probe.json")
    db.write_text(json.dumps({"next_id": 3, "expenses": records}))
    before = db.read_bytes()
    run = subprocess.run(
        [sys.executable, str(root / version / "expense_app/ledger.py"),
         "--db", str(db), "list", "--category", "food"],
        capture_output=True, text=True, timeout=10,
    )
    assert run.returncode == 0, run.stderr
    found = json.loads(run.stdout)
    assert db.read_bytes() == before
    results[version] = {"returned_ids": [r["id"] for r in found],
                        "expected_ids": [1], "exact_match_pass": found == [records[0]],
                        "database_unchanged": True}
assert results["input"]["returned_ids"] == [1, 2]
assert results["output"]["exact_match_pass"]
results["scope"] = "Supplementary exact-case matching interpretation used by baseline; existing hidden tests passed both versions."
with (root / "supplementary-case-probe.json").open("x") as stream:
    json.dump(results, stream, indent=2)
print(json.dumps(results))
