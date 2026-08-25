#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");

const PUBLIC_PADDLE_KEYS = new Set([
  "NEXT_PUBLIC_PADDLE_CLIENT_TOKEN",
  "NEXT_PUBLIC_PADDLE_PRICE_BRAND_SOLO_MONTHLY",
  "NEXT_PUBLIC_PADDLE_PRICE_BRAND_SOLO_YEARLY",
  "NEXT_PUBLIC_PADDLE_PRICE_STARTER_AGENCY_MONTHLY",
  "NEXT_PUBLIC_PADDLE_PRICE_STARTER_AGENCY_YEARLY",
  "NEXT_PUBLIC_PADDLE_PRICE_PRO_AGENCY_MONTHLY",
  "NEXT_PUBLIC_PADDLE_PRICE_PRO_AGENCY_YEARLY",
  "NEXT_PUBLIC_PADDLE_PRICE_AGENCY_PLUS_MONTHLY",
  "NEXT_PUBLIC_PADDLE_PRICE_AGENCY_PLUS_YEARLY",
]);

function parsePublicPaddleEnv(filePath) {
  const values = {};
  for (const rawLine of fs.readFileSync(filePath, "utf8").split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;

    const match = line.match(/^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$/);
    if (!match || !PUBLIC_PADDLE_KEYS.has(match[1])) continue;

    let value = match[2].trim();
    if (
      value.length >= 2 &&
      ((value.startsWith('"') && value.endsWith('"')) ||
        (value.startsWith("'") && value.endsWith("'")))
    ) {
      value = value.slice(1, -1);
    }
    if (value) values[match[1]] = value;
  }
  return values;
}

const frontendDir = path.resolve(__dirname, "..");
const explicitEnvFile = process.env.PADDLE_ENV_FILE;
const candidates = explicitEnvFile
  ? [path.resolve(frontendDir, explicitEnvFile)]
  : [
      path.join(frontendDir, ".env.paddle"),
      path.resolve(frontendDir, "..", "..", ".env.paddle"),
    ];
const paddleEnvFile = candidates.find((candidate) => fs.existsSync(candidate));

if (explicitEnvFile && !paddleEnvFile) {
  console.error("Configured PADDLE_ENV_FILE does not exist.");
  process.exit(1);
}

if (paddleEnvFile) {
  const values = parsePublicPaddleEnv(paddleEnvFile);
  for (const [key, value] of Object.entries(values)) {
    if (!process.env[key]) process.env[key] = value;
  }
  console.log(`[paddle-env] Loaded ${Object.keys(values).length}/9 public values from ignored env.`);
}

const nextArgs = process.argv.slice(2);
if (nextArgs.length === 0) {
  console.error("Usage: node scripts/run-next-with-paddle-env.js <dev|build|start> [args]");
  process.exit(1);
}

const nextBin = path.join(frontendDir, "node_modules", "next", "dist", "bin", "next");
const result = spawnSync(process.execPath, [nextBin, ...nextArgs], {
  cwd: frontendDir,
  env: process.env,
  stdio: "inherit",
});

if (result.error) {
  console.error(`[paddle-env] Next.js failed to start: ${result.error.message}`);
  process.exit(1);
}

process.exit(result.status ?? 1);
