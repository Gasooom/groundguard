#!/usr/bin/env bash
# Run the v2 pipeline with the optional NLI backend and write run files.
#
# This needs network access to download the model, which the development
# environment used for M4a did not have. Run it where Hugging Face is
# reachable, review the output, and commit the run files. Until then the
# repository claims no NLI results.
#
#   pip install -e ".[dev,nli]"
#   scripts/run_nli_benchmark.sh cross-encoder/nli-deberta-v3-small <commit-sha>
#
# Pin the revision to a commit hash (shown on the model page under "Files and
# versions"), so the run is reproducible.
set -euo pipefail

MODEL="${1:?usage: run_nli_benchmark.sh MODEL_ID REVISION_SHA}"
REVISION="${2:?usage: run_nli_benchmark.sh MODEL_ID REVISION_SHA}"
SLUG="$(echo "$MODEL" | tr '/' '_')"
OUT="benchmark/results"

groundguard bench run --dataset gg-legacy-v1 --input-mode context --engine v2 \
  --backend nli --nli-model "$MODEL" --nli-revision "$REVISION" \
  --out "$OUT/v2-nli.$SLUG.legacy.context.json"

groundguard bench compare "$OUT/v2-m3.conjunct.default.context.json" \
  "$OUT/v2-nli.$SLUG.legacy.context.json" || true

if [ -f benchmark/datasets/gg-claims-v2/splits.json ]; then
  groundguard bench claims --records benchmark/datasets/gg-claims-v2/records.jsonl --split dev \
    --backend nli --nli-model "$MODEL" --nli-revision "$REVISION" \
    --out "$OUT/v2-nli.$SLUG.claims-dev.json"
else
  echo "gg-claims-v2 is not frozen yet; skipping the claim-level dev run"
fi
