"use strict";

// Pure platform-to-binary resolution logic.
// No side-effects; injectable for tests.

const path = require("node:path");

/** Maps ${platform}-${arch} -> optional-dependency package name. */
const PLATFORM_MAP = {
  "darwin-arm64": "@moinulmoin/threadlens-darwin-arm64",
  "linux-x64":    "@moinulmoin/threadlens-linux-x64-gnu",
};

/**
 * Resolve the absolute path to the threadlens native binary.
 *
 * All inputs are injectable so the function is unit-testable without real
 * platform packages on disk.
 *
 * @param {object} [opts]
 * @param {string}   [opts.platform]  — defaults to process.platform
 * @param {string}   [opts.arch]      — defaults to process.arch
 * @param {object}   [opts.env]       — defaults to process.env
 * @param {Function} [opts.resolver]  — defaults to require.resolve
 * @returns {string} Absolute path to the executable.
 * @throws {Error} err.code === "UNSUPPORTED_PLATFORM" | "MISSING_PACKAGE"
 */
function resolveBinary({ platform, arch, env, resolver } = {}) {
  platform = platform !== undefined ? platform : process.platform;
  arch     = arch     !== undefined ? arch     : process.arch;
  env      = env      !== undefined ? env      : process.env;
  resolver = resolver !== undefined ? resolver : require.resolve;

  // Explicit override wins unconditionally.
  if (env.THREADLENS_BINARY) {
    return env.THREADLENS_BINARY;
  }

  const key = `${platform}-${arch}`;
  const pkg = PLATFORM_MAP[key];

  if (!pkg) {
    throw Object.assign(
      new Error(
        [
          `threadlens: unsupported platform "${key}".`,
          "",
          "Pre-built binaries are available for: darwin-arm64, linux-x64.",
          "Alternatives:",
          "  uv tool install threadlens       # installs from PyPI (brings its own Python)",
          '  uvx threadlens search "..."      # one-shot, no install',
          "  https://github.com/moinulmoin/threadlens/releases  (release archives)",
        ].join("\n")
      ),
      { code: "UNSUPPORTED_PLATFORM" }
    );
  }

  let pkgJsonPath;
  try {
    pkgJsonPath = resolver(`${pkg}/package.json`);
  } catch (_) {
    throw Object.assign(
      new Error(
        [
          `threadlens: platform package "${pkg}" is not installed.`,
          "",
          "This usually means npm was invoked with --omit=optional (or --no-optional).",
          "Fix it with one of:",
          "  npm install -g threadlens         (re-install without --omit=optional)",
          "  uv tool install threadlens         (install from PyPI instead)",
          '  uvx threadlens search "..."        (run once without installing)',
          "  https://github.com/moinulmoin/threadlens/releases  (download a release archive)",
        ].join("\n")
      ),
      { code: "MISSING_PACKAGE" }
    );
  }

  const pkgDir = path.dirname(pkgJsonPath);
  // The onedir bundle is laid out as:  <pkgDir>/bin/threadlens/threadlens
  return path.join(pkgDir, "bin", "threadlens", "threadlens");
}

module.exports = { PLATFORM_MAP, resolveBinary };
