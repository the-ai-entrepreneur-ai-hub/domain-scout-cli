# Product Requirement Document (PRD): TLD-Based Web Crawler PoC (v1.2 - Final)

## 1. Executive Summary
**Project Name:** Simple Web Crawler for Public Website Data (PoC)
**Objective:** Develop a Python-based Proof-of-Concept (PoC) script that discovers, crawls, and extracts public company information from websites associated with a specific Top-Level Domain (TLD) (e.g., `.de`, `.ch`).
**Target Users:** Technical users running the script via Command Line Interface (CLI).
**Scope:** This is a prototype to demonstrate automated discovery and extraction. It is **not** a large-scale distributed production system.

## 2. Project Scope & Deliverables

### 2.1 In-Scope
*   **CLI Application:** A Python script executable from the terminal.
*   **Domain Discovery:** Mechanism to find active domains under a specified TLD (e.g., `.de`).
*   **Queue Persistence:** Discovered domains are immediately saved to a local database to decouple discovery from crawling.
*   **Web Crawling:** Visiting discovered URLs using `httpx` (HTTP/2) with robust anti-blocking.
*   **Pre-Flight Checks:** DNS resolution check to filter dead domains before HTTP connection attempts.
*   **Data Extraction:** Parsing HTML using `BeautifulSoup` + `lxml`.
*   **Junk Filtering:** Heuristics to skip "Parked Domains" and huge global sites (e.g., `google.de`).
*   **Data Storage:** Saving results to local CSV and SQLite database.
*   **Compliance:** `robots.txt` parser and GDPR filtering.

### 2.2 Out-of-Scope
*   **GUI:** No graphical interface.
*   **CAPTCHA Solving:** Skipped.
*   **Deep Crawling:** Only Home + Contact/About pages.
*   **Authentication:** No login support.

## 3. Functional Requirements

### 3.1 Domain Discovery & Queueing
The system must identify target domains and persist them before crawling.
*   **Sources:**
    1.  **Tranco List:** Filter top 1M list (Primary).
    2.  **Common Crawl:** CDX API (Secondary).
    3.  **Search Engine Fallback:** Limited top 50 results (Tertiary).
*   **Persistence:** Discovered domains are inserted into `crawler_data.db` (Table: `queue`) with status `PENDING`.
*   **Deduplication:** Ignore domains already present in the DB.

### 3.2 Pre-Flight & Crawler Engine
*   **Tech:** `asyncio`, `httpx`, `aiodns`.
*   **DNS Check:** Before HTTP request, resolve the domain. If NXDOMAIN (doesn't exist), mark as `FAILED_DNS` and skip.
*   **Politeness:**
    *   **Rate Limiting:** Per-domain delays.
    *   **User-Agent:** Rotation.
    *   **Blacklist:** Skip domains in `config/blacklist.txt` (e.g., `facebook.com`, `amazon.com`).
*   **Runtime Control:** Stop gracefully if a file named `STOP` is detected in the root directory.

### 3.3 Data Extraction & Quality
*   **Parked Domain Detection:** Skip if Title/Content contains keywords: "Domain for sale", "Under Construction", "Parking", "GoDaddy".
*   **Fields:**
    1.  **Domain URL**
    2.  **Company Name:** (`og:site_name` > `meta title`).
    3.  **Description:** (`meta description`).
    4.  **Email:** Regex (filtering generic free providers unless on Contact page).
    5.  **Phone:** Regex.
    6.  **Address:** Heuristic patterns.
    7.  **Timestamp.**

### 3.4 Data Storage
*   **Database:** SQLite (`crawler_data.db`).
    *   `queue` table: `domain`, `source`, `status` (PENDING, PROCESSING, COMPLETED, FAILED), `created_at`.
    *   `results` table: `domain`, `company_name`, `email`, `...`
*   **CSV Export:** Append successful results to CSV for easy viewing.

## 4. Technical Architecture

### 4.1 Tech Stack
*   **Language:** Python 3.9+
*   **HTTP:** `httpx` (Async/HTTP2)
*   **DNS:** `aiodns`
*   **Parsing:** `BeautifulSoup4` + `lxml`
*   **Validation:** `Pydantic`
*   **DB:** `sqlite3` + `aiosqlite` (Async DB access)

### 4.2 Directory Structure
```
/
├── config/
│   ├── settings.yaml     # Delays, limits
│   └── blacklist.txt     # Domains to ignore
├── data/                 # DB and CSVs
├── main.py               # Entry point
├── requirements.txt
├── /src
│   ├── discovery.py      # Sources -> DB Queue
│   ├── dns_checker.py    # Async DNS resolver
│   ├── crawler.py        # Queue -> HTTP -> Extractor
│   ├── extractor.py      # HTML -> Data
│   ├── database.py       # Async DB wrapper
│   └── models.py         # Pydantic schemas
```

## 5. Implementation Roadmap

### Phase 1: Discovery & Persistence (Refined)
*   Implement `database.py` (SQLite schema).
*   Implement `discovery.py` to fetch domains and `INSERT INTO queue`.
*   **Deliverable:** `python main.py --task discover --tld .de` -> Populates DB.

### Phase 2: Crawling Engine
*   Implement `dns_checker.py`.
*   Implement `crawler.py` consuming the Queue.
*   **Deliverable:** `python main.py --task crawl` -> Processes DB queue.

### Phase 3: Extraction & Polish
*   Implement `extractor.py` with Parked Domain detection.
*   Final CSV export.
