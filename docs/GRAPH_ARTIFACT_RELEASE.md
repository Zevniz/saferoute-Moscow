# Graph Artifact Release

SafeRoute public deployments need a reproducible real graph artifact for `public.moscow_network`. The project must not generate fake graph rows during bootstrap.

## Artifact Location

Store graph artifacts outside git by default:

- `data/graph/moscow_network.dump`
- `data/graph/moscow_network.dump.manifest.json`

The preferred path env is `SAFEROUTE_GRAPH_DUMP_PATH`. `GRAPH_DUMP_FILE` remains supported for compatibility. Precedence is:

1. `SAFEROUTE_GRAPH_DUMP_PATH`
2. `GRAPH_DUMP_FILE`
3. `data/graph/moscow_network.dump`

Do not commit graph dumps, manifests, or release temp artifacts. They are ignored by `.gitignore` and must be published as release assets or stored in controlled object storage.

Current prepared local artifact:

- Repository target: `Zevniz/saferoute-ultimate`
- Repository visibility: private
- Default release tag: `graph-moscow-network-v1`
- Dump path: `data/graph/moscow_network.dump`
- Manifest path: `data/graph/moscow_network.dump.manifest.json`
- SHA-256: `fc28847e08f78f94ce54908324ff3f1905a56ba48c385e30224d2b6f1a4c3a2e`

## Manifest Contract

`npm run db:graph-export` writes a manifest next to the dump. Required fields:

- `dataset_name`
- `dataset_table`
- `city`
- `region`
- `created_at`
- `source_description`
- `source_database_url_redacted`
- `sha256`
- `row_count`
- `node_row_count`
- `srid`
- `graph_schema_version`
- `route_data_version`

`npm run db:graph-dump-check` verifies the dump contains `public.moscow_network`, validates required metadata, checks SRID `4326`, and requires the manifest SHA-256 to match the dump.

## Export

```bash
DATABASE_URL=postgresql://... \
SAFEROUTE_GRAPH_DUMP_PATH=data/graph/moscow_network.dump \
GRAPH_DATASET_NAME="SafeRoute Moscow safety graph" \
GRAPH_CITY=Moscow \
GRAPH_REGION="Moscow and Moscow Oblast" \
GRAPH_SCHEMA_VERSION=1 \
ROUTE_DATA_VERSION=moscow-network-v1 \
npm run db:graph-export

SAFEROUTE_GRAPH_DUMP_PATH=data/graph/moscow_network.dump npm run db:graph-dump-check
```

## Local Release Package

Prepare local release notes and checksum files:

```bash
SAFEROUTE_GRAPH_DUMP_PATH=data/graph/moscow_network.dump npm run release:graph:prepare
SAFEROUTE_GRAPH_DUMP_PATH=data/graph/moscow_network.dump npm run release:graph:check
```

This creates ignored files under `data/graph/release/graph-moscow-network-v1/`:

- `moscow_network.dump.manifest.json`
- `moscow_network.dump.sha256`
- `RELEASE_NOTES.md`
- `UPLOAD_COMMANDS.sh`

The large dump is not copied into release staging.

## GitHub Release Publishing

Use release tags that encode the graph schema version:

```bash
graph-moscow-network-v{graph_schema_version}
```

For the current artifact:

```bash
GRAPH_RELEASE_TAG=graph-moscow-network-v1 npm run release:graph:check
CONFIRM_GRAPH_RELEASE_UPLOAD=true GRAPH_RELEASE_TAG=graph-moscow-network-v1 npm run release:graph:upload
```

`release:graph:upload` intentionally fails unless `CONFIRM_GRAPH_RELEASE_UPLOAD=true` is set. If a release already exists, it fails unless `GRAPH_RELEASE_CLOBBER=true` is also set.

The release must include these assets:

- `moscow_network.dump`
- `moscow_network.dump.manifest.json`
- `moscow_network.dump.sha256`

Consumers verify before restore:

```bash
shasum -a 256 -c moscow_network.dump.sha256
SAFEROUTE_GRAPH_DUMP_PATH=data/graph/moscow_network.dump npm run db:graph-dump-check
```

## Restore

Restore refuses unchecked dumps by default:

```bash
TARGET_DATABASE_URL=postgresql://... \
SAFEROUTE_GRAPH_DUMP_PATH=data/graph/moscow_network.dump \
npm run db:graph-restore
```

Checksum bypass is only for local recovery and must never be used in production:

```bash
ALLOW_UNVERIFIED_GRAPH_DUMP=true ENVIRONMENT=local npm run db:graph-restore
```

With `ENVIRONMENT=production` or `SAFEROUTE_ENV=production`, an unverified graph dump fails closed.

## Fresh Restore Test

Run restore in isolated compose volumes:

```bash
SAFEROUTE_GRAPH_DUMP_PATH=data/graph/moscow_network.dump npm run self-hosted:fresh-restore-test
```

This command uses a separate compose project and removes only its temporary volumes after success. It does not destroy the working stack.

## Rotation

When updating the graph:

1. Export from a known-good real PostGIS source.
2. Verify `npm run db:graph-dump-check`.
3. Run `npm run self-hosted:fresh-restore-test`.
4. Publish dump and manifest together under a new release tag.
5. Update deployment env to the new artifact path or release asset.
6. Keep the previous release available until rollback has been tested.

Never rotate by editing the manifest checksum manually. Re-export or regenerate the manifest from the real dump.
