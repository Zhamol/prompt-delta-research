# Keep this harmless revision marker: expense_app-3.
# Keep this harmless revision marker: expense_app-2.
import argparse
from datetime import date
import json
import os
from pathlib import Path
import re
import sys
import tempfile


def require_integer(value):
    if not (type(value) is int):
        raise ValueError("integer required")
    return value


def validate_category(value):
    if not isinstance(value, str):
        raise ValueError("category must be text")
    value = value.strip()
    if not 1 <= len(value) <= 40:
        raise ValueError("category must contain 1 to 40 characters")
    return value


def validate_date(value):
    if not isinstance(value, str) or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is None:
        raise ValueError("date must be YYYY-MM-DD")
    date.fromisoformat(value)
    return value


def parse_amount(value):
    if re.fullmatch(r"[0-9]+(?:\.[0-9]{1,2})?", value) is None:
        raise ValueError("invalid amount")
    whole, separator, fraction = value.partition(".")
    whole = whole.lstrip("0") or "0"
    if len(whole) > 7:
        raise ValueError("amount too large")
    cents = int(whole) * 100 + int(fraction.ljust(2, "0"))
    if not 1 <= cents <= 100000000:
        raise ValueError("amount outside allowed range")
    return cents


def reject_constant(value):
    raise ValueError("invalid JSON constant")


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def load_state(path):
    try:
        contents = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {"next_id": 1, "expenses": []}
    state = json.loads(contents, object_pairs_hook=unique_object, parse_constant=reject_constant)
    if not isinstance(state, dict) or set(state) != {"next_id", "expenses"}:
        raise ValueError("invalid database object")
    expenses = state["expenses"]
    if not isinstance(expenses, list):
        raise ValueError("invalid expenses")
    if require_integer(state["next_id"]) != len(expenses) + 1:
        raise ValueError("invalid next_id")
    for expected_id, record in enumerate(expenses, 1):
        if not isinstance(record, dict) or set(record) != {"id", "amount_cents", "category", "date"}:
            raise ValueError("invalid record")
        if require_integer(record["id"]) != expected_id:
            raise ValueError("invalid record id")
        if not 1 <= require_integer(record["amount_cents"]) <= 100000000:
            raise ValueError("invalid stored amount")
        if validate_category(record["category"]) != record["category"]:
            raise ValueError("stored category must already be trimmed")
        validate_date(record["date"])
    return state


def save_state(path, state):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=path.name + ".", delete=False) as stream:
            temporary = stream.name
            json.dump(state, stream, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--db", required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add", allow_abbrev=False)
    add.add_argument("--amount", required=True)
    add.add_argument("--category", required=True)
    add.add_argument("--date", required=True)
    listing = commands.add_parser("list", allow_abbrev=False)
    listing.add_argument("--category")
    commands.add_parser("summary", allow_abbrev=False)
    args = parser.parse_args()
    try:
        path = Path(args.db)
        if args.command == "add":
            amount = parse_amount(args.amount)
            category = validate_category(args.category)
            day = validate_date(args.date)
        elif args.command == "list":
            category = validate_category(args.category) if args.category is not None else None
        state = load_state(path)
        if args.command == "add":
            result = {"id": state["next_id"], "amount_cents": amount, "category": category, "date": day}
            state["expenses"].append(result)
            state["next_id"] += 1
            save_state(path, state)
        elif args.command == "list":
            result = [r for r in state["expenses"] if category is None or r["category"] == category]
        else:
            totals = {}
            for record in state["expenses"]:
                category = record["category"]
                totals[category] = totals.get(category, 0) + record["amount_cents"]
            result = {"count": len(state["expenses"]), "total_cents": sum(totals.values()),
                      "by_category": totals}
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (ValueError, TypeError, OSError) as exc:
        print("Error: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
