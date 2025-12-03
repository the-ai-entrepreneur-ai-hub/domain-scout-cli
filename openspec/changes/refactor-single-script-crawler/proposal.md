# Change: Activate the Gold Extraction Pipeline

## Executive Summary

**The gold extraction approach ALREADY EXISTS in the codebase but is NOT being used.**

The `EnhancedCrawler` uses `LegalExtractor` (GLiNER-based, buggy) instead of `RobustLegalExtractor` (structured-data-first, validated). This proposal is about **wiring up existing code**, not building new modules.

---

## The Root Cause

### Current Broken Flow
```python
# enhanced_crawler.py (WHAT'S ACTUALLY RUNNING)
from .legal_extractor import LegalExtractor      # ← WRONG EXTRACTOR
self.legal_extractor = LegalExtractor()

# LegalExtractor problems:
# 1. Removes JSON-LD scripts BEFORE extraction (line 1025)
# 2. Uses GLiNER with threshold=0.3 (too low, line 997)
# 3. GLiNER can override good regex data (line 1095)
```

### The Gold Code That EXISTS But Isn't Used
```python
# robust_legal_extractor.py (ALREADY BUILT!)
class RobustLegalExtractor:
    """
    Extraction Strategy:
    1. Pass 1: Extract from structured data (JSON-LD, Schema.org)
    2. Pass 2: Section-based extraction with country-specific patterns
    3. Pass 3: Merge results and validate all fields
    """
```

### Supporting Infrastructure (ALREADY BUILT)
```
src/
├── robust_legal_extractor.py    # Multi-pass extraction ← EXISTS
├── section_extractor.py          # Section isolation     ← EXISTS
├── field_validators.py           # Validation rules      ← EXISTS
└── country_extractors/
    ├── german_extractor.py       # DE patterns           ← EXISTS
    ├── uk_extractor.py           # UK patterns           ← EXISTS
    ├── french_extractor.py       # FR patterns           ← EXISTS
    └── generic_extractor.py      # Fallback              ← EXISTS
```

---

## The Three Real Problems

### Problem 1: Wrong Extractor Wired
The crawler imports `LegalExtractor` instead of `RobustLegalExtractor`.

**Fix**: One-line change in `enhanced_crawler.py`.

### Problem 2: JSON-LD Destroyed Before Use
```python
# legal_extractor.py line 1025 - THE BUG
for tag in soup(['script', 'style', 'noscript']):
    tag.decompose()  # ← REMOVES JSON-LD SCRIPTS!
```

`RobustLegalExtractor` doesn't have this bug - it extracts JSON-LD FIRST.

### Problem 3: GLiNER Pollutes Results
```python
# legal_extractor.py line 997
entities = self.model.predict_entities(text, labels, threshold=0.3)  # ← TOO LOW

# legal_extractor.py line 1095 - CAN OVERRIDE GOOD DATA
if not result.get('legal_name') or best_org['score'] > 0.7:
    result['legal_name'] = cleaned_gliner_name  # ← OVERWRITES REGEX RESULT
```

`RobustLegalExtractor` has NO GLiNER dependency.

---

## What Changes

### Change 1: Switch Extractor (5 minutes)
```python
# enhanced_crawler.py - BEFORE
from .legal_extractor import LegalExtractor
self.legal_extractor = LegalExtractor()

# enhanced_crawler.py - AFTER
from .robust_legal_extractor import RobustLegalExtractor
self.legal_extractor = RobustLegalExtractor()
```

### Change 2: Verify Output Format Compatibility
The `RobustLegalExtractor` output format must match what `save_results()` expects.

Current `LegalExtractor` returns:
```python
{'legal_name': '...', 'legal_form': '...', 'registered_street': '...', ...}
```

`RobustLegalExtractor` returns:
```python
{'legal_name': '...', 'legal_form': '...', 'street_address': '...', ...}
```

**Fix**: Map field names in `save_results()` or update `RobustLegalExtractor` output keys.

### Change 3: Add RDAP for Domain Registration
Create `src/rdap_client.py`:
```python
RDAP_BOOTSTRAP = "https://rdap.org"

async def lookup_domain(domain: str) -> dict:
    url = f"{RDAP_BOOTSTRAP}/domain/{domain}"
    async with aiohttp.ClientSession() as session:
        resp = await session.get(url)
        data = await resp.json()
        return {
            'registrar': extract_registrar(data),
            'created': extract_date(data, 'registration'),
            'expires': extract_date(data, 'expiration'),
        }
```

Fallback to `python-whois` only if RDAP fails.

### Change 4: Green Terminal UI
Create `src/terminal_ui.py` with colorama-based output.

### Change 5: Keep GLiNER as Optional
Move GLiNER to `--experimental` flag:
```python
# main.py
crawl_parser.add_argument("--experimental-ml", action="store_true",
                          help="Enable GLiNER ML extraction (lower accuracy)")
```

---

## Architecture Comparison

### BEFORE (Broken)
```
Crawl4AI/Playwright ──► HTML
     │
     ├──► EnhancedExtractor ──► general_data (uses JSON-LD ✓)
     │
     └──► LegalExtractor ────► legal_data
              │
              ├── Removes JSON-LD scripts (!)
              ├── Regex extraction
              └── GLiNER at 0.3 threshold (!)
                   └── Can override regex results (!)
```

### AFTER (Gold)
```
Crawl4AI/Playwright ──► HTML
     │
     └──► RobustLegalExtractor ──► all_data
              │
              ├── Pass 1: JSON-LD/Schema.org (100% reliable)
              │      └── If Organization found → DONE
              │
              ├── Pass 2: Country-specific patterns
              │      ├── GermanExtractor (for .de/.at/.ch)
              │      ├── UKExtractor (for .uk)
              │      └── FrenchExtractor (for .fr)
              │
              └── Pass 3: Validate all fields
                     └── FieldValidators.validate_*()
```

---

## Why This Will Work

### The RobustLegalExtractor Already Handles:

1. **JSON-LD Extraction** (`_extract_from_structured_data`):
   - Parses `<script type="application/ld+json">`
   - Handles `@graph` arrays
   - Extracts `legalName`, `address`, `vatID`, `telephone`

2. **Country Detection** (`_detect_country`):
   - TLD-based: `.de` → DE, `.co.uk` → GB
   - Content-based: "impressum" → DE, "companies house" → GB

3. **Country-Specific Patterns**:
   - German: HRB/HRA, Amtsgericht, Geschäftsführer
   - UK: Companies House, Registered in England
   - French: RCS, SIRET, Gérant

4. **Field Validation** (`FieldValidators`):
   - `validate_company_name()` - Rejects noise words
   - `validate_vat_id()` - Country-specific patterns (DE, AT, CH, GB, FR...)
   - `validate_phone()` - Uses phonenumbers library
   - `validate_registration_number()` - HRB format validation

---

## Deliverables

| Item | Status | Action |
|------|--------|--------|
| `robust_legal_extractor.py` | EXISTS | Wire into crawler |
| `country_extractors/*` | EXISTS | Already used by RobustLegalExtractor |
| `field_validators.py` | EXISTS | Already used by RobustLegalExtractor |
| `section_extractor.py` | EXISTS | Already used by RobustLegalExtractor |
| `rdap_client.py` | NEW | Create async RDAP client |
| `terminal_ui.py` | NEW | Create green console output |
| GLiNER integration | DEMOTE | Move to `--experimental-ml` flag |

---

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Output format mismatch | Map field names in `save_results()` |
| Missing edge cases | RobustLegalExtractor has 11k+ lines of patterns |
| RDAP rate limiting | Add 500ms delay, cache results |
| Breaking existing behavior | Keep `--legacy-extractor` flag to use old LegalExtractor |

---

## Success Metrics

1. **Accuracy**: Fewer false positives (no partner companies extracted)
2. **Coverage**: Same or better field extraction rate
3. **Reliability**: Consistent results across runs (no ML randomness)
4. **Performance**: Faster (no model loading)
