import requests
import json
import csv
import os
import time
import random
import re
import argparse
from urllib.parse import urlparse, parse_qs, unquote
from bs4 import BeautifulSoup

# Configuration
DOMAINS_FILE = '/app/domains_full.txt'
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
]

def get_headers():
    return {'User-Agent': random.choice(USER_AGENTS)}

def load_existing_domains():
    if not os.path.exists(DOMAINS_FILE):
        return set()
    with open(DOMAINS_FILE, 'r', encoding='utf-8') as f:
        return set(line.strip().lower() for line in f if line.strip())

def save_domains(domains):
    existing = load_existing_domains()
    new_domains = domains - existing
    
    if not new_domains:
        print("No new domains to add.")
        return 0
        
    with open(DOMAINS_FILE, 'a', encoding='utf-8') as f:
        for domain in sorted(new_domains):
            f.write(f"{domain}\n")
            
    print(f"Added {len(new_domains)} new domains to {DOMAINS_FILE}")
    return len(new_domains)

def discover_crtsh(tld, limit=500):
    """Query Certificate Transparency logs via crt.sh"""
    print(f"[*] Querying crt.sh for *.{tld}...")
    url = f"https://crt.sh/?q=%.{tld}&output=json"
    found = set()
    
    try:
        resp = requests.get(url, headers=get_headers(), timeout=60)
        if resp.status_code != 200:
            print(f"[-] crt.sh failed with {resp.status_code}")
            return found
            
        data = resp.json()
        for entry in data:
            name = entry.get('name_value', '').lower()
            for part in name.split('\n'):
                part = part.strip().lstrip('*.')
                if part.endswith(f".{tld}") and '@' not in part:
                    found.add(part)
                    if len(found) >= limit:
                        return found
    except Exception as e:
        print(f"[-] crt.sh error: {e}")
        
    print(f"[+] crt.sh found {len(found)} domains")
    return found

def discover_ddg(tld, limit=100):
    """Query DuckDuckGo HTML for Imprint pages"""
    print(f"[*] Querying DuckDuckGo for *.{tld}...")
    dorks = [
        f'site:.{tld} "Impressum" "GmbH"',
        f'site:.{tld} "Impressum" "Kontakt" "Telefon"',
        f'site:.{tld} "Legal Notice" "VAT"',
        f'site:.{tld} "Handelsregister" "Amtsgericht"',
    ]
    
    found = set()
    
    for dork in dorks:
        if len(found) >= limit:
            break
            
        print(f"[*] Running dork: {dork}")
        try:
            resp = requests.get(
                "https://duckduckgo.com/html/",
                params={'q': dork, 'kl': f'de-de' if tld in ['de', 'ch', 'at'] else 'us-en'},
                headers=get_headers(),
                timeout=30
            )
            
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'lxml')
                for a in soup.select('.result__a'):
                    href = a.get('href')
                    if href:
                        # Handle DDG redirects
                        if '/l/?kh=-1&uddg=' in href:
                            href = unquote(href.split('uddg=')[1])
                        
                        domain = urlparse(href).netloc.lower()
                        if domain.endswith(f".{tld}"):
                            found.add(domain)
            
            time.sleep(random.uniform(2, 5))
            
        except Exception as e:
            print(f"[-] DDG error: {e}")
            
    print(f"[+] DuckDuckGo found {len(found)} domains")
    return found

def main():
    parser = argparse.ArgumentParser(description="Automatic Domain Discovery")
    parser.add_argument("--tld", type=str, required=True, help="Top Level Domain (e.g. de, ch, com)")
    parser.add_argument("--limit", type=int, default=500, help="Target number of domains")
    args = parser.parse_args()
    
    tld = args.tld.lstrip('.')
    all_domains = set()
    
    # 1. CRT.SH (Fastest, Bulk)
    all_domains.update(discover_crtsh(tld, args.limit))
    
    # 2. DDG (Targeted, Slower)
    if len(all_domains) < args.limit:
        remaining = args.limit - len(all_domains)
        all_domains.update(discover_ddg(tld, remaining))
        
    # Save results
    save_domains(all_domains)

if __name__ == "__main__":
    main()
