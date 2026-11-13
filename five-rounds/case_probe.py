"""Check exact category matching independently of the saved implementation."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def check_category_filter(workspace):
    records = [
        {"id": 1, "amount_cents": 100, "category": "food", "date": "2024-02-29"},
        {"id": 2, "amount_cents": 200, "category": "Food", "date": "2024-02-29"},
    ]
    with tempfile.TemporaryDirectory() as directory:
        db = Path(directory) / "expenses.json"
        db.write_text(json.dumps({"next_id": 3, "expenses": records}))
        before = db.read_bytes()
        try:
            run = subprocess.run(
                [sys.executable, str(Path(workspace) / "expense_app" / "ledger.py"),
                 "--db", str(db), "list", "--category", "food"],
                capture_output=True, text=True, timeout=10, cwd=directory,
            )
            found = json.loads(run.stdout)
            unchanged = db.read_bytes() == before
            passed = run.returncode == 0 and found == [records[0]] and unchanged
            return {"exact_match_pass": passed, "database_unchanged": unchanged}
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
            return {"exact_match_pass": False, "error": type(error).__name__}
