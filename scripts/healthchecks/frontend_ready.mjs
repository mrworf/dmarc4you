#!/usr/bin/env node

const port = process.env.PORT ?? "3000";

const response = await fetch(`http://127.0.0.1:${port}/api/ready`, {
  cache: "no-store",
}).catch(() => null);

process.exit(response?.ok ? 0 : 1);
