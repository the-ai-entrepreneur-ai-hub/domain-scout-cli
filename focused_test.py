"""
Focused test on specific websites with known legal pages.
"""
import asyncio
import aiosqlite
from pathlib import Path

DB_PATH = Path("data/crawler_data.db")

async def add_test_domains():
    """Add specific test domains to the queue."""
    test_domains = [
        # German companies with known Impressum pages
        ('heise.de', 'TEST'),
        ('chip.de', 'TEST'),
        ('zeit.de', 'TEST'),
        ('sueddeutsche.de', 'TEST'),
        ('focus.de', 'TEST'),
        
        # Tech companies
        ('sap.com', 'TEST'),
        ('siemens.de', 'TEST'),
        
        # International
        ('bbc.co.uk', 'TEST'),
        ('lemonde.fr', 'TEST'),
    ]
    
    async with aiosqlite.connect(DB_PATH) as db:
        for domain, source in test_domains:
            await db.execute("""
                INSERT OR IGNORE INTO queue (domain, source, status)
                VALUES (?, ?, 'PENDING')
            """, (domain, source))
        await db.commit()
        
    print(f"Added {len(test_domains)} test domains to queue")

async def test_specific_domain(domain: str):
    """Test a specific domain with enhanced crawler."""
    print(f"\n{'='*60}")
    print(f"TESTING: {domain}")
    print(f"{'='*60}")
    
    from src.enhanced_crawler import EnhancedCrawler
    
    # Reset domain to pending
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE queue SET status = 'PENDING' 
            WHERE domain = ?
        """, (domain,))
        await db.commit()
        
        # Get domain ID
        cursor = await db.execute("""
            SELECT id FROM queue WHERE domain = ?
        """, (domain,))
        row = await cursor.fetchone()
        
        if not row:
            # Insert if not exists
            await db.execute("""
                INSERT INTO queue (domain, source, status)
                VALUES (?, 'TEST', 'PENDING')
            """, (domain,))
            await db.commit()
            
            cursor = await db.execute("""
                SELECT id FROM queue WHERE domain = ?
            """, (domain,))
            row = await cursor.fetchone()
    
    domain_id = row[0]
    
    # Run crawler
    crawler = EnhancedCrawler(concurrency=1, use_playwright=False)
    await crawler.process_domain({'id': domain_id, 'domain': domain})
    
    # Check results
    async with aiosqlite.connect(DB_PATH) as db:
        # Check enhanced results
        cursor = await db.execute("""
            SELECT company_name, emails, phones, confidence_score
            FROM results_enhanced
            WHERE domain = ?
        """, (domain,))
        enhanced = await cursor.fetchone()
        
        if enhanced:
            print(f"\n[ENHANCED RESULTS]")
            print(f"  Company: {enhanced[0] or 'N/A'}")
            print(f"  Emails: {enhanced[1] or 'None'}")
            print(f"  Phones: {enhanced[2] or 'None'}")
            print(f"  Confidence: {enhanced[3]:.1f}%")
        
        # Check legal entity
        cursor = await db.execute("""
            SELECT legal_name, legal_form, registration_number, 
                   vat_id, register_court, ceo_name,
                   legal_notice_url, extraction_confidence
            FROM legal_entities
            WHERE domain = ?
        """, (domain,))
        legal = await cursor.fetchone()
        
        if legal:
            print(f"\n[LEGAL ENTITY FOUND!]")
            print(f"  Legal Name: {legal[0] or 'N/A'}")
            print(f"  Legal Form: {legal[1] or 'N/A'}")
            print(f"  Registration: {legal[2] or 'N/A'}")
            print(f"  VAT ID: {legal[3] or 'N/A'}")
            print(f"  Court: {legal[4] or 'N/A'}")
            print(f"  CEO: {legal[5] or 'N/A'}")
            print(f"  Legal URL: {legal[6] or 'N/A'}")
            print(f"  Confidence: {legal[7]:.1f}%")
        else:
            print(f"\n[NO LEGAL ENTITY FOUND]")

async def manual_legal_test():
    """Manually test legal extraction on a known Impressum page."""
    import httpx
    from src.legal_extractor import LegalExtractor
    
    test_url = "https://www.heise.de/impressum.html"
    
    print(f"\n{'='*60}")
    print(f"MANUAL LEGAL EXTRACTION TEST")
    print(f"URL: {test_url}")
    print(f"{'='*60}")
    
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True, verify=False) as client:
            response = await client.get(test_url)
            
            if response.status_code == 200:
                extractor = LegalExtractor()
                result = extractor.extract(response.text, test_url)
                
                if result.get('status') == 'SUCCESS':
                    print(f"\n[SUCCESS] Legal information extracted!")
                    print(f"  Confidence: {result.get('confidence', 0):.1f}%")
                    
                    fields = ['legal_name', 'legal_form', 'registration_number', 
                             'register_court', 'vat_id', 'ceo']
                    
                    for field in fields:
                        if result.get(field):
                            print(f"  {field}: {result[field]}")
                else:
                    print(f"\n[FAILED] Status: {result.get('status')}")
            else:
                print(f"[ERROR] HTTP {response.status_code}")
                
    except Exception as e:
        print(f"[ERROR] {e}")

async def main():
    print("\n[FOCUSED LEGAL EXTRACTION TEST]\n")
    
    # Test 1: Manual test on known Impressum page
    await manual_legal_test()
    
    # Test 2: Test specific German news site
    await test_specific_domain("heise.de")
    
    # Test 3: Add and test more domains
    # await add_test_domains()
    # await test_specific_domain("chip.de")
    
    print("\n[TEST COMPLETED]")

if __name__ == "__main__":
    asyncio.run(main())
