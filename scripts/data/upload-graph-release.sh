#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
GRAPH_DUMP_FILE="${SAFEROUTE_GRAPH_DUMP_PATH:-${GRAPH_DUMP_FILE:-$ROOT_DIR/data/graph/moscow_network.dump}}"
JQ_BIN="${JQ_BIN:-jq}"
CONFIRM_GRAPH_RELEASE_UPLOAD="${CONFIRM_GRAPH_RELEASE_UPLOAD:-false}"
GRAPH_RELEASE_CLOBBER="${GRAPH_RELEASE_CLOBBER:-false}"

cd "$ROOT_DIR"

if [[ "$CONFIRM_GRAPH_RELEASE_UPLOAD" != "true" ]]; then
  echo "fail: upload requires CONFIRM_GRAPH_RELEASE_UPLOAD=true." >&2
  echo "This creates or modifies a GitHub Release and uploads the real graph dump." >&2
  exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "fail: gh CLI is not installed." >&2
  exit 1
fi

gh auth status >/dev/null

manifest="${GRAPH_DUMP_FILE}.manifest.json"
graph_schema_version="$("$JQ_BIN" -r '.graph_schema_version' "$manifest")"
release_tag="${GRAPH_RELEASE_TAG:-graph-moscow-network-v${graph_schema_version}}"
release_title="${GRAPH_RELEASE_TITLE:-SafeRoute Moscow graph v${graph_schema_version}}"
release_repo="${GRAPH_RELEASE_REPO:-$(gh repo view --json nameWithOwner -q .nameWithOwner)}"
release_dir="$ROOT_DIR/data/graph/release/$release_tag"
checksum_path="$release_dir/moscow_network.dump.sha256"
manifest_copy="$release_dir/moscow_network.dump.manifest.json"
notes_path="$release_dir/RELEASE_NOTES.md"

GRAPH_RELEASE_TAG="$release_tag" GRAPH_DUMP_FILE="$GRAPH_DUMP_FILE" bash scripts/data/check-graph-release.sh >/dev/null

assets=(
  "$GRAPH_DUMP_FILE"
  "$manifest_copy"
  "$checksum_path"
)

if gh release view "$release_tag" --repo "$release_repo" >/dev/null 2>&1; then
  if [[ "$GRAPH_RELEASE_CLOBBER" != "true" ]]; then
    echo "fail: release $release_tag already exists in $release_repo." >&2
    echo "Set GRAPH_RELEASE_CLOBBER=true to upload and replace assets intentionally." >&2
    exit 1
  fi
  gh release upload "$release_tag" "${assets[@]}" --repo "$release_repo" --clobber
else
  gh release create "$release_tag" "${assets[@]}" \
    --repo "$release_repo" \
    --title "$release_title" \
    --notes-file "$notes_path"
fi

release_json="$(gh release view "$release_tag" --repo "$release_repo" --json tagName,url,assets)"
for asset_name in "moscow_network.dump" "moscow_network.dump.manifest.json" "moscow_network.dump.sha256"; do
  if ! printf "%s" "$release_json" | "$JQ_BIN" -e --arg name "$asset_name" '.assets[] | select(.name == $name)' >/dev/null; then
    echo "fail: uploaded release is missing asset $asset_name" >&2
    exit 1
  fi
done

echo "Graph release upload verified."
printf "%s\n" "$release_json" | "$JQ_BIN" '{tagName, url, assets: [.assets[] | {name, size, state, downloadUrl}]}'
