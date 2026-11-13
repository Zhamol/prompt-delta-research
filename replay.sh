#!/bin/sh
# Replay saved edits in fresh, offline containers; no model API calls.
set -eu
TASK_REPO=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$TASK_REPO"
TASK_TOKENIZER_IMAGE='ghcr.io/berriai/litellm:v1.108.7@sha256:3c73aee257be4888fbbbecdce615e12487579a618fcc7dfb278264a3467a9f9f'
mkdir -p tokenizer-cache .replay
if [ ! -f tokenizer-cache/9b5ad71b2ce5302211f9c61530b329a4922fc6a4 ]; then
  curl --fail --location --silent --show-error \
    https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken \
    --output tokenizer-cache/9b5ad71b2ce5302211f9c61530b329a4922fc6a4
fi
if [ ! -f tokenizer-cache/fb374d419588a4632f3f557e76b4b70aebbca790 ]; then
  curl --fail --location --silent --show-error \
    https://openaipublic.blob.core.windows.net/encodings/o200k_base.tiktoken \
    --output tokenizer-cache/fb374d419588a4632f3f557e76b4b70aebbca790
fi
shasum -a 256 -c tokenizer-assets.sha256
TASK_GRADER_IMAGE=$(docker build --quiet -f Dockerfile.grader .)
TASK_RUN=$(mktemp -d "$TASK_REPO/.replay/run.XXXXXX")
mkdir "$TASK_RUN/five-rounds" "$TASK_RUN/logs"
cp five-rounds/harness.py five-rounds/report.py five-rounds/case_probe.py "$TASK_RUN/five-rounds/"
cp -R five-rounds/answers "$TASK_RUN/five-rounds/"
printf 'Replay directory: %s\n' "$TASK_RUN"
for task in log_parser expense_app; do
  for round in 1 2 3 4 5; do
    if docker run --rm --network none --read-only \
      --cap-drop ALL --security-opt no-new-privileges \
      --pids-limit 64 --memory 256m --cpus 1 \
      --tmpfs /tmp:rw,nosuid,size=32m \
      -v "$TASK_RUN:/research" \
      -v "$TASK_REPO/tasks:/poc:ro" \
      -v "$TASK_REPO/five-rounds:/recorded:ro" \
      "$TASK_GRADER_IMAGE" timeout 180 \
      python /research/five-rounds/harness.py replay "$task" "$round" \
      > "$TASK_RUN/logs/$task-$round.log" 2>&1; then
      printf '%s round %s: PASS\n' "$task" "$round"
    else
      cat "$TASK_RUN/logs/$task-$round.log"
      printf 'Replay failed; retained diagnostics in %s\n' "$TASK_RUN" >&2
      exit 1
    fi
  done
done
docker run --rm --network none --read-only \
  --cap-drop ALL --security-opt no-new-privileges --memory 1g --cpus 1 \
  --tmpfs /tmp -e PYTHONDONTWRITEBYTECODE=1 \
  -e TIKTOKEN_CACHE_DIR=/tokenizer-cache \
  -e DELTA_EVIDENCE_ROOT=/recorded \
  -e DELTA_REPORT_DIR=/research/report \
  -e DELTA_REPLAY_ROOT=/research/five-rounds \
  -e DELTA_GRADER_IMAGE="$TASK_GRADER_IMAGE" \
  -v "$TASK_RUN:/research" \
  -v "$TASK_REPO/five-rounds:/recorded:ro" \
  -v "$TASK_REPO/tokenizer-cache:/tokenizer-cache:ro" \
  --entrypoint python "$TASK_TOKENIZER_IMAGE" /research/five-rounds/report.py
printf '\nReports: %s/report\n' "$TASK_RUN"
