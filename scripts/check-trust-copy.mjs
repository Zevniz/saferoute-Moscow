#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";

const ROOT = process.cwd();
const SCAN_DIRS = ["src", "app"];

const FORBIDDEN_PATTERNS = [
  {
    pattern: /гарантированно\s+безопас/iu,
    reason: "Absolute safety guarantee is not allowed in public-beta UI/API copy.",
  },
  {
    pattern: /сам(ый|ая|ое|ые)\s+безопасн/iu,
    reason: "Do not present a route as absolutely safest; qualify it by available data.",
  },
  {
    pattern: /наиболее\s+безопасн/iu,
    reason: "Use qualified wording such as 'с более высокой оценкой'.",
  },
  {
    pattern: /проверенн(ый|ая|ое|ые)\s+безопасн/iu,
    reason: "SafeRoute does not verify absolute route safety.",
  },
  {
    pattern: /можно\s+доверять\s+полностью/iu,
    reason: "Data confidence is not a full trust guarantee.",
  },
  {
    pattern: /данные\s+точн(ые|ы)/iu,
    reason: "Data can be incomplete or stale; avoid absolute precision claims.",
  },
  {
    pattern: /ai\s+знает|ии\s+знает/iu,
    reason: "No AI safety facts may be invented or implied.",
  },
  {
    pattern: /телеметрия\s+активна/iu,
    reason: "Telemetry confidence is inactive while real telemetry rows are absent.",
  },
  {
    pattern: /измеренн(ый|ая|ое|ые)\s+трафик\s+актив/iu,
    reason: "Measured traffic is inactive without a licensed measured source.",
  },
];

const allowedExtensions = new Set([".js", ".jsx", ".ts", ".tsx", ".py"]);

function walk(dir) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (["__pycache__", "node_modules", "dist"].includes(entry.name)) {
        continue;
      }
      files.push(...walk(fullPath));
      continue;
    }
    if (entry.isFile() && allowedExtensions.has(path.extname(entry.name))) {
      files.push(fullPath);
    }
  }
  return files;
}

const failures = [];
for (const scanDir of SCAN_DIRS) {
  const absoluteDir = path.join(ROOT, scanDir);
  if (!fs.existsSync(absoluteDir)) {
    continue;
  }
  for (const file of walk(absoluteDir)) {
    const content = fs.readFileSync(file, "utf8");
    const lowered = content.toLowerCase();
    for (const { pattern, reason } of FORBIDDEN_PATTERNS) {
      if (pattern.test(lowered)) {
        failures.push(`${path.relative(ROOT, file)}: ${reason}`);
      }
    }
  }
}

if (failures.length > 0) {
  console.error("Trust-copy check failed:");
  for (const failure of failures) {
    console.error(`- ${failure}`);
  }
  process.exit(1);
}

console.log("Trust-copy check passed: no misleading public safety claims found.");
