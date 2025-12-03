## Context

The gold extraction approach **already exists** in the codebase but is not wired into the main crawler. This design documents how to activate the existing `RobustLegalExtractor` and supporting infrastructure.

## Key Discovery

```python
# WHAT'S RUNNING (broken):
from .legal_extractor import LegalExtractor

# WHAT SHOULD RUN (gold):
from .robust_legal_extractor import RobustLegalExtractor
```

## Existing Infrastructure (Already Built)

```
src/
├── robust_legal_extractor.py    # Multi-pass extraction       ← USE THIS
├── section_extractor.py          # Section isolation           ← ALREADY USED
├── field_validators.py           # Validation (phonenumbers)   ← ALREADY USED
├── country_extractors/
│   ├── german_extractor.py       # DE/AT/CH patterns           ← ALREADY USED
│   ├── uk_extractor.py           # UK patterns                 ← ALREADY USED
│   ├── french_extractor.py       # FR patterns                 ← ALREADY USED
│   └── generic_extractor.py      # Fallback                    ← ALREADY USED
├── whois_enricher.py             # WHOIS lookup                ← KEEP + ADD RDAP
└── enhanced_crawler.py           # Main crawler                ← CHANGE IMPORT
```

---

## RobustLegalExtractor - How It Works (Already Implemented)

### The Three-Pass Architecture

```
RobustLegalExtractor.extract(html, url)
    │
    ├─► Pass 1: _extract_from_structured_data(soup)
    │       Parses JSON-LD <script type="application/ld+json">
    │       Handles @graph arrays
    │       Extracts: legalName, address, vatID, telephone
    │       → If Organization found: HIGH confidence data
    │
    ├─► Pass 2: _extract_from_sections(text, sections, country)
    │       Uses SectionExtractor to isolate legal content
    │       Routes to country-specific extractor:
    │       ├── GermanExtractor (DE, AT, CH)
    │       ├── UKExtractor (GB)
    │       ├── FrenchExtractor (FR)
    │       └── GenericExtractor (fallback)
    │
    └─► Pass 3: _merge_and_validate(structured, section, country)
            Merges results (structured takes priority)
            Validates all fields via FieldValidators
            Calculates confidence score
```

### Existing Code: JSON-LD Extraction (robust_legal_extractor.py lines 71-120)

```python
def _extract_from_structured_data(self, soup: BeautifulSoup) -> Dict:
    """Extract from JSON-LD and other structured data."""
    result = {}
    
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string or '{}')
            
            # Handle @graph format
            if isinstance(data, dict) and '@graph' in data:
                items = data['@graph']
            elif isinstance(data, list):
                items = data
            else:
                items = [data]
                
            for item in items:
                if item.get('@type') in ['Organization', 'Corporation', 'LocalBusiness']:
                    # Company name (with validation!)
                    name = item.get('legalName') or item.get('name')
                    if name:
                        validated = FieldValidators.validate_company_name(name)
                        if validated:
                            result['legal_name'] = validated
                    
                    # VAT ID (with validation!)
                    vat = item.get('vatID') or item.get('taxID')
                    if vat:
                        validated = FieldValidators.validate_vat_id(vat)
                        if validated:
                            result['vat_id'] = validated
                    # ... address, phone, email extraction
        except:
            continue
    return result
```

### Existing Code: German Patterns (german_extractor.py)

```python
PATTERNS = {
    'company_tmg': re.compile(
        r'Angaben\s+gem.{1,3}\s+.{1,2}\s*5\s+TMG[:\s]*\n*'
        r'([A-Za-z\u00C4-\u00FC\s&\-\.]{3,60}(?:GmbH|AG|UG|KG|OHG|GbR|e\.K\.))',
    ),
    'geschaeftsfuehrer': re.compile(
        r'Gesch.ftsf.hr(?:er|ung|erin)?[:\s]+'
        r'([A-Za-z\u00C4-\u00FC\.\-\s,]+?)'
        r'(?:\n|Handelsregister|USt|$)',
    ),
    'hrb': re.compile(r'HRB\s*(\d+)\s*([A-Z])?'),
    'ust_idnr': re.compile(
        r'(?:USt\.?-?Id\.?-?Nr\.?|Umsatzsteuer-?ID)[:\s\.]*'
        r'(DE\s*\d{3}\s*\d{3}\s*\d{3}|DE\s*\d{9})',
    ),
}
```

### Existing Code: Field Validators (field_validators.py)

```python
class FieldValidators:
    VAT_PATTERNS = {
        'DE': r'^DE\d{9}$',
        'AT': r'^ATU\d{8}$',
        'CH': r'^CHE\d{9}(MWST)?$',
        'GB': r'^GB\d{9,12}$',
        'FR': r'^FR[A-Z0-9]{2}\d{9}$',
        # ... 16 countries supported
    }
    
    @classmethod
    def validate_phone(cls, phone: str) -> Optional[str]:
        try:
            parsed = phonenumbers.parse(phone)
            if phonenumbers.is_valid_number(parsed):
                return phonenumbers.format_number(
                    parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
        except:
            pass
        return None
```

**Why This Works**: Schema.org markup is intentionally placed by site owners to describe their business. It's not guesswork - it's authoritative self-description.

---

### 2. DOMAnalyzer (`src/dom_analyzer.py`)

**Purpose**: Extract from structured HTML patterns (key-value pairs)

**Key Patterns**:
```python
GERMAN_LABELS = {
    'Geschäftsführer': 'ceo',
    'Vorstand': 'directors',
    'Handelsregister': 'register',
    'Amtsgericht': 'register_court',
    'USt-IdNr': 'vat_id',
    'Sitz der Gesellschaft': 'registered_address',
}

def extract_definition_lists(self, soup):
    """Parse <dl><dt>Label</dt><dd>Value</dd></dl>"""
    for dl in soup.find_all('dl'):
        pairs = zip(dl.find_all('dt'), dl.find_all('dd'))
        for dt, dd in pairs:
            label = dt.get_text(strip=True)
            value = dd.get_text(strip=True)
            field = self._match_label(label)
            if field:
                yield field, value, 'dom-dl', 0.9

def extract_label_value_patterns(self, soup):
    """Parse 'Label: Value' text patterns"""
    pattern = re.compile(
        r'^(Geschäftsführer|Vorstand|Handelsregister|USt-IdNr|Amtsgericht)'
        r'\s*[:]\s*(.+)$',
        re.MULTILINE
    )
    # ...
```

**Why This Works**: Legal pages are designed for human reading with labeled sections. Deterministic pattern matching on these labels is reliable.

---

### 3. RDAPClient (`src/rdap_client.py`)

**Purpose**: Fetch domain registration data via RDAP (not WHOIS)

**Why RDAP over WHOIS**:
| Aspect | WHOIS | RDAP |
|--------|-------|------|
| Format | Unstructured text | JSON |
| Blocking | Frequent | Rare |
| Standard | Legacy | ICANN-mandated |
| Parsing | Regex nightmare | Direct JSON access |

**Implementation**:
```python
RDAP_BOOTSTRAP = "https://rdap.org"

class RDAPClient:
    async def lookup(self, domain: str) -> dict:
        tld = domain.split('.')[-1]
        rdap_url = f"{RDAP_BOOTSTRAP}/domain/{domain}"
        
        async with aiohttp.ClientSession() as session:
            resp = await session.get(rdap_url)
            data = await resp.json()
            
        return {
            'registrar': self._extract_registrar(data),
            'created': data.get('events', [{}])[0].get('eventDate'),
            'expires': self._find_event(data, 'expiration'),
            'source': 'rdap',
        }
    
    async def fallback_whois(self, domain: str) -> dict:
        """Only if RDAP fails"""
        import whois
        w = whois.whois(domain)
        return {'registrar': w.registrar, 'source': 'whois-fallback'}
```

---

### 4. FieldValidator (`src/field_validator.py`)

**Purpose**: Reject malformed data before storage

**Validation Rules**:

```python
class FieldValidator:
    def validate_company_name(self, name: str, domain: str) -> bool:
        # Must contain legal form OR fuzzy-match domain
        has_form = any(f in name for f in KNOWN_LEGAL_FORMS)
        matches_domain = fuzz.partial_ratio(name.lower(), domain) > 60
        return has_form or matches_domain
    
    def validate_vat(self, vat: str, country: str) -> bool:
        # EU VAT numbers have country-specific checksums
        vat = re.sub(r'[^A-Z0-9]', '', vat.upper())
        if country == 'DE':
            return len(vat) == 11 and vat.startswith('DE')
        # ... other countries
    
    def validate_phone(self, phone: str) -> bool:
        try:
            parsed = phonenumbers.parse(phone, None)
            return phonenumbers.is_valid_number(parsed)
        except:
            return False
    
    def validate_postal_code(self, code: str, country: str) -> bool:
        patterns = {
            'DE': r'^\d{5}$',
            'CH': r'^\d{4}$',
            'AT': r'^\d{4}$',
            'UK': r'^[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}$',
        }
        return bool(re.match(patterns.get(country, r'.*'), code))
    
    def validate_person_name(self, name: str) -> bool:
        # Must be "First Last" pattern, no titles
        words = name.split()
        if len(words) < 2:
            return False
        # Reject if contains title
        titles = ['dr', 'prof', 'herr', 'frau', 'mr', 'ms', 'geschäftsführer']
        return not any(w.lower().rstrip('.') in titles for w in words)
```

---

### 5. TerminalUI (`src/terminal_ui.py`)

**Purpose**: Green hacker-style console output

```python
from colorama import init, Fore, Style, Back
import sys

class TerminalUI:
    def __init__(self):
        init()  # Windows compatibility
        self.green = Fore.GREEN
        self.dim = Style.DIM
        self.reset = Style.RESET_ALL
        
    def banner(self):
        print(f"{self.green}╔══════════════════════════════════════╗")
        print(f"║  LEGAL ENTITY CRAWLER v2.0           ║")
        print(f"║  Deterministic Extraction Engine     ║")
        print(f"╚══════════════════════════════════════╝{self.reset}")
    
    def log(self, level: str, msg: str):
        ts = datetime.now().strftime('%H:%M:%S')
        prefix = {'INFO': '●', 'WARN': '▲', 'ERR': '✖', 'OK': '✔'}
        print(f"{self.green}[{ts}] {prefix.get(level, '●')} {msg}{self.reset}")
    
    def progress(self, current: int, total: int, domain: str):
        bar_len = 30
        filled = int(bar_len * current / total)
        bar = '█' * filled + '░' * (bar_len - filled)
        sys.stdout.write(f"\r{self.green}[{bar}] {current}/{total} | {domain}{self.reset}")
        sys.stdout.flush()
```

---

## CSV Output Schema

```csv
domain,legal_name,legal_name_confidence,legal_name_source,legal_form,address_street,address_zip,address_city,address_country,ceo,directors,register_court,register_number,vat_id,phone,email,rdap_registrar,rdap_created,rdap_expires
example.de,Example GmbH,1.0,json-ld,GmbH,Hauptstraße 1,12345,Berlin,Germany,Max Müller,,Amtsgericht Berlin,HRB 12345,DE123456789,+49 30 1234567,info@example.de,DENIC,2010-01-15,2025-01-15
```

**Key Addition**: `*_confidence` and `*_source` columns for transparency.

---

## What Gets Removed

| Removed | Reason |
|---------|--------|
| GLiNER as default | Non-deterministic, threshold guesswork |
| `python-whois` as primary | Unreliable, inconsistent parsing |
| `_predict_gliner()` calls | Moved to optional `--experimental` |
| Implicit 0.3-0.8 thresholds | Replaced with validation rules |
| `extract_legal_name()` ML path | Now uses structured data first |
