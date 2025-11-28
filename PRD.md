# Product Requirement Document (PRD): TLD-Based Web Crawler PoC (v4.0 - Robust Legal Extraction)

## 1. Executive Summary
**Project Name:** Intelligent Web Crawler with Legal & Company Disclosure Extraction
**Objective:** Develop a Python-based Proof-of-Concept (PoC) that accurately discovers, crawls, and extracts comprehensive business information including legal disclosures, company registration details, and compliance information from websites using modern web technologies, structured data parsing, and machine learning techniques.
**Target Users:** Technical users requiring comprehensive business intelligence and legal compliance data via Command Line Interface (CLI).
**Scope:** This is an advanced prototype demonstrating intelligent extraction of both general business data and specific legal/regulatory information. It handles JavaScript-rendered content, multi-language legal notices, and provides validated company registration details.

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

### 3.3 Legal & Company Disclosure Extraction (NEW)
*   **Legal Notice Detection:** Automatically identify and prioritize legal pages:
    - /impressum (German), /legal-notice, /legal, /imprint
    - /mentions-legales (French), /aviso-legal (Spanish)
    - /note-legali (Italian), /privacy, /datenschutz
*   **Multi-Language Support:** Extract legal information in 6+ languages
*   **Registration Information:**
    - Company registration numbers (HRB, HRA, Companies House, etc.)
    - Register court/location details
    - VAT/Tax identification numbers
    - Data protection registration IDs
*   **Authorized Representatives:**
    - CEO/Managing Directors
    - Board members
    - Legal representatives
*   **Complete Address Extraction:**
    - Registered office address
    - Postal/correspondence address
    - International address format support

### 3.5 Robust Legal Data Extraction Requirements (MANDATORY)
For every discovered website, the system MUST extract all publicly available legal and company disclosure details from the website's legal notice section, regardless of country:

| # | Field | Description | Priority |
|---|-------|-------------|----------|
| 1 | **Company/Person Name** | Official legal name or responsible person | Required |
| 2 | **Legal Form** | GmbH, AG, LLC, Ltd, SARL, etc. | Required |
| 3 | **Full Postal Address** | Street, ZIP, City, Country (structured fields) | Required |
| 4 | **Authorized Representatives** | CEO, Directors, Managing Partners | Required |
| 5 | **Contact Information** | Email and Phone (validated & formatted) | Required |
| 6 | **Register Details** | Register Type, Court, Registration Number | Required |

*   **Multi-Pass Extraction Strategy:**
    1. **Pass 1:** Extract from structured data (JSON-LD, Schema.org) - highest accuracy
    2. **Pass 2:** Section-based extraction from isolated legal content
    3. **Pass 3:** Pattern matching with field validation
*   **Section Isolation:** Remove navigation, menus, headers, footers before extraction
*   **Country-Specific Extractors:** Specialized patterns for DE, UK, FR, IT, ES
*   **Field Validation:** All extracted data must pass validation before storage
*   **Structured Address Output:** Separate fields for street, ZIP, city, country

### 3.6 Automated Workflow (New)
*   **Chained Execution:** Users can trigger discovery and crawling in a single command.
*   **CLI Argument:** `--crawl` flag added to the `discover` command.
*   **Behavior:**
    1.  Runs discovery for specified TLD.
    2.  Immediately initializes `EnhancedCrawler`.
    3.  Processes the newly discovered domains (and any pending ones).

### 3.4 Data Extraction & Quality (Enhanced)
*   **Parked Domain Detection:** Advanced ML-based classification for parking pages, including visual similarity detection.
*   **Multi-Page Crawling:** Automatically discover and crawl critical pages (/about, /contact, /impressum, /team).
*   **Structured Data Parsing:** 
    - JSON-LD extraction for Schema.org data
    - Microdata and RDFa parsing
    - OpenGraph and Twitter Card metadata
*   **Enhanced Fields:**
    1.  **Domain URL** 
    2.  **Company Name:** 
        - Schema.org Organization/Corporation
        - JSON-LD @type:LocalBusiness
        - Copyright patterns (© 2024 Company)
        - VAT/Tax ID extraction
    3.  **Description:** Multi-source aggregation from structured data
    4.  **Email:** 
        - Validated with MX records
        - Extracted from mailto: links
        - Structured data ContactPoint
    5.  **Phone:** 
        - International format validation (phonenumbers lib)
        - Click-to-call links (tel:)
        - WhatsApp business numbers
    6.  **Address:** 
        - Schema.org PostalAddress
        - Google Maps iframe parsing
        - Geocoding validation with geopy
    7.  **Industry:** NAICS/SIC classification
    8.  **Social Media:** LinkedIn, Twitter, Facebook profiles
    9.  **Business Hours:** From structured data
    10. **Confidence Score:** Data quality metric (0-100%)
    11. **Legal Entity Information:**
        - Legal name & form (GmbH, LLC, Ltd., etc.)
        - Registration number & court
        - Authorized representatives
    12. **Compliance Data:**
        - Data protection officer contact
        - Legal department contact
        - Fax number (still legally relevant)
    13. **Timestamp**

### 3.4 Data Storage
*   **Database:** SQLite (`crawler_data.db`).
    *   `queue` table: `domain`, `source`, `status` (PENDING, PROCESSING, COMPLETED, FAILED), `created_at`.
    *   `results` table: `domain`, `company_name`, `email`, `...`
*   **CSV Export:** Append successful results to CSV for easy viewing.

## 4. Technical Architecture

### 4.1 Tech Stack (Enhanced)
*   **Language:** Python 3.9+
*   **Browser Automation:** `playwright` (JavaScript rendering, modern web support)
*   **HTTP:** `httpx` (Async/HTTP2) + `cloudscraper` (Anti-bot bypass)
*   **DNS:** `aiodns` + `dnspython` (MX record validation)
*   **Parsing:** 
    - `BeautifulSoup4` + `lxml` (HTML parsing)
    - `extruct` (Structured data extraction)
    - `trafilatura` (Main content extraction)
*   **Data Extraction:**
    - `spacy` (Named Entity Recognition)
    - `newspaper3k` (Article extraction)
*   **Validation:** 
    - `Pydantic` (Data models)
    - `phonenumbers` (Phone validation)
    - `email-validator` (Email verification)
    - `geopy` (Address geocoding)
*   **ML/NLP:**
    - `scikit-learn` (Classification)
    - `langdetect` (Language detection)
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
