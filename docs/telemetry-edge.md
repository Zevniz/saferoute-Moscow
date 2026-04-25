# Telemetry And Edge Roadmap

SafeRoute v2.1 starts the sidewalk digital twin with telemetry ingestion instead of shipping a fake CV demo.

## API

- `POST /api/telemetry/sidewalk-samples` accepts scooter, robot, mobile, manual, and edge-camera observations.
- `GET /api/sidewalk-cells?bbox=<minLon,minLat,maxLon,maxLat>&resolution=<n>` returns aggregated H3 cells as GeoJSON.

## Data Model

- Raw samples are stored in `sidewalk_samples`.
- Aggregates are stored in `sidewalk_cell_aggregates`.
- Each sample maps to an H3 cell at resolution `7-12`; default is `9`.
- Quality combines `surface_score`, `vibration_rms`, `obstacle_score`, and `gps_accuracy_m`.

## Edge AI Phase 2

- Edge devices should export compact observations, not raw video, by default.
- Recommended inference path for NVIDIA edge targets: train/export model to ONNX, optimize with TensorRT, run low-latency inference on Jetson-class devices, and send only privacy-safe metrics to SafeRoute.
- The backend contract is model-version aware so CV models can evolve without changing the public API.

## No Placeholder Policy

The current UI/API exposes only real telemetry if samples exist. Empty cell responses are valid and mean no samples have been ingested for that bbox/resolution.
