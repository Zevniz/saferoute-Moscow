import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_script_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_package_exposes_graph_source_check_script():
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))

    assert package["scripts"]["db:graph-source-check"] == "bash scripts/check-graph-source.sh"
    assert package["scripts"]["db:graph-dump-check"] == "bash scripts/data/check-graph-dump.sh"
    assert package["scripts"]["db:graph-restore"] == "bash scripts/data/restore-safety-graph.sh"
    assert package["scripts"]["db:migrate"] == "bash scripts/run-migrations.sh"
    assert package["scripts"]["bootstrap:fresh"] == "bash scripts/data/fresh-bootstrap.sh"
    assert package["scripts"]["self-hosted:fresh-restore-test"] == "bash scripts/data/fresh-bootstrap.sh"
    assert package["scripts"]["route:corpus-check"] == "bash scripts/check-route-corpus.sh"
    assert package["scripts"]["release:graph:prepare"] == "bash scripts/data/prepare-graph-release.sh"
    assert package["scripts"]["release:graph:check"] == "bash scripts/data/check-graph-release.sh"
    assert package["scripts"]["release:graph:upload"] == "bash scripts/data/upload-graph-release.sh"
    assert package["scripts"]["security:production-check"] == "bash scripts/check-production-security.sh"
    assert package["scripts"]["db:telemetry-report"] == "bash scripts/report-telemetry.sh"
    assert package["scripts"]["db:enrichment-import:osm"] == "bash scripts/data/import-osm-enrichment.sh"
    assert package["scripts"]["db:enrichment-import:curb-osm"] == "OSM_ADVANCED_FACTORS=curb bash scripts/data/import-osm-advanced-enrichment.sh"
    assert package["scripts"]["db:enrichment-import:crossings-osm"] == "OSM_ADVANCED_FACTORS=crossings bash scripts/data/import-osm-advanced-enrichment.sh"
    assert package["scripts"]["db:enrichment-import:advanced-osm"] == "bash scripts/data/import-osm-advanced-enrichment.sh"
    assert package["scripts"]["db:enrichment-import:micromobility-zones"] == "bash scripts/data/import-micromobility-zones.sh"
    assert package["scripts"]["db:traffic-import:measured"] == "bash scripts/data/import-measured-traffic.sh"
    assert package["scripts"]["db:pedestrian-import:density"] == "bash scripts/data/import-pedestrian-density.sh"
    assert package["scripts"]["db:enrichment-report"] == "bash scripts/report-enrichment.sh"
    assert package["scripts"]["db:enrichment-advanced-report"] == "bash scripts/report-enrichment.sh"


def test_graph_source_check_is_read_only():
    script = (ROOT / "scripts" / "check-graph-source.sh").read_text(encoding="utf-8").upper()

    assert "SELECT" in script
    for destructive_sql in ["DROP ", "DELETE ", "TRUNCATE ", "ALTER ", "CREATE ", "INSERT ", "UPDATE "]:
        assert destructive_sql not in script


def test_import_validates_source_before_target_drop():
    script = (ROOT / "scripts" / "data" / "import-safety-graph.sh").read_text(encoding="utf-8")

    assert "validate_source_graph" in script
    assert script.index("  validate_source_graph\n") < script.index("DROP TABLE IF EXISTS public.moscow_network CASCADE")


def test_fresh_bootstrap_uses_isolated_compose_project_and_requires_real_source():
    script = (ROOT / "scripts" / "data" / "fresh-bootstrap.sh").read_text(encoding="utf-8")

    assert "FRESH_PROJECT_NAME" in script
    assert "GRAPH_BOOTSTRAP_REQUIRED" in script
    assert "check-graph-dump.sh" in script
    assert "fake graph data" in script
    assert "down -v" in script


def test_graph_restore_verifies_dump_before_pg_restore():
    script = (ROOT / "scripts" / "data" / "restore-safety-graph.sh").read_text(encoding="utf-8")

    assert "scripts/data/check-graph-dump.sh" in script
    assert script.index("scripts/data/check-graph-dump.sh") < script.index('--dbname="$TARGET_DATABASE_URL"')
    assert "ALLOW_UNVERIFIED_GRAPH_DUMP" in script
    assert 'normalized_env" != "production"' in script


def test_graph_dump_check_fails_without_manifest(tmp_path):
    dump = tmp_path / "moscow_network.dump"
    dump.write_text("real dump placeholder", encoding="utf-8")
    pg_restore = tmp_path / "pg_restore"
    pg_restore.write_text(
        "#!/usr/bin/env bash\n"
        "if [[ \"$1\" == \"--list\" ]]; then\n"
        "  echo '123; 0 0 TABLE public moscow_network saferoute'\n"
        "  exit 0\n"
        "fi\n"
        "exit 0\n",
        encoding="utf-8",
    )
    pg_restore.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = f"{tmp_path}:{env['PATH']}"
    env["GRAPH_DUMP_FILE"] = str(dump)

    result = subprocess.run(
        ["bash", str(ROOT / "scripts" / "data" / "check-graph-dump.sh")],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "manifest is missing" in result.stderr


def test_graph_dump_check_fails_on_checksum_mismatch(tmp_path):
    dump = tmp_path / "moscow_network.dump"
    dump.write_text("real dump placeholder", encoding="utf-8")
    (tmp_path / "moscow_network.dump.manifest.json").write_text(
        json.dumps(
            {
                "dataset_name": "SafeRoute Moscow safety graph",
                "dataset_table": "public.moscow_network",
                "city": "Moscow",
                "region": "Moscow and Moscow Oblast",
                "created_at": "2026-04-26T00:00:00Z",
                "source_description": "Test manifest for checksum validation",
                "source_database_url_redacted": "postgresql://test@localhost/test",
                "sha256": "deadbeef",
                "row_count": 1,
                "node_row_count": 1,
                "srid": "4326",
                "graph_schema_version": "1",
                "route_data_version": "moscow-network-v1",
            }
        ),
        encoding="utf-8",
    )
    assert hashlib.sha256(dump.read_bytes()).hexdigest() != "deadbeef"
    pg_restore = tmp_path / "pg_restore"
    pg_restore.write_text(
        "#!/usr/bin/env bash\n"
        "if [[ \"$1\" == \"--list\" ]]; then\n"
        "  echo '123; 0 0 TABLE public moscow_network saferoute'\n"
        "  exit 0\n"
        "fi\n"
        "exit 0\n",
        encoding="utf-8",
    )
    pg_restore.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = f"{tmp_path}:{env['PATH']}"
    env["GRAPH_DUMP_FILE"] = str(dump)

    result = subprocess.run(
        ["bash", str(ROOT / "scripts" / "data" / "check-graph-dump.sh")],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "checksum mismatch" in result.stderr


def test_graph_restore_refuses_unverified_dump_in_production(tmp_path):
    dump = tmp_path / "moscow_network.dump"
    dump.write_text("real dump placeholder", encoding="utf-8")
    pg_restore = tmp_path / "pg_restore"
    pg_restore.write_text(
        "#!/usr/bin/env bash\n"
        "if [[ \"$1\" == \"--list\" ]]; then\n"
        "  echo '123; 0 0 TABLE public moscow_network saferoute'\n"
        "  exit 0\n"
        "fi\n"
        "exit 0\n",
        encoding="utf-8",
    )
    pg_restore.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = f"{tmp_path}:{env['PATH']}"
    env["GRAPH_DUMP_FILE"] = str(dump)
    env["ALLOW_UNVERIFIED_GRAPH_DUMP"] = "true"
    env["SAFEROUTE_ENV"] = "production"

    result = subprocess.run(
        ["bash", str(ROOT / "scripts" / "data" / "restore-safety-graph.sh")],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "restore is blocked" in result.stderr


def test_graph_release_upload_requires_explicit_confirmation():
    script = (ROOT / "scripts" / "data" / "upload-graph-release.sh").read_text(encoding="utf-8")

    assert "CONFIRM_GRAPH_RELEASE_UPLOAD" in script
    assert "gh release create" in script
    assert "gh release upload" in script
    assert "moscow_network.dump.sha256" in script


def test_graph_release_prepare_does_not_copy_large_dump_into_staging():
    prepare_script = (ROOT / "scripts" / "data" / "prepare-graph-release.sh").read_text(encoding="utf-8")
    check_script = (ROOT / "scripts" / "data" / "check-graph-release.sh").read_text(encoding="utf-8")

    assert "check-graph-dump.sh" in prepare_script
    assert "moscow_network.dump.sha256" in prepare_script
    assert "moscow_network.dump\" ]]; then" in check_script
    assert "must not contain a copied dump" in check_script


def test_production_security_probe_does_not_print_api_key():
    script = (ROOT / "scripts" / "check-production-security.sh").read_text(encoding="utf-8")

    assert "SAFEROUTE_API_KEY" in script
    assert "Authorization: Bearer $SAFEROUTE_API_KEY" in script
    assert "echo \"$SAFEROUTE_API_KEY\"" not in script
    assert "route without key" in script
    assert "deep health without key" in script
    assert "429" in script


def test_micromobility_zone_import_is_fail_closed():
    script = (ROOT / "scripts" / "data" / "import-micromobility-zones.sh").read_text(encoding="utf-8")

    assert "MICROMOBILITY_ZONES_FILE" in script
    assert "SOURCE_OWNER" in script
    assert "SOURCE_LICENSE" in script
    assert "SOURCE_CHECKSUM mismatch" in script
    assert "tests/fixtures cannot be activated" in script
    assert "ST_Intersects(edge.geometry, zone.geom)" in script
    assert "micromobility_allowed" in script
    assert "forbidden_zone" in script
    assert "micromobility_slow_zone" in script


def test_measured_traffic_and_pedestrian_imports_are_fail_closed():
    traffic = (ROOT / "scripts" / "data" / "import-measured-traffic.sh").read_text(encoding="utf-8")
    pedestrian = (ROOT / "scripts" / "data" / "import-pedestrian-density.sh").read_text(encoding="utf-8")
    validator = (ROOT / "scripts" / "data" / "validate-measured-layer-csv.py").read_text(encoding="utf-8")
    route_corpus = (ROOT / "scripts" / "check-route-corpus.sh").read_text(encoding="utf-8")

    assert "MEASURED_TRAFFIC_FILE" in traffic
    assert "SOURCE_LICENSE_CONFIRMED=true" in traffic
    assert "test fixtures under tests/fixtures cannot be activated" in traffic
    assert "OSM road-class/maxspeed/lanes" in traffic
    assert "road-exposure proxies" in traffic
    assert "accident/crash sources" in traffic
    assert "validate-measured-layer-csv.py measured_traffic" in traffic

    assert "PEDESTRIAN_DENSITY_FILE" in pedestrian
    assert "SOURCE_LICENSE_CONFIRMED=true" in pedestrian
    assert "test fixtures under tests/fixtures cannot be activated" in pedestrian
    assert "POI/transit/land-use proxy sources" in pedestrian
    assert "validate-measured-layer-csv.py pedestrian_density" in pedestrian

    assert "TRAFFIC_BLOCKED_TOKENS" in validator
    assert "PEDESTRIAN_BLOCKED_TOKENS" in validator
    assert "requires at least one measured raw field" in validator
    assert "OSM road attributes" in validator
    assert "POI/transit proxies" in validator

    assert "avg_traffic_intensity" in route_corpus
    assert "avg_pedestrian_density" in route_corpus
    assert "avg_telemetry_confidence" in route_corpus


def test_alembic_baseline_does_not_manage_graph_table_destructively():
    migration = (ROOT / "alembic" / "versions" / "0001_app_schema_baseline.py").read_text(encoding="utf-8")

    assert "safety_edge_enrichment" in migration
    assert "sidewalk_samples" in migration
    assert "CREATE TABLE IF NOT EXISTS" in migration
    assert "moscow_network" not in migration
    assert "DROP TABLE" not in migration


def test_enrichment_csv_validator_normalizes_real_temp_csv(tmp_path):
    source = tmp_path / "real-enrichment.csv"
    normalized = tmp_path / "normalized.csv"
    source.write_text(
        "edge_id,confidence,surface_type,surface_quality,sidewalk_presence,sidewalk_width_m,lighting_quality,traffic_intensity\n"
        "42,0.85,Asphalt,Smooth,yes,2.4,Good,0.2\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "data" / "validate-enrichment-csv.py"), str(source), str(normalized)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "1"
    rows = normalized.read_text(encoding="utf-8").splitlines()
    assert rows[0].startswith("edge_id,confidence,observed_at,surface_type")
    assert "42,0.85,,asphalt,smooth,true,2.4" in rows[1]


def test_enrichment_csv_validator_accepts_advanced_real_factor_columns(tmp_path):
    source = tmp_path / "advanced-enrichment.csv"
    normalized = tmp_path / "normalized.csv"
    source.write_text(
        "edge_id,confidence,curb_density_per_km,crossing_count,controlled_crossing_count,"
        "uncontrolled_crossing_count,crossing_risk,micromobility_slow_zone,road_exposure_proxy\n"
        "42,0.91,12.5,3,2,1,0.4,false,0.7\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "data" / "validate-enrichment-csv.py"), str(source), str(normalized)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "1"
    normalized_row = normalized.read_text(encoding="utf-8").splitlines()[1]
    assert ",12.5,3,2,1,0.4," in normalized_row
    assert ",false,,0.7," in normalized_row


def test_enrichment_test_only_fixture_validates(tmp_path):
    source = ROOT / "tests" / "fixtures" / "enrichment" / "test-only-valid-enrichment.csv"
    normalized = tmp_path / "normalized.csv"

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "data" / "validate-enrichment-csv.py"), str(source), str(normalized)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "1"
    assert normalized.read_text(encoding="utf-8").splitlines()[1].startswith("42,0.85")


def test_enrichment_csv_validator_rejects_fake_unknown_values(tmp_path):
    source = tmp_path / "bad-enrichment.csv"
    normalized = tmp_path / "normalized.csv"
    source.write_text("edge_id,confidence,surface_type\n42,0.5,moon_dust\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "data" / "validate-enrichment-csv.py"), str(source), str(normalized)],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "surface_type has unsupported value" in result.stderr


def test_enrichment_csv_validator_rejects_confidence_out_of_range(tmp_path):
    source = tmp_path / "bad-enrichment.csv"
    normalized = tmp_path / "normalized.csv"
    source.write_text("edge_id,confidence,surface_type\n42,1.5,asphalt\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "data" / "validate-enrichment-csv.py"), str(source), str(normalized)],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "confidence must be <= 1" in result.stderr


def test_enrichment_import_requires_checksum_before_activation(tmp_path):
    source = tmp_path / "real-enrichment.csv"
    source.write_text("edge_id,confidence,surface_type\n42,0.8,asphalt\n", encoding="utf-8")
    env = os.environ.copy()
    env.pop("SOURCE_CHECKSUM", None)
    env.update(
        {
            "ENRICHMENT_FILE": str(source),
            "DATASET_VERSION": "test-only",
            "SOURCE_NAME": "test-only",
            "ACTIVATE_ENRICHMENT": "true",
        }
    )

    result = subprocess.run(
        ["bash", str(ROOT / "scripts" / "data" / "import-enrichment.sh")],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "SOURCE_CHECKSUM" in result.stderr


def test_enrichment_import_activation_requires_real_factor_column():
    script = (ROOT / "scripts" / "data" / "import-enrichment.sh").read_text(encoding="utf-8")

    assert "ACTIVATE_ENRICHMENT=true requires at least one real factor column populated" in script
    assert "curb_density_per_km" in script
    assert "crossing_risk" in script


def test_enrichment_import_keeps_other_active_datasets_by_default():
    script = (ROOT / "scripts" / "data" / "import-enrichment.sh").read_text(encoding="utf-8")

    assert "DEACTIVATE_OTHER_ENRICHMENT_DATASETS" in script
    assert "(:'deactivate_others')::boolean" in script
    assert "WHEN (:'activate')::boolean THEN false" not in script


def test_enrichment_import_rejects_unknown_graph_edge_ids():
    script = (ROOT / "scripts" / "data" / "import-enrichment.sh").read_text(encoding="utf-8")

    assert "public.moscow_network edge ids" in script
    assert "LEFT JOIN public.moscow_network edge" in script


def test_osm_enrichment_import_uses_direct_osm_way_mapping_only():
    builder = (ROOT / "scripts" / "data" / "build-osm-enrichment-csv.py").read_text(encoding="utf-8")
    wrapper = (ROOT / "scripts" / "data" / "import-osm-enrichment.sh").read_text(encoding="utf-8")

    assert "public.moscow_network.osmid -> OSM way id" in builder
    assert '"tags-filter"' in builder
    assert "no spatial guessing" in builder
    assert "OSM_ENRICHMENT_FACTORS" in wrapper
    assert "ACTIVATE_ENRICHMENT" in wrapper


def test_osm_advanced_enrichment_import_is_real_data_gated():
    builder = (ROOT / "scripts" / "data" / "build-osm-advanced-enrichment-csv.py").read_text(encoding="utf-8")
    wrapper = (ROOT / "scripts" / "data" / "import-osm-advanced-enrichment.sh").read_text(encoding="utf-8")

    assert "Open Database License (ODbL) 1.0; attribution required" in builder
    assert "direct public.moscow_network.osmid to OSM way id; point/node features are not guessed" in builder
    assert "curb-hybrid" in builder
    assert "node_neighborhood" in builder
    assert "crossing_assisted" in builder
    assert "max_p95_distance_m" in builder
    assert "sample_matches" in builder
    assert "accepted_features" in builder
    assert "ambiguous_rate" in builder
    assert "validation_passed" in wrapper
    assert "OSM_CURB_MAPPING_MODE:-curb-hybrid" in wrapper
    assert "not importing as active enrichment" in wrapper


def test_osm_curb_risk_requires_real_curb_signal():
    module = load_script_module(
        "build_osm_advanced_enrichment_csv",
        ROOT / "scripts" / "data" / "build-osm-advanced-enrichment-csv.py",
    )

    assert module.curb_risk_from_tags({"tactile_paving": "yes"}) is None
    assert module.curb_risk_from_tags({"wheelchair": "no"}) is None
    assert module.curb_risk_from_tags({"kerb": "raised"}) == 0.8
    assert module.curb_risk_from_tags({"kerb": "flush"}) == 0.1
    assert module.curb_risk_from_tags({"sloped_curb": "yes"}) == 0.15


def test_trust_ui_uses_beta_safe_copy_and_no_local_feedback_network():
    app = (ROOT / "src" / "App.jsx").read_text(encoding="utf-8")
    insight = (ROOT / "src" / "components" / "RouteInsight.jsx").read_text(encoding="utf-8")
    route_utils = (ROOT / "src" / "lib" / "route-utils.js").read_text(encoding="utf-8")
    e2e = (ROOT / "scripts" / "e2e-smoke.mjs").read_text(encoding="utf-8")

    assert "Индекс безопасности" not in app
    assert "не гарантия" in app
    assert "Что мы знаем" in insight
    assert "Что мы не знаем" in insight
    assert "Неизвестные риски" in insight
    assert "не влияет на маршруты" in insight
    assert "fetch(" not in insight
    assert "XMLHttpRequest" not in insight
    assert "local feedback sent a network request" in e2e

    combined_frontend = "\n".join([app, insight, route_utils])
    forbidden_claims = [
        "гарантированно безопас",
        "наиболее безопасн",
        "самый безопасн",
        "телеметрия активна",
        "измеренный трафик активен",
        "плотность пешеходов активна",
        "зоны сим активны",
    ]
    lowered = combined_frontend.lower()
    for claim in forbidden_claims:
        assert claim not in lowered

    package_json = (ROOT / "package.json").read_text(encoding="utf-8")
    trust_check = (ROOT / "scripts" / "check-trust-copy.mjs").read_text(encoding="utf-8")
    assert "check:trust-copy" in package_json
    assert "Trust-copy check failed" in trust_check


def test_release_readiness_script_checks_docs_and_fallback_guardrails():
    package_json = (ROOT / "package.json").read_text(encoding="utf-8")
    release_check = (ROOT / "scripts" / "check-release-readiness.mjs").read_text(encoding="utf-8")

    assert "check:release-readiness" in package_json
    assert "docs/RELEASE_CHECKLIST.md" in release_check
    assert "docs/PRODUCTION_READINESS_GAPS.md" in release_check
    assert "ALLOW_PUBLIC_SERVICE_FALLBACK" in release_check
    assert "request.url" in release_check
    assert "saferoute_route_requests_total" in release_check


def test_public_planner_does_not_offer_car_profile():
    config = (ROOT / "src" / "config" / "safeRoute.js").read_text(encoding="utf-8")
    e2e = (ROOT / "scripts" / "e2e-smoke.mjs").read_text(encoding="utf-8")

    profile_block = config.split("export const PROFILE_OPTIONS = [", 1)[1].split("];", 1)[0]
    scoring_block = config.split("export const SCORING_MODE_OPTIONS = [", 1)[1].split("];", 1)[0]
    assert "id: \"car\"" not in profile_block
    assert "Авто" not in profile_block
    assert "Footprints" in scoring_block
    assert "Accessibility" not in scoring_block
    assert "car profile is visible in the public planner" in e2e


def test_liquid_glass_is_limited_to_functional_controls():
    package_json = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    npmrc = (ROOT / ".npmrc").read_text(encoding="utf-8")
    shell = (ROOT / "src" / "components" / "ui" / "LiquidGlassShell.jsx").read_text(encoding="utf-8")
    app = (ROOT / "src" / "App.jsx").read_text(encoding="utf-8")
    route_controls = (ROOT / "src" / "components" / "RouteControls.jsx").read_text(encoding="utf-8")
    app_panels = (ROOT / "src" / "components" / "AppPanels.jsx").read_text(encoding="utf-8")
    route_insight = (ROOT / "src" / "components" / "RouteInsight.jsx").read_text(encoding="utf-8")
    docs = (ROOT / "docs" / "LIQUID_GLASS_UI.md").read_text(encoding="utf-8")

    assert "liquid-glass-react" in package_json["dependencies"]
    assert "legacy-peer-deps=true" in npmrc
    assert "data-liquid-native" in shell
    assert "prefers-reduced-motion" in docs
    assert "длинных блоков объяснений" in docs
    assert "LiquidGlassShell" in app
    assert "LiquidGlassShell" in route_controls
    assert "LiquidGlassShell" in app_panels
    assert "LiquidGlassShell" not in route_insight
    assert "data-liquid-glass" not in route_insight
