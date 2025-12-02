# SMB Web Crawler v2.2 (Docker + Auto-Discovery)

Advanced web scraping tool for extracting legal/business information (Impressum) from DACH region websites.

## Features

- **Automatic Discovery**: Find domains via Certificate Transparency logs & search engines
- **Hybrid Extraction**: NLP + Structural analysis for high accuracy
- **Anti-Blocking**: Proxy rotation, stealth headers, Playwright rendering
- **Clean Output**: Colored progress, summary stats, CSV/PostgreSQL export

---

## Quick Start

```bash
cd docker-crawler

# 1. Build
docker-compose build crawler
docker-compose up -d redis postgres ollama

# 2. Discover domains (automatic)
docker-compose run --rm crawler python discovery.py --tld de --limit 500

# 3. Crawl
docker-compose run --rm crawler scrapy crawl robust -a domains_file=/app/domains_full.txt

# 4. Export results (timestamped files)
ls data/legal_notices_*.csv
```

---

## Commands Reference

### Discovery
```bash
# German domains
docker-compose run --rm crawler python discovery.py --tld de --limit 1000

# Swiss domains
docker-compose run --rm crawler python discovery.py --tld ch --limit 500

# Austrian domains
docker-compose run --rm crawler python discovery.py --tld at --limit 500
```

### Crawling
```bash
# From file
docker-compose run --rm crawler scrapy crawl robust -a domains_file=/app/domains_full.txt

# Specific domains
docker-compose run --rm crawler scrapy crawl robust -a domains="bmw.de,siemens.com"
```

### Export
```bash
# Export clean records only (filters garbage)
docker-compose run --rm crawler python export_clean.py
# Output: data/clean_leads_YYYYMMDD_HHMMSS.csv

# List all exports
dir docker-crawler/data/*.csv          # Windows
ls docker-crawler/data/*.csv           # Linux/Mac

# PostgreSQL export
docker-compose exec postgres psql -U crawler -d crawler -c \
  "\COPY legal_notices TO '/tmp/export.csv' CSV HEADER"
docker cp $(docker-compose ps -q postgres):/tmp/export.csv ./export.csv

# Query database
docker-compose exec postgres psql -U crawler -d crawler -c \
  "SELECT domain, company_name, city FROM legal_notices LIMIT 10"
```

---

## Output Fields

| Field | Example |
|-------|---------|
| `domain` | `example.de` |
| `company_name` | `Example GmbH` |
| `street` | `Musterstraße 123` |
| `postal_code` | `12345` |
| `city` | `Berlin` |
| `phone` | `+49 30 12345678` |
| `email` | `info@example.de` |
| `legal_form` | `GmbH` |
| `register_number` | `HRB 12345` |
| `vat_id` | `DE123456789` |
| `ceo` | `Max Mustermann` |

---

## Sample Output

```
=== Domain Discovery Tool ===
[*] Querying crt.sh for *.de...
[+] crt.sh found 500 domains
[+] Added 500 new domains to /app/domains_full.txt

============================================================
           CRAWL SUMMARY
============================================================
Duration: 0h 45m 12s
--- Domains ---
  Total domains:    500
  Successful:       320
  Failed:           180
  Success rate:     64.0%
--- Items Extracted ---
  Total items:      320
============================================================
```

---

## Documentation

- [Docker Setup Guide](docs/DOCKER_SETUP.md) - Complete installation & usage
- [Architecture V2](docs/ARCHITECTURE_V2.md) - How the extraction works
- [Data Model](docs/DATA_MODEL.md) - Database schema

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| No domains loaded | Run `discovery.py` first |
| DATABASE_URL not set | Create `.env` file in docker-crawler/ |
| High 403 errors | Reduce `CONCURRENT_REQUESTS` in settings.py |
| Slow crawling | Increase `CONCURRENT_REQUESTS` (if not blocked) |

---

## License

MIT License
