# Spec: Unified Export (Issue #5)

## ADDED Requirements

### Requirement: Unified Exporter Logic
The system SHALL create a `UnifiedExporter` class to join tables and map fields.

#### Scenario: merging legal and enhanced data
Given a domain "example.com" exists in both `results_enhanced` and `legal_entities` tables
When `export_unified` is called
Then `company_name` should be taken from `legal_entities.legal_name`
And `emails` should be taken from `results_enhanced.emails`

#### Scenario: Strict Schema Compliance
Given the exporter runs
Then the output columns MUST match the client's list exactly (Corporate Profile, Contact, Location, etc.)
And fields like `robots_allowed` MUST be present

### Requirement: Company Size Logic
The system SHALL implement a heuristic classifier for company size.

#### Scenario: Classifying an Enterprise
Given a company with legal form "AG"
When `classify_company_size` is called
Then it should return "enterprise"

#### Scenario: Classifying a Solo Business
Given a company with legal form "e.K."
When `classify_company_size` is called
Then it should return "solo"

### Requirement: Robots Tracking
The crawler SHALL explicitly track `robots.txt` status.

#### Scenario: Robots disallowed
Given a domain has `Disallow: /` in robots.txt
When the crawler processes it
Then it should store `robots_allowed=False` in the database
And the export should show `robots_allowed=False`
