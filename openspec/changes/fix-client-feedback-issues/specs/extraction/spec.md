# Spec: Extraction & Data Quality (Issue #4)

## ADDED Requirements

### Requirement: Strict Validation Layer
The system SHALL implement a `DataValidator` class using `spaCy` to reject garbage data.

#### Scenario: Validating a correct CEO name
Given the extractor finds "Max Mustermann"
When `validate_ceo_name("Max Mustermann")` is called
Then it should return True because it fits the person pattern

#### Scenario: Rejecting an address as CEO
Given the extractor finds "Otto-Ostrowski-Straße 7" as a CEO name
When `validate_ceo_name` is called
Then it should return False because it contains "Straße" and digits

#### Scenario: Validating a correct Address
Given the extractor finds "Musterstraße 1, 12345 Berlin"
When `validate_address` is called
Then it should return True because it has a street, 5-digit ZIP, and valid city

### Requirement: SpaCy Integration
The system SHALL use `spaCy` for Named Entity Recognition.

#### Scenario: Distinguishing Person from Organization
Given a text "Google LLC"
When the NER model processes it
Then it should label it as `ORG`
And NOT as `PER`

## MODIFIED Requirements

### Requirement: Legal Name Cleaning
The `clean_legal_name` function SHALL handle navigation text and irrelevant prefixes.

#### Scenario: Removing navigation menus
Given the legal name candidate is "Home Menu Contact GmbH"
When `clean_legal_name` is called
Then it should reject the string or strip the navigation terms

### Requirement: Representative Extraction
The extraction logic SHALL use NLP to identify person entities correctly.

#### Scenario: Extracting multiple directors
Given the text "Geschäftsführer: Hans Müller und Petra Schmidt"
When extraction runs
Then it should identify "Hans Müller" and "Petra Schmidt" as separate entities
And correctly assign them to the `directors` list

## REMOVED Requirements

### Requirement: Unwanted Fields
The export output SHALL NOT contain fields requested for removal by the client.

#### Scenario: Exporting data
Given the export process runs
Then the output should NOT contain `authorized_reps`
And the output should NOT contain `dpo_name`
And the output should NOT contain `dpo_email`
And the output should NOT contain `siret`
And the output should NOT contain `siren`
And the output should NOT contain `trading_name`
