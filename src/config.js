import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import readline from "node:readline/promises";

export function configDir() {
  const xdg = process.env.XDG_CONFIG_HOME;
  const base = xdg ? xdg : path.join(os.homedir(), ".config");
  const d = path.join(base, "exa-cli");
  fs.mkdirSync(d, { recursive: true });
  return d;
}

export function configPath() {
  return path.join(configDir(), "config.toml");
}

export function loadKey() {
  const envKey = process.env.EXA_API_KEY ? process.env.EXA_API_KEY.trim() : "";
  if (envKey) return envKey;

  const p = configPath();
  if (fs.existsSync(p)) {
    try {
      const content = fs.readFileSync(p, "utf-8");
      for (const line of content.split("\n")) {
        const s = line.trim();
        if (s.startsWith("api_key")) {
          const parts = s.split("=");
          if (parts.length >= 2) {
            const v = parts.slice(1).join("=").trim().replace(/^["']|["']$/g, "");
            if (v) return v;
          }
        }
      }
    } catch {
      // ignore read error
    }
  }
  return null;
}

export function saveKey(key) {
  const p = configPath();
  fs.writeFileSync(p, `api_key = "${key}"\n`, { mode: 0o600, flag: "w" });
  return p;
}

export function mask(key) {
  if (!key || key.length <= 4) return "****";
  return `${key.slice(0, 3)}…${key.slice(-4)}`;
}

export async function ensureKey() {
  const k = loadKey();
  if (k) return k;

  console.error("No EXA_API_KEY found.");
  console.error("Get a key at https://dashboard.exa.ai/api-keys");

  if (!process.stdin.isTTY) {
    console.error("error: empty key, aborting");
    process.exit(3);
  }

  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stderr,
  });

  const answer = await rl.question("Paste your Exa API key: ");
  rl.close();
  const key = answer.trim();

  if (!key) {
    console.error("error: empty key, aborting");
    process.exit(3);
  }

  saveKey(key);
  console.error(`Saved to ${configPath()} (mode 0600)`);
  return key;
}
