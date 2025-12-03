# Spec: Discovery Improvements for SMBs (Issue #2)

## MODIFIED Requirements

### Requirement: Targeted Search Discovery (New Source)
The system SHALL actively search for legal pages of German companies using dorks to find SMBs.

#### Scenario: Finding a local bakery
Given the crawler is started with `--company-size smb`
When the discovery module runs
Then it should execute a search query `"Impressum" "GmbH" site:.de`
And it should parse the results to extract domains
And it should filter out domains present in the Global Giant Blacklist (e.g., facebook.com)

#### Scenario: Finding a law firm
Given the crawler needs more targets
When the search source is active
Then it should iterate through industry keywords (e.g., "Rechtsanwalt", "Handwerk")
And extract valid domains from the search results

### Requirement: CommonCrawl Tail Filtering
The system SHALL filter for domains that are *NOT* in the Tranco Top 1M list.

#### Scenario: Ignoring popular domains
Given CommonCrawl returns "google.com" and "baeckerei-schmidt.de"
And "google.com" is in the Tranco Top 1M list
Then "google.com" should be discarded
And "baeckerei-schmidt.de" should be added to the queue

## ADDED Requirements

### Requirement: Company Size Filter
The CLI SHALL support a `--company-size` argument to prioritize finding smaller targets.

#### Scenario: User selects SMB mode
Given the user runs `python main.py discover --company-size smb`
Then the system should prioritize `targeted_search` source
And it should SKIP domains found in the `majestic_million` top 10k list
