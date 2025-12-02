#!/usr/bin/env python3
"""
AGGRESSIVE TEST SUITE FOR DOCKER CRAWLER
Tests extraction accuracy against live websites with zero tolerance for errors.

This test will:
1. Clear database
2. Crawl 10 real domains
3. Verify each extraction against actual website data
4. Report HONEST success/failure rates
"""

import subprocess
import time
import requests
import re
import sys
from typing import Dict, List, Optional
import psycopg2

# Test domains - mix of German and Swiss, known to have Impressum pages
TEST_DOMAINS = [
    "simple-fax.de",      # Known: Salzdahlumer Str. 196, 38126 Braunschweig
    "t3n.de",             # Known: Kriegerstr. 40, 30161 Hannover
    "granatapet.de",      # Known: Wohlmutser Weg 12, 87463 Dietmannsried
    "zooplus.ch",         # Known: Herzog-Wilhelm-Str. 18, 80331 München
    "ceff.ch",            # Known: Rue Baptiste-Savoye 33, 2610 Saint-Imier
    "impo.ch",            # Known: Diesel-Strasse 25, 8404 Winterthur
    "radbag.ch",          # Known: Bahnhofstrasse 10, 9100 Herisau
    "bad-bellingen.de",   # Known: Badstraße 14, 79415 Bad Bellingen
    "mapodo.de",          # Known: Werkstr. 12, 25497 Prisdorf
    "asc-paderborn.de",   # Known: Ahornallee 20, 33106 Paderborn
]

# Ground truth data for verification (manually verified)
GROUND_TRUTH = {
    "simple-fax.de": {
        "street_contains": "Salzdahlumer",
        "postal_code": "38126",
        "city_contains": "Braunschweig",
    },
    "t3n.de": {
        "street_contains": "Krieger",
        "postal_code": "30161",
        "city_contains": "Hannover",
    },
    "granatapet.de": {
        "street_contains": "Wohlmutser",
        "postal_code": "87463",
        "city_contains": "Dietmannsried",
    },
    "zooplus.ch": {
        "street_contains": "Herzog-Wilhelm",
        "postal_code": "80331",
        "city_contains": "München",
    },
    "ceff.ch": {
        "street_contains": "Baptiste-Savoye",
        "postal_code": "2610",
        "city_contains": "Imier",
    },
    "impo.ch": {
        "street_contains": "Diesel",
        "postal_code": "8404",
        "city_contains": "Winterthur",
    },
    "radbag.ch": {
        "street_contains": "Bahnhof",
        "postal_code": "9100",
        "city_contains": "Herisau",
    },
    "bad-bellingen.de": {
        "street_contains": "Badstra",
        "postal_code": "79415",
        "city_contains": "Bellingen",
    },
    "mapodo.de": {
        "street_contains": "Werkstr",
        "postal_code": "25497",
        "city_contains": "Prisdorf",
    },
    "asc-paderborn.de": {
        "street_contains": "Ahornallee",
        "postal_code": "33106",
        "city_contains": "Paderborn",
    },
}


class TestResult:
    def __init__(self, domain: str):
        self.domain = domain
        self.crawled = False
        self.extracted = False
        self.street_correct = False
        self.postal_correct = False
        self.city_correct = False
        self.errors: List[str] = []
        self.extracted_data: Dict = {}
        self.expected_data: Dict = {}


def run_command(cmd: str, timeout: int = 300) -> tuple:
    """Run shell command and return output"""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"


def clear_database():
    """Clear the results table"""
    print("\n" + "="*70)
    print("STEP 1: CLEARING DATABASE (AND UPDATING SCHEMA)")
    print("="*70)
    
    # First command: Ensure table exists (basic)
    run_command(
        'cd /d D:\\docker-crawler && docker-compose exec -T postgres psql -U crawler -d crawler -c "CREATE TABLE IF NOT EXISTS results (id SERIAL PRIMARY KEY, domain VARCHAR(255) NOT NULL, url TEXT, extracted_text TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE(domain, url));"'
    )
    
    # Second command: Update schema with new columns
    alter_cmds = [
        "ALTER TABLE results ADD COLUMN IF NOT EXISTS company_name TEXT;",
        "ALTER TABLE results ADD COLUMN IF NOT EXISTS legal_form VARCHAR(100);",
        "ALTER TABLE results ADD COLUMN IF NOT EXISTS street TEXT;",
        "ALTER TABLE results ADD COLUMN IF NOT EXISTS postal_code VARCHAR(20);",
        "ALTER TABLE results ADD COLUMN IF NOT EXISTS city VARCHAR(255);",
        "ALTER TABLE results ADD COLUMN IF NOT EXISTS country VARCHAR(100);",
        "ALTER TABLE results ADD COLUMN IF NOT EXISTS ceo_names TEXT;",
        "ALTER TABLE results ADD COLUMN IF NOT EXISTS emails TEXT;",
        "ALTER TABLE results ADD COLUMN IF NOT EXISTS phone_numbers TEXT;",
        "ALTER TABLE results ADD COLUMN IF NOT EXISTS fax_numbers TEXT;",
        "ALTER TABLE results ADD COLUMN IF NOT EXISTS registration_number VARCHAR(100);",
        "ALTER TABLE results ADD COLUMN IF NOT EXISTS vat_id VARCHAR(100);",
        "ALTER TABLE results ADD COLUMN IF NOT EXISTS owner_organization TEXT;",
        "ALTER TABLE results ADD COLUMN IF NOT EXISTS industry TEXT;",
        "ALTER TABLE results ADD COLUMN IF NOT EXISTS company_size VARCHAR(50);",
        "ALTER TABLE results ADD COLUMN IF NOT EXISTS service_product_description TEXT;",
        "ALTER TABLE results ADD COLUMN IF NOT EXISTS social_links TEXT;",
        "ALTER TABLE results ADD COLUMN IF NOT EXISTS raw_html TEXT;",
        "ALTER TABLE results ADD COLUMN IF NOT EXISTS whois_registrar TEXT;",
        "ALTER TABLE results ADD COLUMN IF NOT EXISTS whois_creation_date VARCHAR(50);",
        "ALTER TABLE results ADD COLUMN IF NOT EXISTS whois_expiration_date VARCHAR(50);",
        "ALTER TABLE results ADD COLUMN IF NOT EXISTS whois_owner TEXT;",
        "ALTER TABLE results ADD COLUMN IF NOT EXISTS whois_emails TEXT;"
    ]
    
    for cmd in alter_cmds:
        run_command(
            f'cd /d D:\\docker-crawler && docker-compose exec -T postgres psql -U crawler -d crawler -c "{cmd}"'
        )
    
    # Now truncate
    code, out, err = run_command(
        'cd /d D:\\docker-crawler && docker-compose exec -T postgres psql -U crawler -d crawler -c "TRUNCATE TABLE results;"'
    )
    
    if code == 0:
        print("[OK] Database cleared and schema updated successfully")
        return True
    else:
        print(f"[FAIL] Failed to clear/update database: {err}")
        return False


def create_test_domains_file():
    """Create domains file for testing"""
    print("\n" + "="*70)
    print("STEP 2: CREATING TEST DOMAINS FILE")
    print("="*70)
    
    with open("D:\\docker-crawler\\test_domains.txt", "w") as f:
        for domain in TEST_DOMAINS:
            f.write(domain + "\n")
    
    print(f"[OK] Created test_domains.txt with {len(TEST_DOMAINS)} domains:")
    for d in TEST_DOMAINS:
        print(f"  - {d}")
    return True


def run_crawler():
    """Run the Scrapy crawler"""
    print("\n" + "="*70)
    print("STEP 3: RUNNING DOCKER CRAWLER")
    print("="*70)
    
    start_time = time.time()
    
    cmd = 'cd /d D:\\docker-crawler && docker-compose run --rm -v "D:\\docker-crawler\\test_domains.txt:/app/test_domains.txt" crawler scrapy crawl robust -a domains_file=/app/test_domains.txt'
    
    print(f"Command: {cmd[:80]}...")
    print("Running... (this may take 2-3 minutes)")
    
    code, out, err = run_command(cmd, timeout=300)
    
    elapsed = time.time() - start_time
    print(f"\nCrawl completed in {elapsed:.1f} seconds")
    
    # Parse stats from output
    if "item_scraped_count" in (out + err):
        match = re.search(r"'item_scraped_count': (\d+)", out + err)
        if match:
            print(f"[OK] Items scraped: {match.group(1)}")
    
    return code == 0 or "Spider closed" in (out + err)


def get_results_from_db() -> List[Dict]:
    """Fetch results from PostgreSQL"""
    print("\n" + "="*70)
    print("STEP 4: FETCHING RESULTS FROM DATABASE")
    print("="*70)
    
    try:
        conn = psycopg2.connect(
            host="localhost",
            port=5433,
            database="crawler",
            user="crawler",
            password="crawler123"
        )
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT DISTINCT ON (domain) 
                domain, company_name, street, postal_code, city, country, emails, phone_numbers, whois_registrar
            FROM results 
            WHERE street IS NOT NULL OR postal_code IS NOT NULL
            ORDER BY domain, id
        """)
        
        columns = ['domain', 'company_name', 'street', 'postal_code', 'city', 'country', 'emails', 'phones', 'whois_registrar']
        results = []
        for row in cursor.fetchall():
            results.append(dict(zip(columns, row)))
        
        cursor.close()
        conn.close()
        
        print(f"[OK] Found {len(results)} unique domain results with address data")
        return results
        
    except Exception as e:
        print(f"[FAIL] Database error: {e}")
        print("  Make sure PostgreSQL is running on port 5433")
        return []


def verify_extraction(domain: str, extracted: Dict, expected: Dict) -> TestResult:
    """Verify extracted data against ground truth"""
    result = TestResult(domain)
    result.extracted_data = extracted
    result.expected_data = expected
    result.crawled = True
    result.extracted = bool(extracted.get('street') or extracted.get('postal_code'))
    
    if not result.extracted:
        result.errors.append("No address data extracted")
        return result
    
    # Check street
    street = extracted.get('street', '') or ''
    if expected.get('street_contains'):
        if expected['street_contains'].lower() in street.lower():
            result.street_correct = True
        else:
            result.errors.append(f"Street mismatch: expected '{expected['street_contains']}' in '{street}'")
    
    # Check postal code
    postal = str(extracted.get('postal_code', '') or '')
    if expected.get('postal_code'):
        if expected['postal_code'] in postal:
            result.postal_correct = True
        else:
            result.errors.append(f"Postal mismatch: expected '{expected['postal_code']}', got '{postal}'")
    
    # Check city
    city = extracted.get('city', '') or ''
    if expected.get('city_contains'):
        # Case-insensitive partial match
        if expected['city_contains'].lower() in city.lower():
            result.city_correct = True
        else:
            result.errors.append(f"City mismatch: expected '{expected['city_contains']}' in '{city}'")
    
    return result


def run_aggressive_tests():
    """Main test runner"""
    print("\n" + "="*70)
    print("AGGRESSIVE DOCKER CRAWLER TEST SUITE")
    print("="*70)
    print(f"Testing {len(TEST_DOMAINS)} domains against ground truth data")
    print("NO LIES. NO FABRICATION. HONEST RESULTS ONLY.")
    print("="*70)
    
    # Step 1: Clear database
    if not clear_database():
        print("FATAL: Cannot clear database. Aborting.")
        return
    
    # Step 2: Create domains file
    if not create_test_domains_file():
        print("FATAL: Cannot create domains file. Aborting.")
        return
    
    # Step 3: Run crawler
    start_time = time.time()
    if not run_crawler():
        print("WARNING: Crawler may have had issues, checking results anyway...")
    crawl_time = time.time() - start_time
    
    # Step 4: Get results
    results = get_results_from_db()
    
    # Step 5: Verify each domain
    print("\n" + "="*70)
    print("STEP 5: VERIFICATION AGAINST GROUND TRUTH")
    print("="*70)
    
    test_results: List[TestResult] = []
    
    for domain in TEST_DOMAINS:
        # Find extracted data for this domain
        extracted = {}
        for r in results:
            if r['domain'] == domain or domain in r['domain']:
                extracted = r
                break
        
        expected = GROUND_TRUTH.get(domain, {})
        result = verify_extraction(domain, extracted, expected)
        test_results.append(result)
        
        # Print result
        status = "[PASS]" if (result.street_correct and result.postal_correct and result.city_correct) else "[FAIL]"
        print(f"\n{status} {domain}")
        
        if extracted:
            street = extracted.get('street') or 'N/A'
            postal = extracted.get('postal_code') or 'N/A'
            city = extracted.get('city') or 'N/A'
            registrar = extracted.get('whois_registrar') or 'N/A'
            print(f"   Extracted: {str(street)[:50]}")
            print(f"   Postal:    {postal}")
            print(f"   City:      {str(city)[:30]}")
            print(f"   Registrar: {str(registrar)[:30]}")
        else:
            print(f"   NO DATA EXTRACTED")
        
        if result.errors:
            for err in result.errors:
                print(f"   ERROR: {err}")
    
    # Step 6: Summary
    print("\n" + "="*70)
    print("FINAL RESULTS - HONEST ASSESSMENT")
    print("="*70)
    
    total = len(test_results)
    crawled = sum(1 for r in test_results if r.crawled)
    extracted = sum(1 for r in test_results if r.extracted)
    street_ok = sum(1 for r in test_results if r.street_correct)
    postal_ok = sum(1 for r in test_results if r.postal_correct)
    city_ok = sum(1 for r in test_results if r.city_correct)
    fully_correct = sum(1 for r in test_results if r.street_correct and r.postal_correct and r.city_correct)
    
    print(f"""
CRAWL METRICS:
  Total domains:        {total}
  Crawled:              {crawled} ({crawled/total*100:.1f}%)
  Extracted data:       {extracted} ({extracted/total*100:.1f}%)
  
ACCURACY METRICS:
  Street correct:       {street_ok}/{total} ({street_ok/total*100:.1f}%)
  Postal code correct:  {postal_ok}/{total} ({postal_ok/total*100:.1f}%)
  City correct:         {city_ok}/{total} ({city_ok/total*100:.1f}%)
  
OVERALL:
  Fully correct:        {fully_correct}/{total} ({fully_correct/total*100:.1f}%)
  Failure rate:         {total-fully_correct}/{total} ({(total-fully_correct)/total*100:.1f}%)
  
PERFORMANCE:
  Crawl time:           {crawl_time:.1f} seconds
  Speed:                {total/crawl_time*60:.1f} domains/minute
""")
    
    # Verdict
    print("="*70)
    if fully_correct >= 7:
        print("VERDICT: GOOD - System is working well (70%+ accuracy)")
    elif fully_correct >= 5:
        print("VERDICT: ACCEPTABLE - System needs improvement (50%+ accuracy)")
    else:
        print("VERDICT: POOR - System needs significant work (<50% accuracy)")
    print("="*70)
    
    # List failures
    failures = [r for r in test_results if not (r.street_correct and r.postal_correct and r.city_correct)]
    if failures:
        print("\nFAILED DOMAINS:")
        for r in failures:
            print(f"  - {r.domain}: {', '.join(r.errors) if r.errors else 'Unknown error'}")
    
    return test_results


if __name__ == "__main__":
    try:
        run_aggressive_tests()
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()
