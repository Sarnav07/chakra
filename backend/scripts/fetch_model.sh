#!/usr/bin/env bash
# Fetch the private classifier artifact during a Render build. Neither the
# model nor the GitHub token is stored in this repository.
set -euo pipefail

: "${MODEL_URL:?MODEL_URL must point to the private GitHub Release asset}"
: "${GITHUB_TOKEN:?GITHUB_TOKEN must be a read-only token for the private repository}"

model_dir="${CHAKRA_MODEL_DIR:-data/model}"
mkdir -p "$model_dir"

curl --fail --location --retry 3 \
  --header "Authorization: Bearer ${GITHUB_TOKEN}" \
  --header "Accept: application/octet-stream" \
  --output "${model_dir}/item_classifier.pt" \
  "$MODEL_URL"

test -s "${model_dir}/item_classifier.pt"
