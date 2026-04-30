# Backup And Restore

## Graph Backup

Export a real graph dump from a known-good database:

```bash
DATABASE_URL=postgresql://... npm run db:graph-export
```

This writes:

- `data/graph/moscow_network.dump`
- `data/graph/moscow_network.dump.manifest.json`

The `data/` directory is intentionally ignored by Git. Store dumps in a secure artifact location with checksum metadata.

## Graph Restore

```bash
GRAPH_DUMP_FILE=data/graph/moscow_network.dump npm run db:graph-restore
```

If the target already has `public.moscow_network`, restore skips by default. Set `FORCE_DB_IMPORT=true` only after confirming backup and source validity.

## App Schema

```bash
npm run db:telemetry-schema
npm run db:migrate
npm run db:migration-check
```

The Alembic baseline is additive and has a no-op downgrade to avoid dropping telemetry or enrichment data.

## Fresh Host

```bash
npm run bootstrap:check
npm run bootstrap:fresh
```

Fresh bootstrap uses isolated Docker volumes and fails with `GRAPH_BOOTSTRAP_REQUIRED` when no real graph source is available.
