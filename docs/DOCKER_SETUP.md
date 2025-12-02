# Docker Crawler Setup & Usage Guide

This project has been migrated to a robust Docker-based architecture to ensure consistency, scalability, and reliability.

## Prerequisites

- **Docker** and **Docker Compose** installed on your machine.
- A valid internet connection (for fetching proxies and crawling).

## Directory Structure

The Docker setup is located in `D:\docker-crawler` (or the root `docker-crawler` folder).

```
docker-crawler/
├── crawler/                 # Scrapy project source
│   ├── legal_crawler/       # Spider & Pipelines
│   │   ├── spiders/robust.py # The main Production Spider
│   │   ├── pipelines.py     # Hybrid Extraction Logic
│   │   ├── settings.py      # Config (Proxies, Timeouts)
│   │   └── ...
│   ├── Dockerfile           # Python environment definition
│   └── requirements.txt     # Dependencies (Trafilatura, SpaCy, etc.)
├── data/                    # Shared volume for CSV results
├── docker-compose.yml       # Service orchestration
└── domains_full.txt         # Input list of domains
```

## Services

The stack consists of 4 services:
1.  **Crawler**: The core Scrapy container (Python 3.11, Playwright, SpaCy).
2.  **Redis**: Manages the job queue and crawl state.
3.  **Postgres**: Stores structured results (SQL).
4.  **Ollama**: (Optional) Local LLM service for advanced extraction (disabled by default for memory).

## Quick Start

### 1. Build the Environment
Before the first run (or after changing code/requirements), build the images:
```bash
cd docker-crawler
docker-compose build crawler
```

### 2. Start Infrastructure
Start the background services (Database & Redis):
```bash
docker-compose up -d redis postgres
```

### 3. Run the Crawler
To run the crawler against a list of domains:

```bash
# Run the 'robust' spider using domains from a file
docker-compose run --rm crawler scrapy crawl robust -a domains_file=/app/domains_full.txt
```

**Note**: Ensure your domain list file (`domains_full.txt`) is present in the `docker-crawler` root directory (which is mounted to `/app` inside the container).

## Configuration

### extraction & Logic
The extraction logic is defined in `crawler/legal_crawler/pipelines.py`. It uses a **Hybrid "Anchor" Strategy**:
1.  **Trafilatura**: Extracts clean main text from HTML.
2.  **SpaCy (NLP)**: Identifies Organizations and Locations.
3.  **Anchoring**: Locates the Zip Code/City line and looks *upwards* to find the Company Name and *around* to find the Street.

### Proxy & Anti-Blocking
Settings are in `crawler/legal_crawler/settings.py`.
-   **Proxies**: Enabled by default (`PROXY_ENABLED = True`). Fetches free proxies from GitHub lists.
-   **Playwright**: Handles JavaScript rendering.
-   **Retries**: Configured for 3 retries with extended timeouts (90s).

## Results
Results are saved to:
1.  **CSV**: `data/results.csv` (Accessible in the `data` folder on your host machine).
2.  **PostgreSQL**: Table `results` in the `crawler` database.

## Troubleshooting

**Timeout Errors?**
The timeouts have been increased to 90s. If sites are still timing out, they might be extremely slow or blocking the connection entirely.

**"Connection Refused" in Docker?**
Ensure `redis` and `postgres` are running (`docker-compose ps`).

**Low Extraction Quality?**
Check `data/results.csv`. If specific fields are missing, the site layout might be unique. The current "Anchor" strategy covers ~85% of standard German/Swiss layouts.
