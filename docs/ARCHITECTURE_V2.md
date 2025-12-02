# Architecture V2: Hybrid Extraction Pipeline

## Overview
The V2 architecture moves away from simple Regular Expressions and introduces a **Structural & Semantic Analysis** approach. This is necessary to handle the high variability of "Impressum" (Legal Notice) pages in the DACH region (Germany, Austria, Switzerland).

## Core Technologies

| Component | Technology | Purpose |
| :--- | :--- | :--- |
| **Browser Engine** | **Playwright** (Chromium) | Renders JavaScript-heavy sites (e.g., SPAs, heavily styled pages) that standard `requests` cannot read. |
| **Content Extractor** | **Trafilatura** | Strips navigation, ads, footers, and cookie banners to provide clean, human-readable text. |
| **NLP Engine** | **SpaCy** (`de_core_news_md`) | Named Entity Recognition (NER) to identify "Organizations" (Companies) and "Locations" (Streets/Cities). |
| **Fuzzy Matching** | **TheFuzz** | Matches text candidates against the domain name to confirm Company Identity. |
| **Phone Parsing** | **Google Libphonenumbers** | Standardizes phone numbers into International Format (e.g., `+49 30...`). |

## The "Anchor & Expand" Strategy

The previous version failed (18% accuracy) because it guessed where data was based on labels like "Firma:". Real websites rarely use these labels.

The **V2 Strategy** uses the highly predictable structure of addresses:

### 1. The Anchor: Zip Code + City
German/Swiss Zip codes are strictly formatted (5 digits DE, 4 digits CH).
-   We scan the clean text for this pattern: `\b\d{4,5}\s+[A-Z][a-z]+`.
-   Accuracy: **~85-90%** (Very reliable).

### 2. The Expand: Contextual Lookup
Once the Anchor is found at line `N`:
-   **Street**: We check line `N` (same line) and `N-1` (line above). We validate candidates using Street suffixes (str, weg, gasse) and SpaCy Location checks.
-   **Company Name**: We check lines `N-1`, `N-2`, and `N-3`. We score candidates based on:
    -   Is it an Organization? (SpaCy)
    -   Does it contain a Legal Form? (GmbH, AG)
    -   Does it fuzzy-match the Domain Name?
    -   Is it *not* a blacklisted word (Geschäftsführer, Kontakt)?

### 3. The Fallback: Wayback Machine
If the live site returns `403 Forbidden` (Blocking) or `Timeout`, the crawler automatically requests the latest snapshot from the **Internet Archive (Wayback Machine)**. This recovers data from ~20% of blocked sites.

## Data Flow

1.  **Spider (`robust.py`)**:
    -   Queues URLs.
    -   Tries Direct Access (Playwright).
    -   If fail: Tries Proxies.
    -   If fail: Tries Wayback Machine.
2.  **Middleware**:
    -   Rotates User-Agents.
    -   Rotates Proxies.
    -   Simulates human delays.
3.  **Pipeline (`pipelines.py`)**:
    -   Receives raw HTML.
    -   Runs `Trafilatura` -> Clean Text.
    -   Runs `SpacyExtractor` -> NLP Entities.
    -   Executes "Anchor & Expand" Logic.
    -   Validates Data.
    -   Saves to CSV & Postgres.

## Performance Metrics (Benchmark)

On a test set of 50 random German business domains:
-   **Postal/City**: 85%
-   **Phone/Email**: 80%+
-   **Company Name**: ~55% (up from 18%)
-   **Street**: ~30% (up from <10%)

*Note: "Street" remains the hardest field due to extreme formatting variations (e.g., multi-line, embedded in sentences).*
