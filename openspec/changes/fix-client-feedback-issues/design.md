# Design: Fix Client Feedback Issues

## Context
This document outlines the architectural decisions required to address GitHub Issue #1. The primary goal is to improve transparency, data quality, and discovery of Small and Medium Enterprises (SMBs).

## 1. Architecture Overview (Issue #1)

The system follows a pipeline architecture: **Discovery → Queue → Crawl → Extract → Validate → Store → Export**.

### Execution Flow Diagram

```mermaid
graph TD
    CLI[CLI (main.py)] -->|triggers| Manager[CrawlManager]
    
    subgraph "Phase 1: Discovery"
        Manager -->|discover command| Disc[Discovery Module]
        Disc -->|Sources| Tranco[Tranco List]
        Disc -->|Sources| Search[Search Engines]
        Disc -->|Sources| CC[CommonCrawl]
        Disc -->|Output| Queue[(SQLite Queue)]
    end
    
    subgraph "Phase 2: Crawl & Extract"
        Manager -->|crawl command| Crawler[EnhancedCrawler]
        Crawler -->|1. Check| Robots[Robots.txt Checker]
        Crawler -->|2. Fetch| HTML[HTML Content]
        
        HTML -->|Input| Extractor[EnhancedExtractor]
        HTML -->|Input| LegalExt[LegalExtractor]
        
        LegalExt -->|Uses| GLiNER[GLiNER AI Model]
        LegalExt -->|Uses| Regex[Regex Fallback]
    end
    
    subgraph "Phase 3: Validation (NEW)"
        LegalExt -->|Raw Data| Validator[DataValidator Class]
        Validator -->|Check| NameCheck{Valid Name?}
        Validator -->|Check| AddrCheck{Valid Address?}
        
        NameCheck -->|Yes| DB[(SQLite DB)]
        NameCheck -->|No| Discard[Discard/Log]
    end
    
    subgraph "Phase 4: Export"
        Manager -->|export command| Exporter[UnifiedExporter]
        DB -->|Read| Exporter
        Exporter -->|Format| CSV[Final CSV File]
    end
```

## 2. Key Technical Decisions

### 2.1 SMB Discovery Strategy (Issue #2)
**Why**: Top-1M lists (Tranco, Majestic) inherently bias towards large global enterprises.
**Decision**: We will implement a **"Targeted Discovery"** mode.
- **Mechanism**: Use Search Engine queries (DuckDuckGo/Bing) with specific dorks.
- **Query Pattern**: `site:.de "Impressum" "GmbH" -site:facebook.com -site:youtube.com`
- **Logic**: This directly finds pages that *have* an Impressum (legal requirement for German businesses) but may not have high traffic.
- **Trade-off**: Slower than bulk list download, but significantly higher quality for SMBs.

### 2.2 Data Quality & Validation (Issue #4)
**Why**: Regex is too greedy. It captures navigation menus as "names" and addresses as "CEOs".
**Decision**: Implement a Strict Validation Layer using **Spacy** (NLP) and Rules.
- **Tool**: `spaCy` (with `de_core_news_sm`) or refined `GLiNER`.
- **Rule: CEO Validation**:
  - Must be `< 4` tokens.
  - Must NOT contain digits.
  - Must NOT contain "GmbH", "Street", "Tel", "Fax".
  - Must be recognized as `PER` (Person) by NER.
- **Rule: Address Validation**:
  - Must contain a valid ZIP code (5 digits for DE).
  - City must be in a known list of cities (optional) or look like a Location entity.
  - Street must contain a number.

### 2.3 Company Size Classification (Issue #5)
**Why**: Client wants `company_size` (solo, sme, enterprise).
**Decision**: Heuristic Classification.
- **Logic**:
  1. **Legal Form**:
     - `AG`, `KGaA`, `SE` → Likely **Enterprise**.
     - `GmbH` → **SME** (or Enterprise, indeterminate).
     - `UG`, `GbR`, `e.K.`, `Einzelunternehmen` → Likely **Solo/Micro**.
  2. **Web Presence**:
     - Massive site structure (>1000 pages) → Likely Enterprise.
     - Presence of "Investor Relations" → Enterprise.
  3. **Content**:
     - Mentions of "X employees" (regex extraction).

### 2.4 Unified Export Schema (Issue #5)
**Why**: Client requires a single file with a specific schema.
**Decision**: Create a dedicated `export_unified()` function that:
- Joins `results_enhanced` (contact info) and `legal_entities` (legal info).
- Prioritizes `legal_entities` for Company Name and Address (more accurate).
- Formats `social_links` as a JSON-like string or pipe-separated list.
- explicitly exports `robots_allowed` status.

## 3. Open Source Tools Integration
To meet the "no hallucination" and "robust" requirement:
- **NLP**: `spaCy` (Industrial-strength NLP) for validation.
- **Crawling**: `Crawl4AI` (Existing) is good.
- **Discovery**: `duckduckgo-search` (Python lib) or custom `httpx` scraper with rotation.
- **Validation**: `pydantic` for strict schema validation before saving.

## 4. Risks
- **Search Rate Limiting**: Search engines block aggressive scraping.
  - *Mitigation*: Use slow delays (random 5-15s), rotate User-Agents, or use APIs if budget allows (SerpApi). *Note: We will stick to free/open source per request, so slower rate is acceptable.*
- **False Positives in Validation**: Strict rules might reject valid weird names.
  - *Mitigation*: Log rejected items to `debug_rejected.csv` for manual review.
