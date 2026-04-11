# GeoIP Setup

DMARCWatch can enrich report records with country data during ingest using a local MMDB file. GeoIP is optional and fully offline once you have the database file.

## Supported providers

- `dbip-lite-country`
- `maxmind-geolite2-country`

The application does not download or update these databases for you.

## Recommended local layout

Store MMDB files under `data/` for local non-Docker runs.

For Docker Compose deployments, store MMDB files under `data/geoip/` by default. The compose stack mounts `${DMARC_GEOIP_BIND_PATH:-./data/geoip}` into the backend container at `/app/geoip`.

Examples:

- `data/dbip-country-lite.mmdb`
- `data/GeoLite2-Country.mmdb`
- `data/geoip/dbip-country-lite.mmdb`
- `data/geoip/GeoLite2-Country.mmdb`

## Configuration

Example using DB-IP Lite:

```yaml
geoip:
  provider: dbip-lite-country
  database_path: data/dbip-country-lite.mmdb
```

Example using MaxMind GeoLite2 Country:

```yaml
geoip:
  provider: maxmind-geolite2-country
  database_path: data/GeoLite2-Country.mmdb
```

Set `provider: none` to disable GeoIP enrichment.

## Docker Compose configuration

When the backend runs in Docker, `geoip.database_path` must point to the path inside the container, not the host path.

1. Copy your MMDB file into the host GeoIP directory, usually `data/geoip/`.
2. Set the GeoIP environment variables in `compose.env`.
3. Restart the backend container.

Example `compose.env` settings using DB-IP Lite:

```env
DMARC_GEOIP_PROVIDER=dbip-lite-country
DMARC_GEOIP_DATABASE_PATH=/app/geoip/dbip-country-lite.mmdb
DMARC_GEOIP_BIND_PATH=./data/geoip
```

Example `compose.env` settings using MaxMind GeoLite2 Country:

```env
DMARC_GEOIP_PROVIDER=maxmind-geolite2-country
DMARC_GEOIP_DATABASE_PATH=/app/geoip/GeoLite2-Country.mmdb
DMARC_GEOIP_BIND_PATH=./data/geoip
```

If you want to keep the MMDB somewhere else on the host, change `DMARC_GEOIP_BIND_PATH` to that directory and keep `DMARC_GEOIP_DATABASE_PATH` pointed at the matching `/app/geoip/...` file inside the container.

Quick start example:

```bash
mkdir -p data/geoip
cp path/to/dbip-country-lite.mmdb data/geoip/dbip-country-lite.mmdb
docker compose --env-file compose.env up -d
```

If the stack is already running, restart the backend after changing the file or `compose.env`:

```bash
docker compose --env-file compose.env up -d api
```

## DB-IP Lite example

```bash
mkdir -p data
curl -L https://download.db-ip.com/free/dbip-country-lite-latest.mmdb.gz \
  -o data/dbip-country-lite.mmdb.gz
gunzip -f data/dbip-country-lite.mmdb.gz
mv data/dbip-country-lite-latest.mmdb data/dbip-country-lite.mmdb
```

Review DB-IP's current terms before using it in production.

## MaxMind GeoLite2 example

```bash
mkdir -p data
tar -xzf GeoLite2-Country_*.tar.gz
find . -name 'GeoLite2-Country.mmdb' -print
cp GeoLite2-Country_*/GeoLite2-Country.mmdb data/GeoLite2-Country.mmdb
```

MaxMind requires its own account and license workflow.

## Verify it works

1. Set `geoip.provider` and `geoip.database_path`.
2. Restart the backend.
3. Ingest a report with a routable source IP.
4. Check search or report detail output for populated `country_code`, `country_name`, and `geo_provider` fields.

## Troubleshooting

If country fields stay empty, verify:

- the provider is not `none`
- `geoip.database_path` points to the actual `.mmdb` file
- the file is readable by the backend process
- the provider matches the MMDB you downloaded
- for Docker, `DMARC_GEOIP_DATABASE_PATH` uses the container path such as `/app/geoip/dbip-country-lite.mmdb`

Quick check:

```bash
ls -l data/*.mmdb
```

Docker quick check:

```bash
ls -l data/geoip/*.mmdb
docker compose --env-file compose.env exec api ls -l /app/geoip
```

GeoIP lookup failures do not reject ingest on their own. If ingest fails, inspect the job result or backend logs for the real cause.
