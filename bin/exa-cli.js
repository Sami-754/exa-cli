#!/usr/bin/env node

import { runCLI } from "../src/cli.js";

runCLI()
  .then((code) => {
    process.exit(code ?? 0);
  })
  .catch((err) => {
    console.error(err);
    process.exit(1);
  });
