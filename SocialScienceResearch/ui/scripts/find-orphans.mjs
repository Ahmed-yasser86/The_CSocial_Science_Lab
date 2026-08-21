/**
 * Scans services modules for exported functions/hooks that are never used
 * elsewhere in src/. Used by the contract gate to prevent frontend/backend drift.
 *
 * Run: node scripts/find-orphans.mjs
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join, resolve } from "node:path";

const SRC = resolve(import.meta.dirname, "..", "src");
const SERVICES = ["services/api.ts", "services/queries.ts"];

function listFiles(dir, out = []) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      listFiles(full, out);
    } else if (/\.(ts|tsx)$/.test(entry) && !entry.endsWith(".test.ts")) {
      out.push(full);
    }
  }
  return out;
}

function exportedNames(source) {
  const names = new Set();
  const re =
    /export\s+(?:async\s+)?function\s+([A-Za-z_$][\w$]*)|export\s+(?:function\s+)?([A-Za-z_$][\w$]*)/g;
  let m;
  while ((m = re.exec(source)) !== null) {
    if (m[1]) names.add(m[1]);
    if (m[2]) names.add(m[2]);
  }
  return names;
}

export function findOrphans() {
  const files = listFiles(SRC).map((f) => resolve(f));
  const serviceFiles = SERVICES.map((f) => resolve(SRC, f));
  const serviceSources = new Map(
    serviceFiles.map((f) => [f, readFileSync(f, "utf8")]),
  );

  const orphans = [];
  for (const [file, source] of serviceSources) {
    const rel = file.replace(SRC + "\\", "").replace(SRC + "/", "");
    for (const name of exportedNames(source)) {
      let used = false;
      for (const f of files) {
        if (f === file) continue;                    // ignore the file itself
        if (f.endsWith(".test.ts") || f.includes("generated-api")) continue;
        if (readFileSync(f, "utf8").includes(name)) {
          used = true;
          break;
        }
      }
      if (!used) orphans.push(`${rel}:${name}`);
    }
  }
  return orphans;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const orphans = findOrphans();
  if (orphans.length) {
    console.log("Orphans:\n" + orphans.map((o) => "  " + o).join("\n"));
    process.exit(1);
  }
  console.log("No orphans.");
}