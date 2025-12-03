## ADDED Requirements

### Requirement: Deterministic Extraction Pipeline
The system SHALL extract data using a strict priority hierarchy, preferring structured data over heuristics.

#### Scenario: Extraction Priority
- **GIVEN** an HTML page is fetched
- **WHEN** the extraction pipeline runs
- **THEN** it SHALL attempt sources in this order:
  1. JSON-LD `@type:Organization` (confidence: 1.0)
  2. Microdata `itemtype=Organization` (confidence: 1.0)
  3. DOM patterns `<dl>/<dt>/<dd>`, `Label: Value` (confidence: 0.9)
  4. Validated regex patterns (confidence: 0.8)
- **AND** stop at the first tier that yields valid data
- **AND** ML extraction SHALL only run if `--experimental` flag is passed

### Requirement: Per-Field Validation
The system SHALL NOT store any field that fails format validation.

#### Scenario: Field Validation Rules
- **WHEN** a field is extracted
- **THEN** it MUST pass the corresponding validation:

| Field | Validation |
|-------|------------|
| Company Name | Contains legal form OR fuzzy-matches domain (>60%) |
| Legal Form | Exact match in `KNOWN_LEGAL_FORMS[country]` |
| Postal Address | Valid postal code format for detected country |
| Representatives | Matches "First Last" pattern, no titles |
| Phone | `phonenumbers.is_valid_number()` returns True |
| Email | Valid format AND domain has MX record |
| Register Number | Matches country format (DE: `HRB \d{1,6}`) |
| VAT ID | Valid format AND passes checksum (if applicable) |

### Requirement: RDAP Domain Lookup (Primary)
The system SHALL use RDAP as the primary source for domain registration data.

#### Scenario: Domain Registration Lookup
- **WHEN** a domain is queued for processing
- **THEN** the system queries `https://rdap.org/domain/{domain}`
- **AND** extracts: registrar, creation date, expiration date
- **IF** RDAP fails (timeout, 404, rate limit)
- **THEN** fallback to `python-whois` with 5-second timeout
- **AND** mark source as `whois-fallback` in output

### Requirement: Six Legal Fields Extraction
The system SHALL extract these 6 specific fields from legal/impressum pages:

#### Scenario: Required Legal Fields
- **WHEN** processing a legal notice page
- **THEN** the system SHALL attempt to extract:

1. **Company Name**: Legal entity name with form (e.g., "Example GmbH")
   - Source priority: JSON-LD `legalName` > Microdata `name` > DOM pattern > Regex
   - Validation: Contains known legal form OR matches domain name

2. **Legal Form**: Company type abbreviation
   - Valid values: GmbH, AG, KG, UG, Ltd, Inc, LLC, SA, SARL, etc.
   - Must be exact match from country-specific list

3. **Postal Address**: Street, ZIP, City, Country
   - ZIP validation per country (DE: 5 digits, CH: 4 digits, UK: alphanumeric)
   - Street must contain number OR named location

4. **Authorized Representatives**: CEO/Director names
   - Must be valid person names (First Last format)
   - Strip titles (Dr., Prof., Herr, Frau)

5. **Contact Information**: Phone and Email
   - Phone: Must pass `phonenumbers.is_valid_number()`
   - Email: Valid format, domain must resolve

6. **Register Details**: Court name and registration number
   - Format: "Amtsgericht {City}, HRB {number}" (Germany)
   - Country-specific validation (UK: Companies House number)

### Requirement: Confidence and Source Tracking
Every extracted field SHALL carry metadata about its origin.

#### Scenario: Output Transparency
- **WHEN** data is written to CSV
- **THEN** each primary field has companion columns:
  - `{field}_confidence`: Float 0.0-1.0
  - `{field}_source`: One of `json-ld`, `microdata`, `dom-pattern`, `regex`, `ml-experimental`

### Requirement: Green Terminal UI
The system SHALL display output in "hacker-style" green terminal format.

#### Scenario: Visual Output
- **WHEN** `python main.py` is executed
- **THEN** all terminal output uses green text (`colorama.Fore.GREEN`)
- **AND** displays startup banner with version
- **AND** shows progress bar during crawl
- **AND** logs include timestamps in `[HH:MM:SS]` format

### Requirement: Single Script Execution
The system SHALL run entirely from `python main.py` without Docker.

#### Scenario: Standalone Execution
- **WHEN** user runs `python main.py --seed domains.txt`
- **THEN** the crawler runs in the current process
- **AND** uses `asyncio` for concurrent HTTP requests
- **AND** outputs results to `data/legal_entities_final.csv`

## MODIFIED Requirements

### Requirement: Reduced ML Dependency
GLiNER and ML-based extraction SHALL be opt-in only.

#### Scenario: Experimental Mode
- **GIVEN** user wants ML-assisted extraction
- **WHEN** running `python main.py --experimental`
- **THEN** GLiNER predictions are added as fallback tier
- **AND** all ML-extracted fields are marked with `source: ml-experimental`
- **AND** confidence is capped at 0.5 for ML fields

### Requirement: Docker as Optional Wrapper
Docker SHALL wrap the same `main.py` without behavior changes.

#### Scenario: Docker Parity
- **WHEN** running via Docker
- **THEN** behavior is identical to local execution
- **AND** no additional services are required (no redis, no celery)
