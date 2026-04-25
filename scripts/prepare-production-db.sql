-- SafeRoute production graph preparation.
-- Run after loading public.moscow_network.

BEGIN;

DROP INDEX IF EXISTS public.idx_moscow_network_geometry;
DROP INDEX IF EXISTS public.ix_public_moscow_network_u;
DROP INDEX IF EXISTS public.ix_public_moscow_network_v;

CREATE INDEX IF NOT EXISTS moscow_network_geom_idx ON public.moscow_network USING gist (geometry);
CREATE INDEX IF NOT EXISTS moscow_network_u_idx ON public.moscow_network USING btree (u);
CREATE INDEX IF NOT EXISTS moscow_network_v_idx ON public.moscow_network USING btree (v);
CREATE INDEX IF NOT EXISTS moscow_network_highway_idx ON public.moscow_network USING btree (lower(coalesce(highway, '')));

ALTER TABLE public.moscow_network ADD COLUMN IF NOT EXISTS cost_walk_safe DOUBLE PRECISION;
ALTER TABLE public.moscow_network ADD COLUMN IF NOT EXISTS cost_bike_safe DOUBLE PRECISION;
ALTER TABLE public.moscow_network ADD COLUMN IF NOT EXISTS cost_car_safe DOUBLE PRECISION;
ALTER TABLE public.moscow_network ADD COLUMN IF NOT EXISTS source_x DOUBLE PRECISION;
ALTER TABLE public.moscow_network ADD COLUMN IF NOT EXISTS source_y DOUBLE PRECISION;
ALTER TABLE public.moscow_network ADD COLUMN IF NOT EXISTS target_x DOUBLE PRECISION;
ALTER TABLE public.moscow_network ADD COLUMN IF NOT EXISTS target_y DOUBLE PRECISION;

UPDATE public.moscow_network
SET
  cost_walk_safe = COALESCE(length, 0.0) * COALESCE(safety_weight, 1.0),
  cost_bike_safe = COALESCE(length, 0.0)
    * CASE
        WHEN lower(coalesce(highway, '')) LIKE '%primary%'
          OR lower(coalesce(highway, '')) LIKE '%secondary%'
        THEN 1.15
        ELSE 1.0
      END
    * COALESCE(safety_weight, 1.0),
  cost_car_safe = COALESCE(length, 0.0) * COALESCE(safety_weight, 1.0)
WHERE cost_walk_safe IS NULL
   OR cost_bike_safe IS NULL
   OR cost_car_safe IS NULL;

UPDATE public.moscow_network
SET
  source_x = ST_X(ST_StartPoint(ST_GeometryN(geometry, 1))),
  source_y = ST_Y(ST_StartPoint(ST_GeometryN(geometry, 1))),
  target_x = ST_X(ST_EndPoint(ST_GeometryN(geometry, ST_NumGeometries(geometry)))),
  target_y = ST_Y(ST_EndPoint(ST_GeometryN(geometry, ST_NumGeometries(geometry))))
WHERE geometry IS NOT NULL
  AND (
    source_x IS NULL
    OR source_y IS NULL
    OR target_x IS NULL
    OR target_y IS NULL
  );

DROP MATERIALIZED VIEW IF EXISTS public.moscow_network_nodes;

CREATE MATERIALIZED VIEW public.moscow_network_nodes AS
SELECT DISTINCT ON (node_id)
  node_id,
  node_geometry AS geometry
FROM (
  SELECT
    u AS node_id,
    ST_StartPoint(ST_GeometryN(geometry, 1)) AS node_geometry
  FROM public.moscow_network
  WHERE geometry IS NOT NULL
  UNION ALL
  SELECT
    v AS node_id,
    ST_EndPoint(ST_GeometryN(geometry, ST_NumGeometries(geometry))) AS node_geometry
  FROM public.moscow_network
  WHERE geometry IS NOT NULL
) AS nodes
WHERE node_geometry IS NOT NULL
ORDER BY node_id;

CREATE UNIQUE INDEX moscow_network_nodes_pkey ON public.moscow_network_nodes (node_id);
CREATE INDEX moscow_network_nodes_geom_idx ON public.moscow_network_nodes USING gist (geometry);

ANALYZE public.moscow_network;
ANALYZE public.moscow_network_nodes;

COMMIT;
