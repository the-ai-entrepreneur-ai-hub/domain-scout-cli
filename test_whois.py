import asyncio
from src.whois_enricher import WhoisEnricher

def main():
    enricher = WhoisEnricher()
    # Test with domains that definitely have WHOIS info
    domains = ["peek-cloppenburg.at", "google.com", "tuwien.ac.at"]
    
    for d in domains:
        print(f"\n--- WHOIS Lookup: {d} ---")
        data = enricher.get_whois_data(d)
        print("Registrant Name:", data.get('registrant_name'))
        print("Registrant Address:", data.get('registrant_address'))
        print("Raw Length:", len(data.get('raw_whois', '')))

if __name__ == "__main__":
    main()
