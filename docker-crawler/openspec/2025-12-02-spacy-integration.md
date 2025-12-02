# Proposal: Integration of spaCy for Intelligent Entity Extraction

## Problem Statement
The current regex-based extraction system has hit a "ceiling" of ~40-50% accuracy. 
- **False Positives**: Extracts "2025" (year) or "0005" (percentage) as postal codes because they match the `\d{4}` pattern.
- **False Negatives**: Misses valid addresses because of strict context windows (e.g., street name too far from postal code).
- **Junk Data**: Extracts "Masseprozent" as a city name.

Regex cannot understand *semantic* context (e.g., knowing that "München" is a city and "Masseprozent" is a unit of measurement).

## Proposed Solution: spaCy Integration
We will incorporate **spaCy**, an industrial-strength Natural Language Processing (NLP) library, directly into the Docker container.

### Why spaCy?
1.  **Named Entity Recognition (NER)**: Can identify `ORG` (Companies), `LOC` (Locations), and `PER` (People) with high accuracy using the `de_core_news_lg` (German large) model.
2.  **Context Awareness**: Understands sentence structure, not just character patterns.
3.  **Open Source & Docker-Friendly**: Easy to install via pip and runs efficiently in containers.

## Implementation Plan

### 1. Docker Updates
- **requirements.txt**: Add `spacy` and `https://github.com/explosion/spacy-models/releases/download/de_core_news_lg-3.7.0/de_core_news_lg-3.7.0.tar.gz`
- **Dockerfile**: Add `RUN python -m spacy download de_core_news_lg` (or install direct via pip to cache it).

### 2. Code Changes (`pipelines.py`)
- Initialize spaCy model on startup (singleton).
- **New Logic**:
    1.  Run regex extraction (as candidates).
    2.  Pass candidates to spaCy for validation:
        - Check if "City" candidate is tagged as `LOC` (Location).
        - Check if "Company Name" candidate is tagged as `ORG` (Organization).
    3.  **Fallback**: If regex fails, use spaCy to find all `LOC` entities and reconstruct address.

### 3. Expected Improvements
- **Eliminate "Masseprozent"**: spaCy knows this is not a location.
- **Fix "2025"**: spaCy knows this is a date, not a location/zip.
- **Better Company Names**: Distinguish "Zooplus AG" from "Contact Us".

## Alternative Tools Researched
- **libpostal**: Gold standard for parsing, but requires complex C-library compilation and 2GB+ model files. Harder to maintain in Docker.
- **Tesseract OCR**: Only useful for image-based Impressums.
- **BERT**: Too slow for CPU-based crawling without GPU.

**Recommendation**: Start with **spaCy** (high impact, medium effort). Move to **libpostal** only if address parsing remains the bottleneck.
