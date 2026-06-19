// Unit tests for the platform->binary resolution logic.
// No real platform packages are required; all I/O is injected.
//
// Run: node --test npm/test/shim.test.mjs

import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here    = dirname(fileURLToPath(import.meta.url));
const npmRoot = join(here, "..");

const require = createRequire(import.meta.url);
const { PLATFORM_MAP, resolveBinary } = require(join(npmRoot, "bin", "resolve.js"));

// ── PLATFORM_MAP shape ────────────────────────────────────────────────────────

test("PLATFORM_MAP contains exactly the 2 supported combos", () => {
  assert.deepEqual(Object.keys(PLATFORM_MAP).sort(), [
    "darwin-arm64",
    "linux-x64",
  ]);
});

test("PLATFORM_MAP values are scoped @moinulmoin packages", () => {
  for (const pkg of Object.values(PLATFORM_MAP)) {
    assert.ok(pkg.startsWith("@moinulmoin/threadlens-"), `bad package name: ${pkg}`);
  }
});

// ── resolveBinary — 3 supported platforms ─────────────────────────────────────

/** Returns a fake resolver that answers <pkg>/package.json → <fakeRoot>/package.json */
function fakeResolver(expectedPkg, fakeRoot) {
  return (id) => {
    if (id === `${expectedPkg}/package.json`) {
      return join(fakeRoot, "package.json");
    }
    const err = new Error(`Cannot find module '${id}'`);
    err.code = "MODULE_NOT_FOUND";
    throw err;
  };
}

// darwin-arm64
test("resolveBinary darwin-arm64 returns correct binary path", () => {
  const pkg      = "@moinulmoin/threadlens-darwin-arm64";
  const fakeRoot = `/fake/node_modules/${pkg}`;

  const resolved = resolveBinary({
    platform: "darwin",
    arch:     "arm64",
    env:      {},
    resolver: fakeResolver(pkg, fakeRoot),
  });

  assert.equal(resolved, join(fakeRoot, "bin", "threadlens", "threadlens"));
});

// darwin-x64 (Intel) is not a prebuilt target -> unsupported (use uvx/PyPI)
test("resolveBinary throws UNSUPPORTED_PLATFORM for darwin-x64", () => {
  assert.throws(
    () => resolveBinary({ platform: "darwin", arch: "x64", env: {}, resolver: () => "" }),
    (err) => err.code === "UNSUPPORTED_PLATFORM",
  );
});

// linux-x64 → maps to linux-x64-gnu package
test("resolveBinary linux-x64 returns correct binary path (gnu package)", () => {
  const pkg      = "@moinulmoin/threadlens-linux-x64-gnu";
  const fakeRoot = `/fake/node_modules/${pkg}`;

  const resolved = resolveBinary({
    platform: "linux",
    arch:     "x64",
    env:      {},
    resolver: fakeResolver(pkg, fakeRoot),
  });

  assert.equal(resolved, join(fakeRoot, "bin", "threadlens", "threadlens"));
});

// ── Unsupported platform → hard error ────────────────────────────────────────

test("resolveBinary throws UNSUPPORTED_PLATFORM for win32-x64", () => {
  assert.throws(
    () =>
      resolveBinary({
        platform: "win32",
        arch:     "x64",
        env:      {},
        resolver: () => { throw new Error("should not be called"); },
      }),
    (err) => {
      assert.equal(err.code, "UNSUPPORTED_PLATFORM", "wrong error code");
      assert.ok(
        err.message.includes('unsupported platform "win32-x64"'),
        `unexpected message: ${err.message}`
      );
      return true;
    }
  );
});

test("resolveBinary throws UNSUPPORTED_PLATFORM for linux-arm64", () => {
  assert.throws(
    () =>
      resolveBinary({
        platform: "linux",
        arch:     "arm64",
        env:      {},
        resolver: () => { throw new Error("should not be called"); },
      }),
    (err) => {
      assert.equal(err.code, "UNSUPPORTED_PLATFORM");
      return true;
    }
  );
});

// ── Missing package (--omit=optional) ────────────────────────────────────────

test("resolveBinary throws MISSING_PACKAGE when optional dep is absent", () => {
  assert.throws(
    () =>
      resolveBinary({
        platform: "darwin",
        arch:     "arm64",
        env:      {},
        resolver: () => {
          const err = new Error("Cannot find module");
          err.code = "MODULE_NOT_FOUND";
          throw err;
        },
      }),
    (err) => {
      assert.equal(err.code, "MISSING_PACKAGE", "wrong error code");
      assert.ok(
        err.message.includes("not installed"),
        `expected 'not installed' in: ${err.message}`
      );
      assert.ok(
        err.message.includes("--omit=optional"),
        `expected '--omit=optional' hint in: ${err.message}`
      );
      return true;
    }
  );
});

// ── THREADLENS_BINARY override ────────────────────────────────────────────────

test("THREADLENS_BINARY env override is returned verbatim", () => {
  const customBin = "/opt/custom/threadlens";
  const resolved  = resolveBinary({
    platform: "win32",   // would normally throw UNSUPPORTED_PLATFORM
    arch:     "arm64",
    env:      { THREADLENS_BINARY: customBin },
    resolver: () => { throw new Error("resolver must not be called with override set"); },
  });
  assert.equal(resolved, customBin);
});

test("THREADLENS_BINARY override beats a valid supported platform", () => {
  const customBin = "/special/threadlens";
  const resolved  = resolveBinary({
    platform: "darwin",
    arch:     "arm64",
    env:      { THREADLENS_BINARY: customBin },
    // resolver should never be invoked
    resolver: () => { throw new Error("resolver must not be called with override set"); },
  });
  assert.equal(resolved, customBin);
});
