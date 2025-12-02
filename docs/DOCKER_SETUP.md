# Docker Crawler Setup & Usage Guide

Complete guide for the Docker-based legal notice crawler with automatic discovery and export.

## Prerequisites

- **Docker** and **Docker Compose** installed
- Internet connection for crawling

## Directory Structure

```
docker-crawler/
├── crawler/                    # Scrapy project
│   ├── discovery.py            # Auto-discovery tool
│   ├── legal_crawler/
│   │   ├── spiders/robust.py   # Production spider
│   │   ├── pipelines.py        # Hybrid extraction
│   │   ├── stats_extension.py  # Colored summary
│   │   └── settings.py         # Configuration
│   ├── Dockerfile
│   └── requirements.txt
├── data/                       # Output folder (CSV)
├── docker-compose.yml
├── domains_full.txt            # Domain list (auto-populated)
└── .env                        # Environment variables
```

---

## Complete Workflow

### Step 1: Build & Start

```bash
cd docker-crawler

# Build the crawler image
docker-compose build crawler

# Start background services
docker-compose up -d redis postgres ollama
```

### Step 2: Discover Domains (Automatic)

Use the discovery tool to find business domains automatically:

```bash
# Find 500 German domains
docker-compose run --rm crawler python discovery.py --tld de --limit 500

# Find 1000 Swiss domains  
docker-compose run --rm crawler python discovery.py --tld ch --limit 1000

# Find Austrian domains
docker-compose run --rm crawler python discovery.py --tld at --limit 500
```

**Output:**
```
=== Domain Discovery Tool ===
Target TLD: .de
Limit: 500

[*] Querying crt.sh for *.de...
[+] crt.sh found 500 domains
[+] Added 500 new domains to /app/domains_full.txt
```

### Step 3: Run Crawler

```bash
# Crawl all discovered domains
docker-compose run --rm crawler scrapy crawl robust -a domains_file=/app/domains_full.txt

# Or crawl specific domains
docker-compose run --rm crawler scrapy crawl robust -a domains="bmw.de,siemens.com"
```

**Output:**
```
[*] Loaded 500 domains
============================================================
[*] Spider started at 2024-12-02 12:00:00
============================================================
[*] Progress: 250/500 (50%) | Success: 180 | Failed: 70

============================================================
           CRAWL SUMMARY
============================================================
Duration: 1h 15m 30s
--- Domains ---
  Successful:        180
  Failed:            70
  Success rate:      72.0%
--- Items Extracted ---
  Total items:       180
============================================================
```

### Step 4: Export Results

#### Option A: CSV File (Default)
Results are automatically saved to:
```
docker-crawler/data/legal_notices.csv
```

View on Windows:
```powershell
Get-Content .\data\legal_notices.csv | Select-Object -First 5
```

View on Linux/Mac:
```bash
head -5 data/legal_notices.csv
```

#### Option B: Export from PostgreSQL

```bash
# Export all columns to CSV
docker-compose exec postgres psql -U crawler -d crawler -c \
  "\COPY legal_notices TO '/tmp/export.csv' CSV HEADER"
docker cp $(docker-compose ps -q postgres):/tmp/export.csv ./data/full_export.csv

# Export selected columns only
docker-compose exec postgres psql -U crawler -d crawler -c \
  "\COPY (SELECT domain, company_name, street, postal_code, city, phone, email FROM legal_notices) TO '/tmp/export.csv' CSV HEADER"
docker cp $(docker-compose ps -q postgres):/tmp/export.csv ./data/contacts.csv
```

#### Option C: Query Database

```bash
# Enter PostgreSQL shell
docker-compose exec postgres psql -U crawler -d crawler

# SQL queries:
SELECT COUNT(*) FROM legal_notices;
SELECT domain, company_name, city FROM legal_notices LIMIT 10;
SELECT * FROM legal_notices WHERE city = 'Berlin';

# Exit
\q
```

#### Option D: Export to JSON

```bash
docker-compose exec postgres psql -U crawler -d crawler -t -c \
  "SELECT json_agg(row_to_json(legal_notices)) FROM legal_notices" > data/export.json
```

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

| Setting | Default | Description |
|---------|---------|-------------|
| `CONCURRENT_REQUESTS` | 8 | Parallel requests |
| `DOWNLOAD_DELAY` | 1 | Seconds between requests |
| `DOWNLOAD_TIMEOUT` | 90 | Request timeout (seconds) |
| `RETRY_TIMES` | 3 | Retry attempts per URL |
| `PROXY_ENABLED` | True | Use rotating proxies |

---

## Output Fields

| Field | Description | Example |
|-------|-------------|---------|
| `domain` | Source domain | `example.de` |
| `url` | Impressum URL | `https://example.de/impressum` |
| `company_name` | Company name | `Example GmbH` |
| `street` | Street address | `Musterstraße 123` |
| `postal_code` | ZIP code | `12345` |
| `city` | City | `Berlin` |
| `phone` | Phone number | `+49 30 12345678` |
| `email` | Email address | `info@example.de` |
| `legal_form` | Legal form | `GmbH` |
| `register_number` | Trade register | `HRB 12345` |
| `vat_id` | VAT ID | `DE123456789` |
| `ceo` | Managing director | `Max Mustermann` |

---

## Troubleshooting

### No domains loaded
```bash
# Check domains file
wc -l domains_full.txt

# Re-run discovery
docker-compose run --rm crawler python discovery.py --tld de --limit 100
```

### DATABASE_URL not set
Create a `.env` file with your credentials (see Configuration section above).

### High 403 error rate
Edit settings.py:
```python
CONCURRENT_REQUESTS = 4      # Reduce parallelism
DOWNLOAD_DELAY = 3           # Increase delay
PROXY_ENABLED = True         # Enable proxies
```

### Services not running
```bash
docker-compose ps
docker-compose up -d redis postgres ollama
```

### Clean restart
```bash
docker-compose down -v --remove-orphans
docker-compose up -d redis postgres ollama
docker-compose build crawler
```

---

## Performance Tips

1. **Targeted Discovery**: Use DuckDuckGo dorks for higher quality domains
2. **Reduce Concurrency**: Lower `CONCURRENT_REQUESTS` if getting blocked
3. **Increase Delays**: Set `DOWNLOAD_DELAY = 2` for stubborn sites
4. **Filter Domains**: Remove large enterprises (they have heavy anti-bot)
5. **Night Crawling**: Run during off-peak hours for better success rates

---

## Architecture

```
Discovery (crt.sh + DDG)
        │
        ▼
   domains_full.txt
        │
        ▼
┌───────────────────┐
│  Scrapy Spider    │
│  (Playwright)     │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│  Trafilatura      │──▶ Clean text extraction
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│  SpaCy NER        │──▶ Entity recognition
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│  Anchor Strategy  │──▶ Find ZIP → look up for company
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐     ┌──────────────────┐
│  PostgreSQL       │     │  CSV Export      │
└───────────────────┘     └──────────────────┘
```
