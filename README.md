# SMB Web Crawler v2.1 (Docker & Hybrid AI)

**Welcome!** This is an advanced web scraping tool designed to extract legal and business information (Impressum) from DACH region websites (Germany, Austria, Switzerland).

**Current Version (v2.1)**:
-   **Architecture**: Docker-based (Scrapy + Playwright + Redis + Postgres).
-   **Strategy**: "Anchor & Expand" Hybrid Extraction (NLP + Structure).
-   **Resilience**: Anti-blocking (Proxies, User-Agents) + Wayback Machine Fallback.

---

## 🚀 Quick Start (Docker)

The project now runs primarily in **Docker** for stability and reproducibility.

### 1. Setup
```bash
cd docker-crawler
docker-compose build crawler
docker-compose up -d redis postgres
```

### 2. Run the Crawler
```bash
# Crawl a list of domains (from domains_full.txt)
docker-compose run --rm crawler scrapy crawl robust -a domains_file=/app/domains_full.txt
```

**Results** are saved automatically to `docker-crawler/data/results.csv`.

👉 **[Read the Full Setup Guide](docs/DOCKER_SETUP.md)**

---

## 🧠 How It Works (Architecture V2)

We have replaced simple Regex matching with a **Hybrid NLP Strategy**:

1.  **Render**: Playwright renders the page (bypassing JS checks).
2.  **Clean**: `Trafilatura` extracts only the main text content.
3.  **Anchor**: We locate the **Zip Code & City** (High confidence anchor).
4.  **Expand**: We analyze the lines *around* the anchor to find the **Company Name** and **Street** using `SpaCy` (AI) and Fuzzy Matching.

👉 **[Read the Architecture Deep Dive](docs/ARCHITECTURE_V2.md)**

---

## Features

*   **Multi-Layer Resilience**:
    *   Direct Request -> Proxy Rotation -> Wayback Machine.
*   **Data Quality**:
    *   Validated against 50+ real-world test cases.
    *   Garbage filtering (removes "Postfach", navigation text).
    *   International Phone Number standardization.
*   **Unified Export**:
    *   Clean CSV output ready for client use.

---

## Legacy (Python Script)
*The old `main.py` method is still available in the `src/` folder but is deprecated in favor of the Dockerized Robust Spider.*

---

*Developed for High-Accuracy Legal Data Extraction*
