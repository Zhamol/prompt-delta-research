# Prompt Delta

Send the full task and code first. For later edits in the same conversation, send only the exact changes.

## How it works

~~~text
Round 1: Full specification + starting code
                    ↓
Rounds 2–5: Exact changes + file version hashes
                    ↓
Model returns a repair
                    ↓
Apply the edit locally → run correctness tests
                    ↓
Keep the accepted version for the next round
~~~

Each update identifies the previous file by its SHA256 hash and supplies ordered, literal old/new replacements. The local code rejects missing or ambiguous matches. Reconstruction checks reject stale versions or corrupted updates. Ordinary code remains ordinary code.

The earlier source must remain available in the model's conversation. Start a new conversation with the full source again.

## Use the demo

Install Git and Docker, start Docker, then run:

~~~sh
git clone https://github.com/Zhamol/prompt-delta-research.git
cd prompt-delta-research
./replay.sh
~~~

The first run downloads pinned container images and public tokenizer data. No API key or AWS account is needed.

The command replays the saved answers for both tasks through five rounds each. Every round runs in a fresh Docker container with networking disabled. Task code and graders execute inside those containers. Your home directory, credentials, and Docker socket are not mounted.

Replay checks that:

- Saved edits reproduce the recorded solutions exactly.
- All ten repaired rounds pass the correctness tests.
- The buggy starting versions are rejected, including the category-filter edge case.
- Change packets reconstruct exactly, and stale versions and ambiguous edits are rejected.

Results are written to a new directory on every run:

~~~text
.replay/run.<id>/
├── five-rounds/       Replayed inputs, outputs, and grading results
├── logs/             Diagnostics for each round
└── report/
    ├── SUMMARY.txt
    ├── results.json
    ├── tokens.csv
    └── grades.csv
~~~

This is an offline replay of recorded model answers. It does not generate new answers or automatically connect to a coding assistant.

## Recorded results

The original experiment ran on November 13, 2026.

| Task | Repaired rounds passing tests | Full-file incoming tokens | Change-only incoming tokens | Reduction |
|---|---:|---:|---:|---:|
| Log parser | 5/5 | 1,429 | 1,192 | 16.6% |
| Expense tracker | 5/5 | 5,926 | 1,762 | 70.3% |

Including the saved answer and acknowledgment payloads, the reductions were 9.83% and 51.82%.

[Recorded report](five-rounds/SUMMARY.txt) · [Token counts](five-rounds/tokens.csv) · [Grades](five-rounds/grades.csv) · [Detailed evidence](five-rounds/results.json)

## How the results were obtained

1. Start each task with its full specification and starting files. The expense app starts with a specification only.
2. Produce the initial solution.
3. Introduce one small regression and one harmless comment change per round.
4. Send exact changes against the previously accepted source, retaining the earlier conversation.
5. Apply the returned repair and grade the resulting code in a fresh Docker container.
6. Count the saved full-file and change-only messages with tiktoken 0.12.0 using o200k_base. Counts include format instructions, JSON syntax, hashes, and the saved validation summaries.

The full-file comparison is an offline count using the same saved answers. It was not a separate set of model runs. These were five sequential rounds per task, not five independent builds; the changes and repairs were authored in the same session.

The figures measure message payloads, not actual provider billing. Total conversation overhead, reasoning tokens, cache reads/writes, and USD savings were not measured. Replay recounts the original messages and reports its fresh correctness checks separately.

The original grader missed one category-filter regression. Replay now includes the existing independent case-sensitive filter check; the original recorded results remain unchanged.

## Files

~~~text
replay.sh                  One-command offline replay
five-rounds/harness.py      Prepare versions and apply exact edits
five-rounds/case_probe.py   Category-filter edge-case check
five-rounds/report.py       Integrity checks and token accounting
five-rounds/answers/        Saved answers for the ten rounds
five-rounds/log_parser/     Recorded parser inputs, outputs, and evidence
five-rounds/expense_app/    Recorded app inputs, outputs, and evidence
tasks/                     Specifications and original starting files
graders/                   Independent correctness tests
sandbox/grade.py           Grader launcher
Dockerfile.grader          Pinned grading environment
tokenizer-assets.sha256    Public tokenizer data checksums
~~~

The tokenizer container is used only to run Python and tiktoken; it does not start a model gateway. Container references and tokenizer-data hashes are pinned in the replay script and Dockerfile.
