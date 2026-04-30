#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
GRAPH_DUMP_FILE="${SAFEROUTE_GRAPH_DUMP_PATH:-${GRAPH_DUMP_FILE:-$ROOT_DIR/data/graph/moscow_network.dump}}"
JQ_BIN="${JQ_BIN:-jq}"

checksum_file() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
}

cd "$ROOT_DIR"

GRAPH_DUMP_FILE="$GRAPH_DUMP_FILE" bash scripts/data/check-graph-dump.sh >/dev/null

manifest="${GRAPH_DUMP_FILE}.manifest.json"
graph_schema_version="$("$JQ_BIN" -r '.graph_schema_version' "$manifest")"
release_tag="${GRAPH_RELEASE_TAG:-graph-moscow-network-v${graph_schema_version}}"
release_dir="$ROOT_DIR/data/graph/release/$release_tag"
checksum_path="$release_dir/moscow_network.dump.sha256"
manifest_copy="$release_dir/moscow_network.dump.manifest.json"
notes_path="$release_dir/RELEASE_NOTES.md"
commands_path="$release_dir/UPLOAD_COMMANDS.sh"

for required_file in "$checksum_path" "$manifest_copy" "$notes_path" "$commands_path"; do
  if [[ ! -f "$required_file" ]]; then
    echo "fail: missing release package file: ${required_file#$ROOT_DIR/}" >&2
    echo "Run npm run release:graph:prepare first." >&2
    exit 1
  fi
done

expected_sha="$(awk '{print $1}' "$checksum_path")"
actual_sha="$(checksum_file "$GRAPH_DUMP_FILE")"
manifest_sha="$("$JQ_BIN" -r '.sha256' "$manifest_copy")"
if [[ "$expected_sha" != "$actual_sha" || "$manifest_sha" != "$actual_sha" ]]; then
  echo "fail: release checksum files do not match the graph dump" >&2
  echo "  dump:     $actual_sha" >&2
  echo "  checksum: $expected_sha" >&2
  echo "  manifest: $manifest_sha" >&2
  exit 1
fi

if [[ -f "$release_dir/moscow_network.dump" ]]; then
  echo "fail: release staging directory must not contain a copied dump: ${release_dir#$ROOT_DIR/}/moscow_network.dump" >&2
  echo "Upload the real dump from data/graph directly; do not duplicate large artifacts in git-adjacent staging." >&2
  exit 1
fi

echo "Graph release package check passed."
echo "  tag: $release_tag"
echo "  dump: ${GRAPH_DUMP_FILE#$ROOT_DIR/}"
echo "  release_dir: ${release_dir#$ROOT_DIR/}"
echo "  sha256: $actual_sha"

if command -v gh >/dev/null 2>&1; then
  repo="${GRAPH_RELEASE_REPO:-$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || true)}"
  if [[ -n "$repo" ]]; then
    if gh release view "$release_tag" --repo "$repo" >/dev/null 2>&1; then
      echo "  github_release: exists in $repo"
    else
      echo "  github_release: not found in $repo"
    fi
  else
    echo "  github_release: gh is installed, but repository could not be resolved"
  fi
else
  echo "  github_release: gh CLI not installed"
fi
