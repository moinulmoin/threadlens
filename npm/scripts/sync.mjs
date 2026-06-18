// Vendors the Python source into ./vendor and syncs the npm version from
// threadlens/__init__.py. Runs automatically on `npm pack` / `npm publish`
// via the package.json "prepack" hook.

import { cpSync, rmSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const npmRoot = join(here, "..");
const repoRoot = join(npmRoot, "..");

const srcPkg = join(repoRoot, "threadlens");
const vendorDir = join(npmRoot, "vendor");
const destPkg = join(vendorDir, "threadlens");

// Fresh copy of the Python package, minus compiled artifacts.
rmSync(vendorDir, { recursive: true, force: true });
cpSync(srcPkg, destPkg, {
  recursive: true,
  filter: (src) => !src.includes("__pycache__") && !src.endsWith(".pyc"),
});

// Keep the npm version identical to the Python package version.
const initPy = readFileSync(join(srcPkg, "__init__.py"), "utf8");
const match = initPy.match(/__version__\s*=\s*["']([^"']+)["']/);
if (!match) {
  throw new Error("could not find __version__ in threadlens/__init__.py");
}
const version = match[1];

const pkgPath = join(npmRoot, "package.json");
const pkg = JSON.parse(readFileSync(pkgPath, "utf8"));
pkg.version = version;
writeFileSync(pkgPath, JSON.stringify(pkg, null, 2) + "\n");

console.log(`synced threadlens ${version} -> vendor/`);
