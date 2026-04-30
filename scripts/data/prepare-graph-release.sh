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

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "$1 is not available. Install it or set the matching *_BIN env." >&2
    exit 1
  fi
}

cd "$ROOT_DIR"
require_cmd "$JQ_BIN"

GRAPH_DUMP_FILE="$GRAPH_DUMP_FILE" bash scripts/data/check-graph-dump.sh >/dev/null

manifest="${GRAPH_DUMP_FILE}.manifest.json"
dataset_name="$("$JQ_BIN" -r '.dataset_name' "$manifest")"
dataset_table="$("$JQ_BIN" -r '.dataset_table' "$manifest")"
city="$("$JQ_BIN" -r '.city' "$manifest")"
region="$("$JQ_BIN" -r '.region' "$manifest")"
created_at="$("$JQ_BIN" -r '.created_at' "$manifest")"
row_count="$("$JQ_BIN" -r '.row_count' "$manifest")"
node_row_count="$("$JQ_BIN" -r '.node_row_count' "$manifest")"
srid="$("$JQ_BIN" -r '.srid' "$manifest")"
graph_schema_version="$("$JQ_BIN" -r '.graph_schema_version' "$manifest")"
route_data_version="$("$JQ_BIN" -r '.route_data_version' "$manifest")"
manifest_sha="$("$JQ_BIN" -r '.sha256' "$manifest")"
actual_sha="$(checksum_file "$GRAPH_DUMP_FILE")"
if [[ "$actual_sha" != "$manifest_sha" ]]; then
  echo "fail: manifest SHA does not match dump SHA" >&2
  exit 1
fi

release_tag="${GRAPH_RELEASE_TAG:-graph-moscow-network-v${graph_schema_version}}"
release_title="${GRAPH_RELEASE_TITLE:-SafeRoute Moscow graph v${graph_schema_version}}"
release_dir="$ROOT_DIR/data/graph/release/$release_tag"
checksum_path="$release_dir/moscow_network.dump.sha256"
manifest_copy="$release_dir/moscow_network.dump.manifest.json"
notes_path="$release_dir/RELEASE_NOTES.md"
commands_path="$release_dir/UPLOAD_COMMANDS.sh"

mkdir -p "$release_dir"
cp "$manifest" "$manifest_copy"
printf "%s  %s\n" "$actual_sha" "$(basename "$GRAPH_DUMP_FILE")" > "$checksum_path"
cat > "$notes_path" <<MARKDOWN
# ${release_title}

Real SafeRoute graph artifact for restoring \`${dataset_table}\`.

## Dataset

- Dataset: ${dataset_name}
- City: ${city}
- Region: ${region}
- Created at: ${created_at}
- Row count: ${row_count}
- Node row count: ${node_row_count}
- SRID: ${srid}
- Graph schema version: ${graph_schema_version}
- Route data version: ${route_data_version}
- SHA-256: \`${actual_sha}\`

## Assets

- \`moscow_network.dump\`
- \`moscow_network.dump.manifest.json\`
- \`moscow_network.dump.sha256\`

## Verify And Restore

\`\`\`bash
shasum -a 256 -c moscow_network.dump.sha256
SAFEROUTE_GRAPH_DUMP_PATH=/path/to/moscow_network.dump npm run db:graph-dump-check
TARGET_DATABASE_URL=postgresql://... SAFEROUTE_GRAPH_DUMP_PATH=/path/to/moscow_network.dump npm run db:graph-restore
\`\`\`

Do not commit the dump or release staging files to git.
MARKDOWN

cat > "$commands_path" <<COMMANDS
#!/usr/bin/env bash
set -euo pipefail

# Generated upload commands for ${release_tag}.
# Run from the repository root after reviewing release notes.

GRAPH_RELEASE_TAG=${release_tag} npm run release:graph:check
CONFIRM_GRAPH_RELEASE_UPLOAD=true GRAPH_RELEASE_TAG=${release_tag} npm run release:graph:upload
COMMANDS
chmod +x "$commands_path"

echo "Graph release package prepared."
echo "  tag: $release_tag"
echo "  dump: ${GRAPH_DUMP_FILE#$ROOT_DIR/}"
echo "  manifest: ${manifest#$ROOT_DIR/}"
echo "  manifest_copy: ${manifest_copy#$ROOT_DIR/}"
echo "  checksum: ${checksum_path#$ROOT_DIR/}"
echo "  notes: ${notes_path#$ROOT_DIR/}"
echo "  upload_commands: ${commands_path#$ROOT_DIR/}"
