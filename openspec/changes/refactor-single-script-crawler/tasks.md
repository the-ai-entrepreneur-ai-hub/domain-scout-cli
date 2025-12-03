# Implementation Tasks: Activate Gold Extraction Pipeline

## Key Insight

Most infrastructure ALREADY EXISTS. Primary work is **wiring and integration**.

---

## Phase 1: Switch Extractor (30 minutes)

### 1.1 Change Import in EnhancedCrawler
- [ ] Edit `src/enhanced_crawler.py` line 26
  ```python
  # BEFORE:
  from .legal_extractor import LegalExtractor
  # AFTER:
  from .robust_legal_extractor import RobustLegalExtractor
  ```

- [ ] Edit `src/enhanced_crawler.py` line 46
  ```python
  # BEFORE:
  self.legal_extractor = LegalExtractor()
  # AFTER:
  self.legal_extractor = RobustLegalExtractor()
  ```

### 1.2 Verify Output Format Compatibility
- [ ] Compare `LegalExtractor.extract()` output keys vs `RobustLegalExtractor.extract()` output keys
- [ ] Map field names if needed:
  - `registered_street` ↔ `street_address`
  - `registered_zip` ↔ `postal_code`
  - `registered_city` ↔ `city`
- [ ] Update `save_results()` in `enhanced_crawler.py` to handle both formats

### 1.3 Test Basic Functionality
- [ ] Run: `python main.py crawl --limit 5`
- [ ] Verify extraction completes without errors
- [ ] Check CSV output has data

---

## Phase 2: RDAP Integration (1 hour)

### 2.1 Create RDAP Client
- [ ] Create `src/rdap_client.py`:
  ```python
  import aiohttp
  
  RDAP_BOOTSTRAP = "https://rdap.org"
  
  async def lookup_domain(domain: str) -> dict:
      url = f"{RDAP_BOOTSTRAP}/domain/{domain}"
      async with aiohttp.ClientSession() as session:
          try:
              resp = await session.get(url, timeout=10)
              if resp.status == 200:
                  data = await resp.json()
                  return parse_rdap_response(data)
          except:
              pass
      return {}
  ```

### 2.2 Integrate with WhoisEnricher
- [ ] Modify `src/whois_enricher.py` to try RDAP first
- [ ] Fall back to python-whois if RDAP fails
- [ ] Add `source: 'rdap'` or `source: 'whois'` to output

---

## Phase 3: Green Terminal UI (1 hour)

### 3.1 Create Terminal UI Module
- [ ] Create `src/terminal_ui.py` with colorama:
  ```python
  from colorama import init, Fore, Style
  
  class TerminalUI:
      def __init__(self):
          init()
          self.green = Fore.GREEN
          self.reset = Style.RESET_ALL
      
      def banner(self):
          print(f"{self.green}╔═══════════════════════════════════╗")
          print(f"║  LEGAL ENTITY CRAWLER v2.0        ║")
          print(f"╚═══════════════════════════════════╝{self.reset}")
  ```

### 3.2 Integrate with EnhancedCrawler
- [ ] Import TerminalUI in enhanced_crawler.py
- [ ] Call `ui.banner()` at start of run
- [ ] Replace logger calls with `ui.log()` for key events

---

## Phase 4: CLI and Legacy Support (30 minutes)

### 4.1 Add CLI Flags
- [ ] Add `--experimental-ml` flag to main.py for GLiNER (currently broken, keep as escape hatch)
- [ ] Add `--legacy-extractor` flag to use old LegalExtractor
- [ ] Update help text

### 4.2 Legacy Mode Implementation
- [ ] In EnhancedCrawler.__init__(), check for legacy flag
- [ ] If legacy: use LegalExtractor, else: use RobustLegalExtractor

---

## Phase 5: Testing and Validation (1 hour)

### 5.1 Comparison Test
- [ ] Run old extractor on 20 domains, save results
- [ ] Run new extractor on same 20 domains, save results
- [ ] Compare: accuracy, false positives, missing fields

### 5.2 Specific Test Cases
- [ ] Test domain with JSON-LD Organization data
- [ ] Test German Impressum page (HRB, Geschäftsführer)
- [ ] Test UK company page (Companies House number)
- [ ] Test page with partner/agency section (should NOT extract partner name)

### 5.3 Performance Test
- [ ] Measure extraction time without GLiNER model loading
- [ ] Expected: 2-3x faster per page

---

## Summary: What's NEW vs What EXISTS

| Component | Status | Work Needed |
|-----------|--------|-------------|
| RobustLegalExtractor | **EXISTS** | Wire into crawler |
| GermanExtractor | **EXISTS** | None |
| UKExtractor | **EXISTS** | None |
| FrenchExtractor | **EXISTS** | None |
| FieldValidators | **EXISTS** | None |
| SectionExtractor | **EXISTS** | None |
| RDAP Client | **NEW** | Create (~50 lines) |
| Terminal UI | **NEW** | Create (~100 lines) |
| CLI flags | **UPDATE** | Add 2 flags |
| Output format mapping | **UPDATE** | Map field names |

---

## Estimated Time

| Phase | Time |
|-------|------|
| Phase 1: Switch Extractor | 30 min |
| Phase 2: RDAP Integration | 1 hour |
| Phase 3: Green Terminal UI | 1 hour |
| Phase 4: CLI and Legacy | 30 min |
| Phase 5: Testing | 1 hour |
| **Total** | **4 hours** |

---

## Dependencies

**Already Installed:**
- beautifulsoup4, lxml
- phonenumbers  
- python-whois

**Need to Add:**
- aiohttp (for RDAP)
- colorama (for green terminal)

**Can Remove from Default (reduce install size):**
- gliner
- torch
