# Change: Fix Client Feedback Issues (Milestone 2)

## Why

The client (GitHub Issue #1) has raised 5 critical issues that must be addressed before final delivery.
This proposal analyzes the root causes of each issue and defines a strict implementation plan using robust open-source frameworks.

### Issue 1: Code Transparency / Architecture Clarity
**Root Cause**: The system grew organically without updating high-level documentation. The current "CLI → Discovery → Crawl → Export" flow is hidden behind code.
**Logic**: The client cannot trust or maintain a "black box". We must provide a clear map of the system.

### Issue 2: Large Domain Bias (Crawler misses SMBs)
**Root Cause**: Current discovery sources (`Tranco`, `Majestic`, `Umbrella`) are "Top 1 Million" lists. By definition, these contain high-traffic, large enterprises. Small local businesses (e.g., local bakeries, law firms) never appear in these lists.
**Logic**: To find SMBs, we must invert the discovery strategy. Instead of "global popularity lists", we need "local keyword search" and "directory-based discovery".

### Issue 3: File Purpose Confusion
**Root Cause**: `legal_entities.csv` and `enhanced_results.csv` have overlapping fields but different schemas, causing confusion.
**Logic**: The client wants a single source of truth. We will document the legacy files but prioritize the new "Unified Export" as the standard deliverable.

### Issue 4: Data Quality Issues (Garbage In, Garbage Out)
**Root Cause**:
1. **Regex Brittleness**: Regex patterns like `r"Geschäftsführer: (.*)"` blindly capture everything until the newline, including navigation menus, addresses, or garbage text.
2. **Lack of Semantic Understanding**: The system doesn't "know" that "Otto-Ostrowski-Straße" is an address, not a CEO name.
3. **No Validation Layer**: Extracted data is saved directly without being checked against a "common sense" filter (e.g., "Is this name longer than 50 chars? Does it contain numbers?").
**Logic**: We need a **Validation Pipeline** that uses strict rules and Named Entity Recognition (NER) to reject invalid data *before* it saves.

### Issue 5: Output Format Wrong
**Root Cause**: The exporter dumps the database schema directly. The client needs a specific business-ready format.
**Logic**: We will implement a "Presentation Layer" that transforms raw database rows into the exact schema requested, handling type conversion, field merging, and validation.

## What Changes

### 1. Architecture Documentation
- **ADD** detailed execution flow diagram in `design.md`.
- **DEFINE** responsibility of every class (e.g., `LegalExtractor` = specialized parsing, `EnhancedCrawler` = orchestration).

### 2. Discovery Strategy Shift (SMB Focus)
- **ADD** `Google/DuckDuckGo` Search Discovery with targeted dorks (e.g., `site:.de "Impressum" "GmbH" -site:facebook.com`).
- **ADD** `CommonCrawl` filtering for low-rank domains (tail-end discovery).
- **ADD** `--company-size` filter to prioritize finding smaller targets.

### 3. Data Quality & Validation Pipeline (The "No Hallucination" Fix)
- **INTEGRATE** `spaCy` (Open Source NLP) or refine `GLiNER` usage for strict Entity Validation.
- **IMPLEMENT** `Validator` class:
  - `validate_person_name(name)`: Rejects names with numbers, addresses, or excessive length.
  - `validate_address(addr)`: Rejects addresses missing zip codes or cities.
  - `validate_legal_form(form)`: Must match known list (GmbH, AG, etc.).
- **REMOVE** fields: `authorized_reps`, `dpo_name`, `dpo_email`, `siret`, `siren`, `trading_name`.

### 4. Unified Export System
- **CREATE** `UnifiedExporter` class.
- **SCHEMA**: Exact match to client request (Corporate Profile, Contact, Location, Service, Social, Metadata).
- **LOGIC**:
  - **Company Size**: Infer from `legal_form` (AG=Enterprise, e.K.=SME) and `employee_count` mentions.
  - **Robots Check**: explicitly track `robots.txt` status during crawl and export it.

## Impact

- **Breaking Changes**:
  - CLI output format completely changes.
  - `legal_entities.csv` structure changes (removed fields).
- **Performance**: Validation adds ~100ms per domain processing time (negligible).
- **Dependencies**: May need `spacy` and `de_core_news_sm` model for better German NLP.

## Plan
See `tasks.md` for the step-by-step implementation plan.
