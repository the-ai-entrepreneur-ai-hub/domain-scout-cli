# Docker-Based Legal Notice Crawler (V2.2)

Production-grade crawler for extracting legal notice (Impressum) data from German/Swiss websites.
Features **Automatic Discovery**, **Hybrid Extraction** (NLP + Anchor Strategy), and **Colored Output**.

## Quick Start

### 1. Build & Start Services
```bash
cd docker-crawler
docker-compose build crawler
docker-compose up -d redis postgres ollama
```

### 2. Discover Domains (Automatic)
```bash
# Find 500 German domains
docker-compose run --rm crawler python discovery.py --tld de --limit 500

# Find 1000 Swiss domains
docker-compose run --rm crawler python discovery.py --tld ch --limit 1000

# Find Austrian domains
docker-compose run --rm crawler python discovery.py --tld at --limit 500
```

### 3. Run Crawler
```bash
# Crawl all discovered domains
docker-compose run --rm crawler scrapy crawl robust -a domains_file=/app/domains_full.txt

# Or crawl specific domains
docker-compose run --rm crawler scrapy crawl robust -a domains="example.de,firma.ch"
```

### 4. Export Results

#### CSV Export (Default)
Results are automatically saved with timestamp:
```
docker-crawler/data/legal_notices_YYYYMMDD_HHMMSS.csv
```

#### Export Clean Records Only
Filter out garbage and export only valid business leads:
```bash
docker-compose run --rm crawler python export_clean.py
```
Output: `data/clean_leads_YYYYMMDD_HHMMSS.csv`

#### View CSV on Host
```bash
# Windows PowerShell - list all exports
dir .\data\*.csv

# Linux/Mac
ls -la data/*.csv
```

#### Export from PostgreSQL
```bash
# Export all data to CSV
docker-compose exec postgres psql -U crawler -d crawler -c "\COPY legal_notices TO '/tmp/export.csv' CSV HEADER"
docker cp $(docker-compose ps -q postgres):/tmp/export.csv ./data/export.csv

# Export specific columns
docker-compose exec postgres psql -U crawler -d crawler -c "\COPY (SELECT domain, company_name, street, postal_code, city, phone, email FROM legal_notices) TO '/tmp/export.csv' CSV HEADER"
docker cp $(docker-compose ps -q postgres):/tmp/export.csv ./data/export.csv
```

#### Query Database Directly
```bash
# Enter PostgreSQL shell
docker-compose exec postgres psql -U crawler -d crawler

# Inside psql:
SELECT domain, company_name, city FROM legal_notices LIMIT 10;
SELECT COUNT(*) FROM legal_notices;
\q  -- exit
```

#### Export to JSON
```bash
docker-compose exec postgres psql -U crawler -d crawler -c "SELECT json_agg(legal_notices) FROM legal_notices" > data/export.json
```

---

## Output Format

The crawler exports the following fields:

| Field | Description | Example |
|-------|-------------|---------|
| `domain` | Source domain | `example.de` |
| `url` | Impressum URL | `https://example.de/impressum` |
| `company_name` | Extracted company | `Example GmbH` |
| `street` | Street address | `Musterstraße 123` |
| `postal_code` | ZIP/PLZ | `12345` |
| `city` | City | `Berlin` |
| `phone` | Phone number | `+49 30 12345678` |
| `email` | Email address | `info@example.de` |
| `legal_form` | Legal form | `GmbH` |
| `register_number` | Trade register | `HRB 12345` |
| `register_court` | Court | `Amtsgericht Berlin` |
| `vat_id` | VAT ID | `DE123456789` |
| `ceo` | Managing director | `Max Mustermann` |
| `crawled_at` | Timestamp | `2024-12-02 12:00:00` |

---

## Configuration

### Environment Variables (.env)
Create a `.env` file in `docker-crawler/` with your database credentials.
See `docker-crawler/.env.example` for the required variables:
- `DB_PASS` - Database password
- `DATABASE_URL` - Full PostgreSQL connection string  
- `PROXY_ENABLED` - Enable proxy rotation (true/false)
- `LOG_LEVEL` - Logging level (ERROR recommended)

### Crawler Settings
Edit `crawler/legal_crawler/settings.py`:
```python
CONCURRENT_REQUESTS = 8        # Parallel requests
DOWNLOAD_DELAY = 1             # Delay between requests
DOWNLOAD_TIMEOUT = 90          # Request timeout
RETRY_TIMES = 3                # Retry attempts
```

---

## Troubleshooting

### No domains loaded (0 domains)
```bash
# Check if domains_full.txt exists and has content
cat domains_full.txt | wc -l

# Re-run discovery
docker-compose run --rm crawler python discovery.py --tld de --limit 100
```

### DATABASE_URL not set
Create a `.env` file with your credentials (see Configuration section above).

### High failure rate (many 403 errors)
- Consider using residential proxies
- Reduce `CONCURRENT_REQUESTS` to 4
- Increase `DOWNLOAD_DELAY` to 2-3 seconds

### Clean restart
```bash
docker-compose down -v
docker-compose up -d redis postgres ollama
docker-compose build crawler
```

---

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Discovery.py   │────▶│  domains_full.txt │────▶│  Scrapy Spider  │
│  (crt.sh + DDG) │     │  (domain list)    │     │  (Playwright)   │
└─────────────────┘     └──────────────────┘     └────────┬────────┘
                                                          │
                        ┌─────────────────────────────────┘
                        ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Trafilatura   │────▶│   SpaCy NER      │────▶│  Anchor+Expand  │
│  (clean text)   │     │  (de_core_news)  │     │  (extraction)   │
└─────────────────┘     └──────────────────┘     └────────┬────────┘
                                                          │
                        ┌─────────────────────────────────┘
                        ▼
┌─────────────────┐     ┌──────────────────┐
│   PostgreSQL    │◀────│   CSV Export     │
│   (storage)     │     │  (legal_notices) │
└─────────────────┘     └──────────────────┘
```

---

## License

MIT License
