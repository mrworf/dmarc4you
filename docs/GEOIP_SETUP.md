# GeoIP Setup

This application supports optional offline GeoIP country enrichment during ingest. When configured, aggregate and forensic records store country metadata derived from the source IP.

## Supported providers

- `dbip-lite-country`
- `maxmind-geolite2-country`

Both providers use a local MMDB database file. The application does not download or update these files automatically.

## Configuration

Set the provider and database path in `config.yaml`:

```yaml
geoip:
  provider: dbip-lite-country
  database_path: /opt/dmarc4you/geoip/dbip-country-lite.mmdb
```

Or:

```yaml
geoip:
  provider: maxmind-geolite2-country
  database_path: /opt/dmarc4you/geoip/GeoLite2-Country.mmdb
```

If `provider` is `none`, GeoIP enrichment is disabled.

## Option 1: DB-IP Lite Country

DB-IP Lite provides a free country-level database. Review their current download and attribution terms before using it in production.

Typical setup flow:

```bash
mkdir -p /opt/dmarc4you/geoip
cd /opt/dmarc4you/geoip

# Download the current MMDB archive from DB-IP
curl -LO https://download.db-ip.com/free/dbip-country-lite-latest.mmdb.gz
gunzip dbip-country-lite-latest.mmdb.gz
mv dbip-country-lite-latest.mmdb dbip-country-lite.mmdb
```

Then configure:

```yaml
geoip:
  provider: dbip-lite-country
  database_path: /opt/dmarc4you/geoip/dbip-country-lite.mmdb
```

## Option 2: MaxMind GeoLite2 Country

MaxMind GeoLite2 requires a free MaxMind account and acceptance of their license terms.

Typical setup flow:

```bash
mkdir -p /opt/dmarc4you/geoip
cd /opt/dmarc4you/geoip

# Download the GeoLite2 Country archive from MaxMind using your account workflow
tar -xzf GeoLite2-Country_*.tar.gz
find . -name 'GeoLite2-Country.mmdb' -print
cp GeoLite2-Country_*/GeoLite2-Country.mmdb /opt/dmarc4you/geoip/GeoLite2-Country.mmdb
```

Then configure:

```yaml
geoip:
  provider: maxmind-geolite2-country
  database_path: /opt/dmarc4you/geoip/GeoLite2-Country.mmdb
```

## Python dependencies

GeoIP lookups require the optional MMDB reader dependency declared in `requirements.txt`.

If you use a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Verification

1. Configure `geoip.provider` and `geoip.database_path`.
2. Restart the application.
3. Ingest a report containing a source IP that resolves to a known country.
4. Open the report detail or dashboard/search results and confirm `country_code` / `country_name` are populated.

## Troubleshooting

### Country fields stay empty

Check:

- `geoip.provider` is not `none`
- `geoip.database_path` points to the actual `.mmdb` file
- the configured provider matches the database you downloaded
- the optional Python dependencies were installed successfully

### The file path looks correct but still does not work

Verify the application process can read the MMDB file:

```bash
ls -l /opt/dmarc4you/geoip
```

### Ingest fails when GeoIP is misconfigured

GeoIP lookup failures should not reject ingest. If reports fail, inspect the ingest job item status and application logs for a different root cause.

### Reverse DNS works but GeoIP does not

Reverse DNS and GeoIP are separate features. Reverse DNS uses DNS resolvers; GeoIP uses the local MMDB file only.
