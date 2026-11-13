# Prompt Delta Research

Can an LLM work from the original context plus small, exact updates instead of receiving entire files again?

This repository contains local research, codecs, saved Codex answers, and reproducible grading evidence. **It demonstrates smaller experimental messages and successful simple edits. It does not demonstrate lower API bills or guaranteed model accuracy.**

## How the five-round experiment worked

For each of two tasks, round 1 supplied the specification and starting files. Codex wrote an initial solution. Rounds 2–5 introduced one small regression and one harmless comment change. Codex received exact old/new text replacements and file hashes, then produced a repair while keeping the other changes.

Earlier code remained in the conversation. References do not give the model access to files that are absent from its context.

~~~mermaid
flowchart TD
    A["Round 1: full task and starting files"] --> C["Codex uses the retained conversation"]
    B["Rounds 2–5: exact changes and version hashes"] --> C
    C --> D["Create code or a small repair"]
    D --> E["Apply exact replacements locally"]
    E --> F["Fresh Docker container runs independent tests"]
    F --> G["Save code and results"]
    G -->|"Next small change"| B
~~~

Example of a repair, instead of resending the entire expense tracker:

~~~diff
- state["next_id"] += 2
+ state["next_id"] += 1
~~~

The local adapter rejects missing or ambiguous replacement text. Version checks protect against applying an update to the wrong source. These guards check edit application; the tests check behavior.

## Recorded results

Recorded on **2026-11-13**. Counts below use the local **o200k_base tokenizer proxy** and include the five incoming task messages, format instructions, JSON syntax, hashes, and negative-control summaries.

| Task | Repaired rounds passing existing tests | Full-file incoming tokens | Change-packet incoming tokens | Incoming reduction |
|---|---:|---:|---:|---:|
| Log parser | 5/5 | 1,429 | 1,192 | 16.59% |
| Expense tracker | 5/5 | 5,926 | 1,762 | 70.27% |

Including the saved answer and acknowledgment payloads, the reductions are **9.83%** and **51.82%** respectively. The full-file arm is an offline calculation using the same saved answers, not a separately executed model arm.

- All 10 repaired rounds passed: 50 test-method executions, repeating the same 3 parser and 7 expense tests.
- All 8 change packets reconstructed their source exactly; 36 integrity checks passed.
- The two starting versions and 7 of 8 later mutations failed the existing grader.
- **Known coverage gap:** case-insensitive category filtering passed the expense grader. A supplementary exact-case probe showed that the altered implementation returned both `food` and `Food`; the repaired implementation returned only `food`.

Read the [summary](five-rounds/SUMMARY.txt), [full evidence](five-rounds/results.json), [token counts](five-rounds/tokens.csv), and [grades](five-rounds/grades.csv).

### What these results do not establish

This was one shared Codex conversation. The same assistant designed the mutations and wrote the repairs. Most repairs reverse a simple, already-known mutation. The expense app was built once and then repaired four times; it was not independently rebuilt five times.

The tokenizer proxies are **not verified Codex billing counters**. Complete conversation/tool wrappers, setup, reasoning tokens, and actual provider cache counters were unavailable or outside the measured payloads. There are no measured USD savings. Fresh Docker containers isolate execution; they do not make the model sessions independent.

The graders were unread during the original coding trials. They are now included for auditing, so future runs with access to this repository must not be described as blinded. Keep graders out of model inputs in any new evaluation.

## Earlier codec research, including negative results

[RESEARCH.txt](RESEARCH.txt) documents the earlier investigation and sources. Its statements about “no model inference” refer to that codec-only stage, before the five-round Codex exercise.

`experiment.py` tests whole-line dictionaries, lexical templates, shallow grammar rules, and versioned snapshot deltas. It passed 501 reconstruction/integrity checks. `controls.py` passed 27 additional gzip and scripted-edit controls.

The measurements include repetitive code, mostly unique code, logs, short prompts, Unicode/whitespace edge cases, and the two task inputs. Results were mixed:

| Fixture | Original tokens | Dictionary | Templates | Shallow grammar |
|---|---:|---:|---:|---:|
| Repeated code | 2,239 | 1,066 | 2,054 | 2,802 |
| Mostly unique code | 3,162 | 3,390 | 4,020 | 3,602 |
| Ordered logs | 6,720 | 7,025 | 3,961 | 6,511 |
| Short prompt | 13 | 78 | 98 | 94 |

These are synthetic/local measurements, including encoding overhead. Successful reconstruction does not prove model comprehension. Static compression expanded many inputs; raw text remains necessary.

Dictionary encoding, templates, grammar compression, and delta encoding are established techniques. This repository makes no claim to have invented them.

## Repository tree

~~~text
.
├── experiment.py           Codec and tokenizer experiments
├── controls.py             Gzip and exact-edit controls
├── examples/               Original and encoded test payloads
├── results.json / .csv     Codec-stage measurements
├── controls.json           Control-stage measurements
├── RESEARCH.txt            Original research notes and source list
├── five-rounds/
│   ├── harness.py          Stages rounds, applies saved answers, runs graders
│   ├── answers/            Saved Codex-generated code and repairs
│   ├── log_parser/         Five rounds: inputs, outputs, prompts, test logs
│   ├── expense_app/        Five rounds plus the supplementary case probe
│   ├── case_probe.py       Supplementary category-filter check
│   ├── report.py           Token accounting and integrity checks
│   ├── results.json
│   ├── tokens.csv / grades.csv
│   └── SUMMARY.txt
├── tasks/                  Two specifications and the original parser starter
├── graders/                Original independent graders, now inspectable
├── sandbox/grade.py        Grader launcher
├── Dockerfile.grader       Minimal isolated grading image
├── tokenizer-assets.json   Recorded public vocabulary hashes
├── tokenizer-assets.sha256
└── third_party/            Notice for the Python-source fixture
~~~

`harness.py` does not call Codex or another model automatically. The original assistant authored the saved answers in its conversation. Replaying them reproduces grading and token arithmetic, not a new model evaluation.

## Replay the saved code safely

Requirements: Git and Docker. Run commands from this repository root. Execute the task implementations and graders inside containers, not on the host.

~~~sh
git clone --branch codex/research-package https://github.com/Zhamol/prompt-delta-research.git
cd prompt-delta-research
docker build -f Dockerfile.grader -t prompt-delta-grader:local .
~~~

Run every saved repaired version against the original grader:

~~~sh
for task in log_parser expense_app; do
  for round in 1 2 3 4 5; do
    docker run --rm --network none --read-only \
      --cap-drop ALL --security-opt no-new-privileges \
      --pids-limit 64 --memory 256m --cpus 1 \
      --tmpfs /tmp:rw,nosuid,size=32m \
      -v "$PWD/five-rounds/$task/round-$round/output:/submission:ro" \
      prompt-delta-grader:local \
      timeout 90 python /repo/sandbox/grade.py "$task"
  done
done
~~~

Each invocation creates a fresh container. Only that saved submission is mounted; no home directory, Docker socket, or credentials are mounted. To inspect a negative control, use `input` instead of `output`. A nonzero exit is expected for the recorded failing inputs; expense round 4 is the documented exception.

## Reproduce tokenizer measurements

The existing LiteLLM image is used only as a pinned Python/tiktoken runtime. Its gateway is not started. No LiteLLM, Claude Code, TokenEconomizer, AWS, or model API integration is implemented here.

Pinned runtimes:

| Purpose | Version / immutable reference |
|---|---|
| Grading base | `python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c` |
| Tokenizer runtime | `ghcr.io/berriai/litellm:v1.108.7@sha256:3c73aee257be4888fbbbecdce615e12487579a618fcc7dfb278264a3467a9f9f` |
| Runtime Python / tokenizer | Python 3.13.18 / tiktoken 0.12.0 |
| Tokenizer proxies | `o200k_base`, `cl100k_base` |

Pins preserve the recorded environment; they are not a claim that the images are perpetually maintained or guaranteed safe.

Download the public tokenizer data once and verify its recorded hashes. This requires network access but no credentials or model calls. The cache is excluded from Git.

~~~sh
TOKENIZER_IMAGE='ghcr.io/berriai/litellm:v1.108.7@sha256:3c73aee257be4888fbbbecdce615e12487579a618fcc7dfb278264a3467a9f9f'
docker pull "$TOKENIZER_IMAGE"
mkdir -p tokenizer-cache .replay
curl --fail --location \
  https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken \
  --output tokenizer-cache/9b5ad71b2ce5302211f9c61530b329a4922fc6a4
curl --fail --location \
  https://openaipublic.blob.core.windows.net/encodings/o200k_base.tiktoken \
  --output tokenizer-cache/fb374d419588a4632f3f557e76b4b70aebbca790
shasum -a 256 -c tokenizer-assets.sha256
~~~

Recalculate the five-round report in a new directory, preserving the recorded evidence:

~~~sh
TASK_REPLAY_DIR="$(mktemp -d "$PWD/.replay/report.XXXXXX")"
mkdir "$TASK_REPLAY_DIR/five-rounds"
cp -R five-rounds/log_parser five-rounds/expense_app "$TASK_REPLAY_DIR/five-rounds/"
cp five-rounds/harness.py five-rounds/report.py "$TASK_REPLAY_DIR/five-rounds/"
cp -R tokenizer-cache "$TASK_REPLAY_DIR/"
docker run --rm --network none --read-only \
  --cap-drop ALL --security-opt no-new-privileges --memory 1g --cpus 1 \
  --tmpfs /tmp -e PYTHONDONTWRITEBYTECODE=1 \
  -e TIKTOKEN_CACHE_DIR=/research/tokenizer-cache \
  -v "$TASK_REPLAY_DIR:/research" \
  --entrypoint python "$TOKENIZER_IMAGE" /research/five-rounds/report.py
~~~

For the earlier codec experiment, use another fresh directory:

~~~sh
TASK_REPLAY_DIR="$(mktemp -d "$PWD/.replay/codec.XXXXXX")"
cp experiment.py controls.py "$TASK_REPLAY_DIR/"
cp -R tokenizer-cache "$TASK_REPLAY_DIR/"
docker run --rm --network none --read-only \
  --cap-drop ALL --security-opt no-new-privileges --memory 1g --cpus 1 \
  --tmpfs /tmp -e PYTHONDONTWRITEBYTECODE=1 \
  -e TIKTOKEN_CACHE_DIR=/research/tokenizer-cache \
  -v "$TASK_REPLAY_DIR:/research" -v "$PWD/tasks:/poc:ro" \
  --entrypoint python "$TOKENIZER_IMAGE" /research/experiment.py
docker run --rm --network none --read-only \
  --cap-drop ALL --security-opt no-new-privileges --memory 1g --cpus 1 \
  --tmpfs /tmp -e PYTHONDONTWRITEBYTECODE=1 \
  -e TIKTOKEN_CACHE_DIR=/research/tokenizer-cache \
  -v "$TASK_REPLAY_DIR:/research" \
  --entrypoint python "$TOKENIZER_IMAGE" /research/controls.py
~~~

The scripts retain their original container paths (`/research`, `/poc`, `/repo`) to preserve recorded script hashes. Mounts above supply those paths without requiring the original local POC checkout. Grader copies match the SHA256 values recorded in each round's metadata. Replay-generated timing values may differ.

## What would justify continuing

A future evaluation needs independent model sessions, equivalent full-context and stateful-dictionary baselines, harder changes, identical test criteria, and real provider usage counters. It must count output/reasoning, retries, retrieval, helpers, cache reads/writes, and failed tasks, then compare cost per successful task with dated prices and billing reconciliation.

Prompt caching was not measured here. Stable message prefixes can be inspected locally, but actual cache hits and charges cannot be inferred from that alone. This repository makes no paid calls and does not access AWS.

## Research sources and attribution

- [Dictionary encoding and in-context learning](https://arxiv.org/abs/2604.13066)
- [Meta-token compression](https://arxiv.org/abs/2506.00307)
- [SEQUITUR grammar compression](https://arxiv.org/abs/cs/9709102)
- [VCDIFF delta encoding](https://www.rfc-editor.org/info/rfc3284/)
- [tiktoken 0.12.0](https://github.com/openai/tiktoken/tree/0.12.0)
- [Amazon Bedrock prompt caching](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-caching.html)

The longer source review and the distinction between existing techniques and proposed combinations are in [RESEARCH.txt](RESEARCH.txt). See [third-party notices](THIRD_PARTY_NOTICES.md) for the CPython source included in the mostly-unique-code fixture.
