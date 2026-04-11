#!/usr/bin/env node

const response = await fetch("http://127.0.0.1:3000/api/ready", {
  cache: "no-store",
}).catch(() => null);

process.exit(response?.ok ? 0 : 1);
