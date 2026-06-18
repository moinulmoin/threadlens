#!/usr/bin/env node
"use strict";

// Thin launcher for the threadlens Python CLI.
//
// The real tool is pure-Python (stdlib only). This npm package vendors that
// source under ./vendor and runs it with the user's own Python interpreter, so
// `threadlens skill` keeps returning a real, copyable on-disk path (a zipapp
// would hide those files inside an archive).

const { spawnSync } = require("node:child_process");
const path = require("node:path");

// vendor/ contains the importable `threadlens` package directory.
const vendorDir = path.join(__dirname, "..", "vendor");

function isPython310(cmd) {
  const probe =
    "import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 10) else 1)";
  const res = spawnSync(cmd, ["-c", probe], { stdio: "ignore" });
  return res.status === 0;
}

function pickPython() {
  const override = process.env.THREADLENS_PYTHON;
  const candidates = override ? [override] : ["python3", "python"];
  for (const cmd of candidates) {
    try {
      if (isPython310(cmd)) return cmd;
    } catch (_) {
      // not found / not executable; try the next candidate
    }
  }
  return null;
}

const python = pickPython();

if (!python) {
  process.stderr.write(
    [
      "threadlens: could not find Python 3.10+ on your PATH.",
      "",
      "threadlens is a Python CLI; this npm package is a thin launcher.",
      "Fix it with either:",
      "",
      "  • Install Python 3.10+  (https://www.python.org/downloads or `brew install python`)",
      "  • Or install the native build with uv (it can fetch Python for you):",
      "      uv tool install threadlens     # then run `threadlens`",
      '      uvx threadlens search "..."    # run without installing',
      "",
      "Already have a specific interpreter? Point at it:",
      "      THREADLENS_PYTHON=/path/to/python threadlens ...",
      "",
    ].join("\n")
  );
  process.exit(127);
}

const env = { ...process.env, PYTHONDONTWRITEBYTECODE: "1" };
env.PYTHONPATH = env.PYTHONPATH
  ? vendorDir + path.delimiter + env.PYTHONPATH
  : vendorDir;

const res = spawnSync(python, ["-m", "threadlens", ...process.argv.slice(2)], {
  stdio: "inherit",
  env,
});

if (res.error) {
  process.stderr.write(`threadlens: failed to launch Python: ${res.error.message}\n`);
  process.exit(1);
}

process.exit(res.status === null ? 1 : res.status);
