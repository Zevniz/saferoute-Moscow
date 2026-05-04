#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";

const ROOT = process.cwd();

function read(relativePath) {
  return fs.readFileSync(path.join(ROOT, relativePath), "utf8");
}

function exists(relativePath) {
  return fs.existsSync(path.join(ROOT, relativePath));
}

const failures = [];
const requiredDocs = [
  "docs/PUBLIC_BETA_READINESS.md",
  "docs/PRIVACY_AND_TELEMETRY.md",
  "docs/TRUST_ARCHITECTURE.md",
  "docs/EXPLAINABILITY_MODEL.md",
  "docs/BETA_SAFETY_LIMITS.md",
  "docs/SCORING_GOVERNANCE.md",
  "docs/DATA_FRESHNESS_POLICY.md",
  "docs/INCIDENT_RESPONSE.md",
  "docs/RELEASE_CHECKLIST.md",
  "docs/PRODUCTION_READINESS_GAPS.md",
  "docs/OBSERVABILITY.md",
  "docs/SECURITY_REVIEW.md",
];

for (const doc of requiredDocs) {
  if (!exists(doc)) {
    failures.push(`${doc} is missing`);
    continue;
  }
  if (read(doc).trim().length < 200) {
    failures.push(`${doc} is too small to be useful`);
  }
}

const packageJson = JSON.parse(read("package.json"));
for (const scriptName of ["check:trust-copy", "check:release-readiness", "smoke:self-hosted", "route:corpus-check"]) {
  if (!packageJson.scripts?.[scriptName]) {
    failures.push(`package.json missing script ${scriptName}`);
  }
}

const compose = read("docker-compose.yml");
if (/ALLOW_PUBLIC_SERVICE_FALLBACK\s*[:=]\s*["']?true/i.test(compose)) {
  failures.push("base docker-compose.yml must not enable public service fallback");
}

const observability = read("app/core/observability.py");
if (observability.includes("request.url") && !observability.includes("request.url.path")) {
  failures.push("request logging must not log full URLs with coordinates/query strings");
}

const apiRoutes = read("app/api/routes.py");
if (!apiRoutes.includes("saferoute_route_requests_total")) {
  failures.push("route API operational metric is missing");
}

if (failures.length > 0) {
  console.error("Release-readiness check failed:");
  for (const failure of failures) {
    console.error(`- ${failure}`);
  }
  process.exit(1);
}

console.log("Release-readiness check passed: docs, fallback guardrails, and operational checks are present.");
