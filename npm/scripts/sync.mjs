// Generates the 3 platform-package scaffolds under npm/platforms/ and syncs
// the main npm/package.json version + optionalDependency pins from
// threadlens/__init__.py.
//
// Idempotent — safe to run repeatedly. CI drops the onedir bundle into each
// platform package's bin/threadlens/ directory before publishing.
//
// Run: node scripts/sync.mjs

import { mkdirSync, readFileSync, writeFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here    = dirname(fileURLToPath(import.meta.url));
const npmRoot = join(here, "..");
const repoRoot = join(npmRoot, "..");

// ── Read canonical version ────────────────────────────────────────────────────

const initPy  = readFileSync(join(repoRoot, "threadlens", "__init__.py"), "utf8");
const verMatch = initPy.match(/__version__\s*=\s*["']([^"']+)["']/);
if (!verMatch) {
  throw new Error("could not find __version__ in threadlens/__init__.py");
}
const version = verMatch[1];

// ── Platform package definitions ──────────────────────────────────────────────

const PLATFORMS = [
  {
    name:     "@moinulmoin/threadlens-darwin-arm64",
    basename: "threadlens-darwin-arm64",
    os:       ["darwin"],
    cpu:      ["arm64"],
  },
  {
    name:     "@moinulmoin/threadlens-linux-x64-gnu",
    basename: "threadlens-linux-x64-gnu",
    os:       ["linux"],
    cpu:      ["x64"],
    libc:     ["glibc"],
  },
];

const platformsDir = join(npmRoot, "platforms");

// ── Generate / update each platform package ───────────────────────────────────

for (const plat of PLATFORMS) {
  const pkgDir = join(platformsDir, plat.basename);
  const binDir = join(pkgDir, "bin");

  mkdirSync(binDir, { recursive: true });

  // package.json — rebuild every run so version stays in sync.
  const pkgJson = {
    name:        plat.name,
    version,
    description: `Pre-built threadlens binary for ${plat.basename}`,
    os:          plat.os,
    cpu:         plat.cpu,
    // libc field only for linux packages (npm 8.7+ / node 18+ honors it)
    ...(plat.libc ? { libc: plat.libc } : {}),
    files:       ["bin"],
    license:     "MIT",
    repository:  {
      type: "git",
      url:  "git+https://github.com/moinulmoin/threadlens.git",
    },
  };
  writeFileSync(
    join(pkgDir, "package.json"),
    JSON.stringify(pkgJson, null, 2) + "\n"
  );

  // bin/.gitkeep — placeholder so git tracks the bin/ directory.
  // CI replaces this with the real onedir bundle (bin/threadlens/).
  const gitkeep = join(binDir, ".gitkeep");
  if (!existsSync(gitkeep)) {
    writeFileSync(gitkeep, "");
  }

  console.log(`  ✓ platforms/${plat.basename}/package.json  (${version})`);
}

// ── Sync main package.json ────────────────────────────────────────────────────

const mainPkgPath = join(npmRoot, "package.json");
const mainPkg     = JSON.parse(readFileSync(mainPkgPath, "utf8"));

mainPkg.version = version;
mainPkg.optionalDependencies = Object.fromEntries(
  PLATFORMS.map((p) => [p.name, version])
);

writeFileSync(mainPkgPath, JSON.stringify(mainPkg, null, 2) + "\n");

console.log(`\nsynced threadlens ${version} → npm/package.json + npm/platforms/`);
