# Tasks: Fix Client Feedback Issues

## Phase 1: Architecture & Discovery (Issue 1 & 2)
- [ ] 1.1 Update `design.md` with new pipeline diagram. (Done in spec)
- [ ] 1.2 Implement `ingest_targeted_search` in `discovery.py` (DuckDuckGo with dorks).
- [ ] 1.3 Implement `CommonCrawl` inverse-popularity filter (SMB finding).
- [ ] 1.4 Add `--company-size` CLI argument to `main.py`.

## Phase 2: Data Quality & Validation (Issue 4)
- [ ] 2.1 Create `src/validator.py` with `DataValidator` class.
- [ ] 2.2 Integrate `spaCy` for German NER (update `requirements.txt`).
- [ ] 2.3 Implement strict `validate_legal_name` (Reject garbage, nav menus).
- [ ] 2.4 Implement strict `validate_ceo_name` (Reject addresses, numbers).
- [ ] 2.5 Implement strict `validate_address` (Require ZIP+City match).
- [ ] 2.6 Update `LegalExtractor` to use `DataValidator` before returning results.
- [ ] 2.7 Remove deprecated fields (`authorized_reps`, `dpo_*`, etc.) from Extractor.

## Phase 3: Unified Export (Issue 3 & 5)
- [ ] 3.1 Update `EnhancedCrawler` to check and store `robots.txt` status.
- [ ] 3.2 Create `src/exporters/unified.py` (Refactor storage logic).
- [ ] 3.3 Implement `classify_company_size` logic.
- [ ] 3.4 Implement `export_unified` function matching strict schema.
- [ ] 3.5 Add `export --unified` command to `main.py`.

## Phase 4: Verification
- [ ] 4.1 Run `pytest` on new Validator logic.
- [ ] 4.2 Run a "SMB Discovery" crawl (limit 50) and verify domain quality.
- [ ] 4.3 Export unified CSV and manually verify columns match Client Spec exactly.
- [ ] 4.4 Verify no "garbage" (addresses in name fields) exists in output.
