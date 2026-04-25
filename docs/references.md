# Official References

These primary references guided the v2 implementation choices.

## Frontend

- [Motion layout animations](https://motion.dev/docs/react-layout-animations)
- [MotionConfig and reduced motion](https://motion.dev/docs/react-motion-config)
- [MapLibre Map API, including fitBounds](https://maplibre.org/maplibre-gl-js/docs/API/classes/Map/)
- [MapLibre animate a line example](https://maplibre.org/maplibre-gl-js/docs/examples/animate-a-line/)

## Routing And Geocoding

- [Valhalla API overview](https://valhalla.github.io/valhalla/api/)
- [Valhalla turn-by-turn route API](https://valhalla.github.io/valhalla/api/turn-by-turn/api-reference/)
- [Valhalla map matching and trace_route](https://valhalla.github.io/valhalla/api/map-matching/api-reference/)
- [Photon README and features](https://github.com/komoot/photon)
- [OpenStreetMap Foundation Nominatim usage policy](https://operations.osmfoundation.org/policies/nominatim/)
- [Geofabrik Central Federal District OSM extract](https://download.geofabrik.de/russia/central-fed-district.html)

## Backend

- [FastAPI response models](https://fastapi.tiangolo.com/tutorial/response-model/)
- [SQLAlchemy engine and pooling docs](https://docs.sqlalchemy.org/en/20/core/engines_connections.html)
- [Prometheus exposition formats](https://prometheus.io/docs/instrumenting/exposition_formats/)
- [H3 geospatial indexing documentation](https://h3geo.org/docs/)
- [NVIDIA TensorRT documentation](https://docs.nvidia.com/tensorrt/index.html)

## Project Decision Notes

- Public Nominatim is not used from the browser runtime because app autocomplete/search-as-you-type should go through the SafeRoute backend and a dedicated geocoder.
- Valhalla is the maneuver source of truth because it returns route geometry and turn-by-turn maneuvers with shape indexes.
- PostGIS remains the safety-data source of truth because the custom `moscow_network.safety_weight` values live there.
