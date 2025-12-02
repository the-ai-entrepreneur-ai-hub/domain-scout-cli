#!/usr/bin/env python3
"""
Export Clean Records - Filters out garbage and exports valid business data
Usage: python export_clean.py [input_file]
"""
import csv
import os
import sys
from datetime import datetime

# ANSI Colors
GREEN = '\033[92m'
CYAN = '\033[96m'
YELLOW = '\033[93m'
END = '\033[0m'

# Garbage patterns to filter out
GARBAGE_PATTERNS = [
    'menu', 'menü', 'schließen', 'hauptinhalt', 'cookies', 'newsletter', 
    'navigation', 'top marken', 'versandkostenfrei', 'zum hauptinhalt', 
    'keine zusatzkosten', 'domains', 'systemanforderungen', 'warum', 
    'warenkorb', 'suche', 'kontakt', 'impressum', 'datenschutz',
    'agb', 'widerrufsrecht', 'versand', 'zahlung', 'skip to', 'jump to',
    'toggle', 'close', 'open menu', 'search', 'cart', 'login', 'register'
]

def is_clean(row):
    """Check if a record is clean (not garbage)"""
    company = row.get('company_name', '').strip().lower()
    
    # Must have company name
    if not company:
        return False
    
    # Must have at least city or postal code
    if not row.get('city', '').strip() and not row.get('postal_code', '').strip():
        return False
    
    # Filter out garbage patterns
    for pattern in GARBAGE_PATTERNS:
        if pattern in company:
            return False
    
    # Filter out very short names (likely garbage)
    if len(company) < 3:
        return False
    
    return True

def main():
    # Input file
    input_file = sys.argv[1] if len(sys.argv) > 1 else '/app/data/results.csv'
    
    # Check if running locally (Windows path)
    if not os.path.exists(input_file):
        local_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'results.csv')
        if os.path.exists(local_path):
            input_file = local_path
    
    if not os.path.exists(input_file):
        print(f"{YELLOW}[!] Input file not found: {input_file}{END}")
        sys.exit(1)
    
    # Read input
    with open(input_file, 'r', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    
    # Filter clean records
    clean_rows = [r for r in rows if is_clean(r)]
    
    # Output columns (most useful fields)
    output_fields = [
        'domain', 'company_name', 'legal_form', 'street', 'postal_code', 
        'city', 'country', 'phone_numbers', 'emails', 'vat_id', 
        'registration_number', 'ceo_names'
    ]
    
    # Generate output filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = os.path.dirname(input_file)
    output_file = os.path.join(output_dir, f'clean_leads_{timestamp}.csv')
    
    # Write clean records
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=output_fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(clean_rows)
    
    # Print summary
    print(f"\n{GREEN}=== Clean Export Complete ==={END}")
    print(f"  Input:  {len(rows)} total records")
    print(f"  Output: {CYAN}{len(clean_rows)}{END} clean records ({len(clean_rows)/len(rows)*100:.1f}%)")
    print(f"  File:   {GREEN}{output_file}{END}\n")

if __name__ == '__main__':
    main()
