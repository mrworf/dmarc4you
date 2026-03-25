import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const appDir = path.resolve(__dirname, "..", "app");

const requiredRoutes = [
  { route: "/login", file: "login/page.tsx" },
  { route: "/domains", file: "domains/page.tsx" },
  { route: "/dashboards", file: "dashboards/page.tsx" },
  { route: "/dashboards/[id]", file: "dashboards/[id]/page.tsx" },
  { route: "/search", file: "search/page.tsx" },
  { route: "/upload", file: "upload/page.tsx" },
  { route: "/ingest-jobs", file: "ingest-jobs/page.tsx" },
  { route: "/ingest-jobs/[id]", file: "ingest-jobs/[id]/page.tsx" },
  { route: "/users", file: "users/page.tsx" },
  { route: "/apikeys", file: "apikeys/page.tsx" },
  { route: "/audit", file: "audit/page.tsx" },
  { route: "/api/ready", file: "api/ready/route.ts" },
];

const missing = requiredRoutes.filter(({ file }) => !existsSync(path.join(appDir, file)));

if (missing.length > 0) {
  console.error("Missing migrated cutover routes:");
  for (const entry of missing) {
    console.error(`- ${entry.route} -> app/${entry.file}`);
  }
  process.exit(1);
}

console.log(`Verified ${requiredRoutes.length} migrated cutover routes in frontend/app.`);
