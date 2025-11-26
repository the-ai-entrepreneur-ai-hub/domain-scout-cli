"""
Test script for robust legal extraction (v4.0).
Tests the multi-pass extraction on real German domains.
"""
import asyncio
import httpx
from src.robust_legal_extractor import RobustLegalExtractor
from src.enhanced_storage import save_robust_legal_entity, export_robust_legal_to_csv

# Test domains with known impressum pages
TEST_DOMAINS = [
    ('heise.de', 'https://www.heise.de/impressum.html'),
    ('zeit.de', 'https://www.zeit.de/impressum/index'),
    ('spiegel.de', 'https://www.spiegel.de/impressum'),
    ('kicker.de', 'https://www.kicker.de/impressum'),
    ('chip.de', 'https://www.chip.de/impressum'),
    ('golem.de', 'https://www.golem.de/impressum.html'),
    ('computerbild.de', 'https://www.computerbild.de/artikel/Impressum-13078.html'),
    ('t-online.de', 'https://www.t-online.de/impressum/'),
    ('web.de', 'https://web.de/impressum/'),
    ('gmx.de', 'https://www.gmx.net/impressum/'),
]


async def fetch_page(url: str) -> str:
    """Fetch page content."""
    async with httpx.AsyncClient(
        timeout=30.0,
        follow_redirects=True,
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text


async def test_extraction(domain: str, url: str, extractor: RobustLegalExtractor):
    """Test extraction on a single domain."""
    print(f"\n{'='*60}")
    print(f"Testing: {domain}")
    print(f"URL: {url}")
    print('='*60)
    
    try:
        html = await fetch_page(url)
        result = extractor.extract(html, url)
        
        # Add domain to result
        result['domain'] = domain
        
        # Print results
        print(f"\n[RESULT] Legal Name: {result.get('legal_name', 'N/A')}")
        print(f"[RESULT] Legal Form: {result.get('legal_form', 'N/A')}")
        print(f"[RESULT] Street: {result.get('street_address', 'N/A')}")
        print(f"[RESULT] ZIP: {result.get('postal_code', 'N/A')}")
        print(f"[RESULT] City: {result.get('city', 'N/A')}")
        print(f"[RESULT] Country: {result.get('country', 'N/A')}")
        print(f"[RESULT] Registration #: {result.get('registration_number', 'N/A')}")
        print(f"[RESULT] Register Court: {result.get('register_court', 'N/A')}")
        print(f"[RESULT] VAT ID: {result.get('vat_id', 'N/A')}")
        print(f"[RESULT] CEO: {result.get('ceo_name', 'N/A')}")
        print(f"[RESULT] Phone: {result.get('phone', 'N/A')}")
        print(f"[RESULT] Email: {result.get('email', 'N/A')}")
        print(f"[RESULT] Confidence: {result.get('extraction_confidence', 0):.1f}%")
        
        # Save to database
        await save_robust_legal_entity(result)
        print(f"\n[OK] Saved to database")
        
        return result
        
    except Exception as e:
        print(f"\n[ERROR] {type(e).__name__}: {e}")
        return None


async def main():
    """Run robust extraction tests."""
    print("\n" + "#"*60)
    print("# ROBUST LEGAL EXTRACTION TEST (v4.0)")
    print("#"*60)
    
    extractor = RobustLegalExtractor()
    results = []
    
    for domain, url in TEST_DOMAINS:
        result = await test_extraction(domain, url, extractor)
        if result:
            results.append(result)
        await asyncio.sleep(1)  # Be polite
        
    # Summary
    print("\n\n" + "#"*60)
    print("# TEST SUMMARY")
    print("#"*60)
    
    successful = len(results)
    total = len(TEST_DOMAINS)
    print(f"\nSuccessful extractions: {successful}/{total}")
    
    # Field coverage
    fields = ['legal_name', 'legal_form', 'street_address', 'postal_code', 'city',
              'registration_number', 'vat_id', 'ceo_name', 'phone', 'email']
    
    print("\nField Coverage:")
    for field in fields:
        count = sum(1 for r in results if r.get(field))
        pct = (count / successful * 100) if successful > 0 else 0
        print(f"  {field}: {count}/{successful} ({pct:.0f}%)")
        
    # Export to CSV
    print("\n\nExporting to CSV...")
    csv_path = await export_robust_legal_to_csv('data/robust_test_results.csv')
    print(f"[OK] Exported to {csv_path}")
    
    # Print average confidence
    if results:
        avg_conf = sum(r.get('extraction_confidence', 0) for r in results) / len(results)
        print(f"\nAverage confidence score: {avg_conf:.1f}%")


if __name__ == '__main__':
    asyncio.run(main())
