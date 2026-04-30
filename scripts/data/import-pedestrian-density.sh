#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PEDESTRIAN_DENSITY_FILE="${PEDESTRIAN_DENSITY_FILE:-}"
DATASET_VERSION="${DATASET_VERSION:-}"
SOURCE_NAME="${SOURCE_NAME:-}"
SOURCE_OWNER="${SOURCE_OWNER:-}"
SOURCE_URL="${SOURCE_URL:-}"
SOURCE_LICENSE="${SOURCE_LICENSE:-}"
SOURCE_LICENSE_CONFIRMED="${SOURCE_LICENSE_CONFIRMED:-false}"
SOURCE_CHECKSUM="${SOURCE_CHECKSUM:-}"
EDGE_MAPPING_METHOD="${EDGE_MAPPING_METHOD:-}"
ACTIVATE_ENRICHMENT="${ACTIVATE_ENRICHMENT:-false}"
DEACTIVATE_OTHER_ENRICHMENT_DATASETS="${DEACTIVATE_OTHER_ENRICHMENT_DATASETS:-false}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

fail() {
  echo "fail: $*" >&2
  exit 1
}

normalize_bool() {
  printf "%s" "$1" | tr '[:upper:]' '[:lower:]'
}

activation="$(normalize_bool "$ACTIVATE_ENRICHMENT")"
license_confirmed="$(normalize_bool "$SOURCE_LICENSE_CONFIRMED")"

if [[ "$activation" != "true" && "$activation" != "false" ]]; then
  fail "ACTIVATE_ENRICHMENT must be true or false"
fi

if [[ "$license_confirmed" != "true" && "$license_confirmed" != "false" ]]; then
  fail "SOURCE_LICENSE_CONFIRMED must be true or false"
fi

if [[ -z "$PEDESTRIAN_DENSITY_FILE" ]]; then
  fail "PEDESTRIAN_DENSITY_FILE is required and must point to a real licensed pedestrian-density CSV"
fi

if [[ ! -f "$PEDESTRIAN_DENSITY_FILE" ]]; then
  fail "PEDESTRIAN_DENSITY_FILE does not exist: $PEDESTRIAN_DENSITY_FILE"
fi

for required_name in DATASET_VERSION SOURCE_NAME SOURCE_OWNER SOURCE_URL SOURCE_LICENSE SOURCE_CHECKSUM EDGE_MAPPING_METHOD; do
  if [[ -z "${!required_name:-}" ]]; then
    fail "$required_name is required for pedestrian density imports"
  fi
done

source_realpath="$("$PYTHON_BIN" - "$PEDESTRIAN_DENSITY_FILE" <<'PY'
from pathlib import Path
import sys
print(Path(sys.argv[1]).resolve())
PY
)"

case "$source_realpath" in
  */tests/fixtures/*)
    if [[ "$activation" == "true" ]]; then
      fail "test fixtures under tests/fixtures cannot be activated as production pedestrian density data"
    fi
    ;;
esac

metadata_text="$(printf "%s %s %s %s %s" "$SOURCE_NAME" "$SOURCE_OWNER" "$SOURCE_URL" "$SOURCE_LICENSE" "$EDGE_MAPPING_METHOD" | tr '[:upper:]' '[:lower:]')"
case "$metadata_text" in
  *poi*|*transit*|*station*|*land_use*|*proxy*)
    fail "pedestrian density import rejects POI/transit/land-use proxy sources"
    ;;
esac

if [[ "$activation" == "true" && "$license_confirmed" != "true" ]]; then
  fail "ACTIVATE_ENRICHMENT=true requires SOURCE_LICENSE_CONFIRMED=true for a licensed pedestrian-density export"
fi

actual_checksum="$("$PYTHON_BIN" - "$PEDESTRIAN_DENSITY_FILE" <<'PY'
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

digest = hashlib.sha256()
with Path(sys.argv[1]).open("rb") as handle:
    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
        digest.update(chunk)
print(digest.hexdigest())
PY
)"
expected_checksum="$(printf "%s" "$SOURCE_CHECKSUM" | sed -E 's/^sha256://I' | tr '[:upper:]' '[:lower:]')"
if [[ "$actual_checksum" != "$expected_checksum" ]]; then
  fail "SOURCE_CHECKSUM mismatch: expected sha256:$expected_checksum, got sha256:$actual_checksum"
fi

tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/saferoute-pedestrian-density.XXXXXX")"
trap 'rm -rf "$tmp_dir"' EXIT
normalized_csv="$tmp_dir/enrichment.csv"
validation_report="$tmp_dir/validation-report.json"
metadata_file="$tmp_dir/source-metadata.json"

cd "$ROOT_DIR"
"$PYTHON_BIN" scripts/data/validate-measured-layer-csv.py pedestrian_density "$PEDESTRIAN_DENSITY_FILE" "$normalized_csv" "$validation_report" >/dev/null

"$PYTHON_BIN" - \
  "$validation_report" \
  "$metadata_file" \
  "$actual_checksum" \
  "$SOURCE_OWNER" \
  "$SOURCE_URL" \
  "$SOURCE_LICENSE" \
  "$EDGE_MAPPING_METHOD" \
  "$SOURCE_LICENSE_CONFIRMED" <<'PY'
from __future__ import annotations

import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    validation = json.load(handle)

metadata = {
    **validation,
    "source_owner": sys.argv[4],
    "source_url": sys.argv[5],
    "source_license": sys.argv[6],
    "source_checksum": f"sha256:{sys.argv[3]}",
    "edge_mapping_method": sys.argv[7],
    "source_license_confirmed": sys.argv[8].lower() == "true",
}
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    json.dump(metadata, handle, ensure_ascii=False, indent=2)
    handle.write("\n")
PY

ENRICHMENT_FILE="$normalized_csv" \
DATASET_VERSION="$DATASET_VERSION" \
SOURCE_NAME="$SOURCE_NAME" \
SOURCE_URL="$SOURCE_URL" \
SOURCE_CHECKSUM="sha256:$actual_checksum" \
SOURCE_METADATA_FILE="$metadata_file" \
ACTIVATE_ENRICHMENT="$activation" \
DEACTIVATE_OTHER_ENRICHMENT_DATASETS="$DEACTIVATE_OTHER_ENRICHMENT_DATASETS" \
bash scripts/data/import-enrichment.sh
