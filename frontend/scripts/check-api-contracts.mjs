import { spawnSync } from "node:child_process";
import process from "node:process";
import { isDeepStrictEqual } from "node:util";

const pythonExecutable = process.env.DMARC_CONTRACT_PYTHON ?? "../.venv/bin/python";
const exportScript = new URL("./export_openapi_contracts.py", import.meta.url);

const pythonResult = spawnSync(pythonExecutable, [exportScript.pathname], {
  cwd: process.cwd(),
  encoding: "utf8",
});

if (pythonResult.status !== 0) {
  process.stderr.write(pythonResult.stderr || pythonResult.stdout || "Contract fixture export failed.\n");
  process.exit(pythonResult.status ?? 1);
}

const contractPayload = JSON.parse(pythonResult.stdout);

const expectedComponents = [
  "AuthLoginResponse",
  "AuthMeResponse",
  "CreateApiKeyBody",
  "CreateDashboardBody",
  "CreateUserBody",
  "DashboardSummary",
  "DashboardsListResponse",
  "DomainsListResponse",
  "IngestEnvelope",
  "LoginBody",
  "SearchRequest",
];

const expectedContracts = {
  auth_login_request: { $ref: "#/components/schemas/LoginBody" },
  auth_login_response: { $ref: "#/components/schemas/AuthLoginResponse" },
  auth_me_response: { $ref: "#/components/schemas/AuthMeResponse" },
  domains_list_response: { $ref: "#/components/schemas/DomainsListResponse" },
  dashboards_list_response: { $ref: "#/components/schemas/DashboardsListResponse" },
  dashboards_create_request: { $ref: "#/components/schemas/CreateDashboardBody" },
  dashboards_create_response: { $ref: "#/components/schemas/DashboardSummary" },
  dashboard_detail_response: { additionalProperties: true, title: "Response Get Dashboard Api V1 Dashboards  Dashboard Id  Get", type: "object" },
  search_request: { $ref: "#/components/schemas/SearchRequest" },
  search_response: { additionalProperties: true, title: "Response Post Search Api V1 Search Post", type: "object" },
  forensic_list_response: { additionalProperties: true, title: "Response Get Reports Forensic Api V1 Reports Forensic Get", type: "object" },
  users_list_response: { additionalProperties: true, title: "Response List Users Api V1 Users Get", type: "object" },
  users_create_request: { $ref: "#/components/schemas/CreateUserBody" },
  users_create_response: { additionalProperties: true, title: "Response Create User Api V1 Users Post", type: "object" },
  apikeys_list_response: { additionalProperties: true, title: "Response List Apikeys Api V1 Apikeys Get", type: "object" },
  apikeys_create_request: { $ref: "#/components/schemas/CreateApiKeyBody" },
  apikeys_create_response: { additionalProperties: true, title: "Response Create Apikey Api V1 Apikeys Post", type: "object" },
  audit_list_response: { additionalProperties: true, title: "Response Get Audit Api V1 Audit Get", type: "object" },
  reports_ingest_request: { $ref: "#/components/schemas/IngestEnvelope" },
  reports_ingest_response: { additionalProperties: true, title: "Response Post Reports Ingest Api V1 Reports Ingest Post", type: "object" },
};

const failures = [];

for (const name of expectedComponents) {
  if (!contractPayload.components.includes(name)) {
    failures.push(`Missing OpenAPI component schema: ${name}`);
  }
}

for (const [name, expected] of Object.entries(expectedContracts)) {
  const actual = contractPayload.contracts[name];
  if (!isDeepStrictEqual(actual, expected)) {
    failures.push(`OpenAPI contract mismatch for ${name}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  }
}

if (failures.length > 0) {
  process.stderr.write(`${failures.join("\n")}\n`);
  process.exit(1);
}

process.stdout.write("Frontend API OpenAPI contracts verified against FastAPI.\n");
