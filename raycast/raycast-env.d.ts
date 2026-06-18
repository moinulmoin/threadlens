/// <reference types="@raycast/api">

/* 🚧 🚧 🚧
 * This file is auto-generated from the extension's manifest.
 * Do not modify manually. Instead, update the `package.json` file.
 * 🚧 🚧 🚧 */

/* eslint-disable @typescript-eslint/ban-types */

type ExtensionPreferences = {
  /** Threadlens Command - Installed Threadlens executable to run. */
  "threadlensCommand": string,
  /** Threadlens Args - Optional args before the Threadlens subcommand. */
  "threadlensArgs": string,
  /** Working Directory - Optional cwd for running Threadlens. */
  "threadlensCwd": string
}

/** Preferences accessible in all the extension's commands */
declare type Preferences = ExtensionPreferences

declare namespace Preferences {
  /** Preferences accessible in the `search-threadlens` command */
  export type SearchThreadlens = ExtensionPreferences & {}
}

declare namespace Arguments {
  /** Arguments passed to the `search-threadlens` command */
  export type SearchThreadlens = {}
}

