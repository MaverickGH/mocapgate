// Stage only a verified native package; original modules are never Tauri resources.
import { spawnSync } from "node:child_process";
import { cpSync, existsSync, mkdirSync, rmSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../../..");
const stage = path.join(root, "apps/studio/desktop/runtime/package");
const source = process.env.MOCAPGATE_NATIVE_PACKAGE;
if (!source || path.resolve(source) === stage || !existsSync(path.join(source, "native-manifest.json"))) {
  throw new Error("Set MOCAPGATE_NATIVE_PACKAGE to a separately built, tested native package for this target.");
}
const python = path.join(source, process.platform === "win32" ? "python/python.exe" : "python/bin/python3.12");
const result = spawnSync(python, ["-B", path.join(root, "scripts/native_packaging.py"), "check", path.resolve(source)], { stdio: "inherit" });
if (result.status !== 0) throw new Error("Native package validation failed");
rmSync(stage, { recursive: true, force: true });
mkdirSync(path.dirname(stage), { recursive: true });
cpSync(path.resolve(source), stage, { recursive: true });
