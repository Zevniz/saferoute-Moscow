import { readFileSync } from "node:fs";

const checks = [
  {
    file: "src/App.jsx",
    pattern: /fetch\(["'`][^"'`]*nominatim/i,
    message: "Browser runtime must not call public Nominatim directly.",
    expect: false,
  },
  {
    file: "app/services/routing.py",
    pattern: /Следуйте по маршруту/,
    message: "Live backend must not synthesize fake navigation instructions.",
    expect: false,
  },
  {
    file: "docker-compose.yml",
    pattern: /ALLOW_PUBLIC_SERVICE_FALLBACK:\s*["']?true/i,
    message: "Production compose must keep public fallback disabled.",
    expect: false,
  },
  {
    file: "app/api/routes.py",
    pattern: /\/api\/metrics/,
    message: "Metrics endpoint must stay exposed for Platform Core observability.",
    expect: true,
  },
  {
    file: "package.json",
    pattern: /"smoke:self-hosted"\s*:/,
    message: "Self-hosted smoke script must stay available from package.json.",
    expect: true,
  },
  {
    file: "package.json",
    pattern: /"bootstrap:self-hosted"\s*:/,
    message: "Self-hosted bootstrap script must stay available from package.json.",
    expect: true,
  },
  {
    file: "docker-compose.yml",
    pattern: /npm run dev|--reload/,
    message: "Base compose must stay production-like; dev server and reload belong in docker-compose.dev.yml only.",
    expect: false,
  },
  {
    file: "docker-compose.yml",
    pattern: /file:\/\/\/custom_files\/osm\/moscow-oblast\.osm\.pbf/,
    message: "Base compose Valhalla must point at the repo-local Moscow+Oblast extract.",
    expect: true,
  },
];

let failed = false;
for (const check of checks) {
  const text = readFileSync(check.file, "utf8");
  const matched = check.pattern.test(text);
  if (matched !== check.expect) {
    failed = true;
    console.error(`lint failed: ${check.file}: ${check.message}`);
  }
}

if (failed) {
  process.exit(1);
}

console.log("SafeRoute project lint passed");
