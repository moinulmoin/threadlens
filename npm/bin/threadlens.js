#!/usr/bin/env node
"use strict";

// Thin launcher — resolves the pre-built native binary for this platform
// and exec's it, passing all arguments through verbatim.
//
// Set THREADLENS_BINARY=/path/to/binary to override the auto-resolved path.

const { spawnSync } = require("node:child_process");
const { resolveBinary } = require("./resolve.js");

let bin;
try {
  bin = resolveBinary();
} catch (err) {
  process.stderr.write(err.message + "\n");
  process.exit(127);
}

const result = spawnSync(bin, process.argv.slice(2), { stdio: "inherit" });

if (result.error) {
  process.stderr.write(
    `threadlens: failed to launch binary (${bin}): ${result.error.message}\n`
  );
  process.exit(1);
}

process.exit(result.status === null ? 1 : result.status);
