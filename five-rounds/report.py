"""Measure saved task payloads, not Codex billing. Run in the tokenizer container."""
import csv
import hashlib
import importlib.metadata
import json
from pathlib import Path
import tiktoken
from harness import FILENAMES, FORMAT, replace_unique, sha

ROOT = Path("/research/five-rounds")
def read(p):
    return p.read_bytes().decode("utf-8")
def load(p):
    return json.loads(read(p))
def render(x):
    return json.dumps(x, ensure_ascii=False, separators=(",", ":"))
def put(p, text):
    with p.open("x") as stream:
        stream.write(text)
def decode(base, packet):
    if sha(base) != packet["base_sha256"]:
        raise ValueError("stale base")
    result = replace_unique(base, packet["replacements"])
    if sha(result) != packet["current_sha256"]:
        raise ValueError("corrupt delta")
    return result

rounds = []
integrity_checks = 0
for task, name in FILENAMES.items():
    for number in range(1, 6):
        folder = ROOT / task / f"round-{number}"
        before = load(folder / "before.json")
        after = load(folder / "completed.json")
        meta = load(folder / "metadata.json")
        if number > 1:
            base = read(ROOT / task / f"round-{number-1}" / "output" / task / name)
            packet = json.loads(read(folder / "prompt-delta.txt").split("\n", 1)[1])
            assert decode(base, packet).encode("utf-8") == (folder / "input" / task / name).read_bytes()
            integrity_checks += 1
            stale = dict(packet, base_sha256="0" * 64)
            try:
                decode(base, stale)
            except ValueError:
                integrity_checks += 1
            else:
                raise AssertionError("stale base accepted")
            corrupted = dict(packet, current_sha256="0" * 64)
            try:
                decode(base, corrupted)
            except ValueError:
                integrity_checks += 1
            else:
                raise AssertionError("corrupt update accepted")
        assert sha(read(folder / "output" / task / name)) == after["source_sha256"]
        integrity_checks += 1
        rounds.append({
            "task": task, "round": number, "before_success": before["successful"],
            "before_failed_tests": (before["failures"] or 0) + (before["errors"] or 0),
            "passed": after["successful"], "tests_run": after["tests_run"],
            "failures": after["failures"], "errors": after["errors"],
            "markers_preserved": after["marker_preservation"],
            "grader_seconds": after["grader_seconds"],
            "elapsed_including_orchestration_seconds": after["elapsed_since_prepare_seconds"],
            "source_sha256": after["source_sha256"],
            "provider_input_tokens": None, "provider_output_tokens": None,
            "provider_cache_read_tokens": None, "provider_cache_write_tokens": None,
            "provider_reasoning_tokens": None, "billed_usd": None,
            "extra_saved_packet_or_grade_reads": 2 if task == "expense_app" and number == 4 else 0,
        })

for text, old in [("same same", "same"), ("abc", "missing")]:
    try:
        replace_unique(text, [{"old": old, "new": "x"}])
    except ValueError:
        integrity_checks += 1
    else:
        raise AssertionError("ambiguous/missing edit accepted")

rows = []
totals = []
for encoding_name in ("o200k_base", "cl100k_base"):
    encoding = tiktoken.get_encoding(encoding_name)
    def count(text):
        return len(encoding.encode(text, disallowed_special=()))
    def shared(a, b):
        x = encoding.encode(a, disallowed_special=())
        y = encoding.encode(b, disallowed_special=())
        return next((i for i, (u, v) in enumerate(zip(x, y)) if u != v), min(len(x), len(y)))
    for task in FILENAMES:
        histories = {"full": "", "delta": ""}
        previous_requests = {"full": "", "delta": ""}
        local_rows = []
        for number in range(1, 6):
            folder = ROOT / task / f"round-{number}"
            before = load(folder / "before.json")
            after = load(folder / "completed.json")
            answer = read(folder / "answer.json")
            ack = render({"task": task, "round": number, "accepted": after}) + "\n"
            row = {"tokenizer": encoding_name, "task": task, "round": number,
                   "answer_payload_tokens": count(answer), "acknowledgment_tokens": count(ack)}
            for method in ("full", "delta"):
                incoming = read(folder / ("prompt-" + method + ".txt"))
                incoming += "NEGATIVE_CONTROL " + render(before) + "\n"
                row[method + "_incoming_tokens"] = count(incoming)
                # Replay the same logical history in both representations. This is
                # an offline counterfactual, NOT a second set of model executions.
                request = histories[method] + "\nTOOL INPUT\n" + incoming
                row[method + "_cumulative_request_tokens"] = count(request)
                row[method + "_stable_prefix_tokens"] = shared(previous_requests[method], request)
                previous_requests[method] = request
                histories[method] = request + "\nASSISTANT ANSWER\n" + answer + "\nTOOL ACK\n" + ack
            rows.append(row)
            local_rows.append(row)
        summary = {"task": task, "tokenizer": encoding_name,
                   "format_instruction_tokens_once": count(FORMAT)}
        for method in ("full", "delta"):
            incoming = sum(r[method + "_incoming_tokens"] for r in local_rows)
            output = sum(r["answer_payload_tokens"] for r in local_rows)
            ack_tokens = sum(r["acknowledgment_tokens"] for r in local_rows)
            summary[method + "_incoming_tokens"] = incoming
            summary[method + "_input_output_ack_payload_tokens"] = incoming + output + ack_tokens
            summary[method + "_sum_cumulative_request_tokens"] = sum(
                r[method + "_cumulative_request_tokens"] for r in local_rows)
        summary["incoming_reduction_percent"] = round(
            100 * (1 - summary["delta_incoming_tokens"] / summary["full_incoming_tokens"]), 2)
        summary["input_output_ack_reduction_percent"] = round(
            100 * (1 - summary["delta_input_output_ack_payload_tokens"] /
                   summary["full_input_output_ack_payload_tokens"]), 2)
        totals.append(summary)

result = {
    "design": "Two tasks, five sequential rounds each; first full input, then four seeded regressions as exact change packets.",
    "model_execution": "Answers authored by the current Codex assistant, in one shared conversation; no independent sessions or baseline model arm.",
    "limitations": [
        "The same assistant designed the changes and wrote the repairs. Most repairs reverse simple, known mutations.",
        "This is a smoke test of sequential editing, not a blind accuracy benchmark or five independent repetitions.",
        "Source snapshots and hashes reconstruct exactly; that alone is not evidence of model understanding.",
        "Actual code was graded in fresh network-disabled Docker containers against existing unread hidden tests.",
        "Full-input counts are an offline counterfactual using the same answers, not separate model executions.",
        "Tokenizer proxies are not verified Codex billing counters. Complete tool wrappers, this conversation, reasoning and setup are excluded.",
        "Inputs include format instructions, JSON escaping, hashes, source changes and negative-control summaries; outputs and acknowledgments are also reported.",
        "Stable prefixes are local text measurements, not provider cache reads/writes. Billing and cache usage remain unknown.",
        "No Bedrock or external model API calls. No measured USD savings. POC task files were mounted read-only.",
        "Expense round 4 passed the existing grader before repair. A separate exact-case filter probe exposes this coverage gap.",
        "Round 4 required two extra local reads of the saved change packet and aggregate grade after the negative-control guard stopped. No full source was reread.",
    ],
    "tiktoken_version": importlib.metadata.version("tiktoken"),
    "grader_image": "sha256:b75dc32684cd7b5f2550cb49360f9da57bc3a414f5881543c4e9e1185997f2de",
    "tokenizer_image": "ghcr.io/berriai/litellm:v1.108.7@sha256:3c73aee257be4888fbbbecdce615e12487579a618fcc7dfb278264a3467a9f9f",
    "integrity_checks_passed": integrity_checks,
    "script_hashes": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                      for name in ("harness.py", "report.py")},
    "supplementary_case_probe": load(ROOT / "expense_app/round-4/supplementary-case-probe.json"),
    "rounds": rounds, "token_counts": rows, "totals": totals,
}
put(ROOT / "results.json", json.dumps(result, indent=2))
with (ROOT / "tokens.csv").open("x", newline="") as stream:
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
with (ROOT / "grades.csv").open("x", newline="") as stream:
    writer = csv.DictWriter(stream, fieldnames=list(rounds[0]))
    writer.writeheader()
    writer.writerows(rounds)
lines = [
    "FIVE-ROUND SEQUENTIAL EDITING SMOKE TEST",
    "Full starting context, then four lossless change packets. Existing POC unchanged.",
    "",
    f"Completed: {sum(r['passed'] for r in rounds)}/10 rounds; "
    f"{sum(r['tests_run'] or 0 for r in rounds)} hidden-test method executions.",
    f"Failed starting versions/regressions: {sum(not r['before_success'] for r in rounds)}/10.",
    f"Integrity checks: {integrity_checks}.",
    "",
    "o200k_base PROXY incoming payload tokens (all five rounds; includes codec overhead):",
]
for row in totals:
    if row["tokenizer"] == "o200k_base":
        lines.append(
            f"{row['task']}: full {row['full_incoming_tokens']}; delta {row['delta_incoming_tokens']}; "
            f"reduction {row['incoming_reduction_percent']}%. "
            f"Including common answer/ack payloads: {row['input_output_ack_reduction_percent']}%."
        )
lines += ["", "Round results:"]
for row in rounds:
    lines.append(f"{row['task']} {row['round']}: passed={row['passed']}; tests={row['tests_run']}; "
                 f"grading_seconds={row['grader_seconds']}; "
                 f"rejected_before_repair={not row['before_success']}")
lines += ["", "LIMITS"] + result["limitations"]
text = "\n".join(lines) + "\n"
put(ROOT / "SUMMARY.txt", text)
print(text)
