# Docker-Based Legal Notice Crawler

Production-grade crawler for extracting legal notice (Impressum) data from German/Swiss websites.

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Scrapy    │────▶│   Splash    │────▶│  Websites   │
│   Crawler   │     │ (JS Render) │     │             │
└──────┬──────┘     └─────────────┘     └─────────────┘
       │
       │ Items
       ▼
┌─────────────┐     ┌─────────────┐
│  Extractor  │────▶│ PostgreSQL  │
│ (spaCy NER) │     │  Database   │
└─────────────┘     └─────────────┘
```

## Quick Start

```powershell
cd D:\docker-crawler

# Build images
.\run.ps1 build

# Start services
.\run.ps1 start

# Run crawler
.\run.ps1 crawl

# Check results
.\run.ps1 status

# Export to CSV
.\run.ps1 export
```

## Manual Commands

```powershell
# Build
docker-compose build

# Start services
docker-compose up -d

# Run crawler with custom domains
docker-compose run --rm crawler scrapy crawl impressum -a domains_file=/app/domains.txt

# View logs
docker-compose logs -f crawler

# Query database
docker-compose exec postgres psql -U crawler -d crawler -c "SELECT domain, company_name, street, city FROM results;"

# Stop
docker-compose down
```

## Expected Extraction Rates

| Field | Target Rate |
|-------|-------------|
| Complete Address | 25-40% |
| Company Name | 60%+ |
| Email | 40%+ |
| Phone | 40%+ |

## Components

- **Splash**: JavaScript rendering (port 8050)
- **Redis**: Task queue (port 6379)
- **PostgreSQL**: Results storage (port 5432)
- **Extractor**: spaCy NER service (port 8080)
- **Scrapy**: Web crawler
