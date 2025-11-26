"""
Final aggressive test with improved legal extraction.
"""
import asyncio
import aiosqlite
from pathlib import Path

DB_PATH = Path("data/crawler_data.db")

async def test_domain_with_details(domain: str):
    """Test a single domain and show detailed results."""
    print(f"\n{'='*70}")
    print(f"TESTING: {domain}")
    print(f"{'='*70}")
    
    # Reset domain to pending
    async with aiosqlite.connect(DB_PATH) as db:
        # Check if exists
        cursor = await db.execute("SELECT id FROM queue WHERE domain = ?", (domain,))
        row = await cursor.fetchone()
        
        if not row:
            # Insert new
            await db.execute("""
                INSERT INTO queue (domain, source, status)
                VALUES (?, 'FINAL_TEST', 'PENDING')
            """, (domain,))
        else:
            # Reset to pending
            await db.execute("""
                UPDATE queue SET status = 'PENDING'
                WHERE domain = ?
            """, (domain,))
        await db.commit()
        
        cursor = await db.execute("SELECT id FROM queue WHERE domain = ?", (domain,))
        row = await cursor.fetchone()
        domain_id = row[0]
    
    # Run enhanced crawler
    from src.enhanced_crawler import EnhancedCrawler
    
    crawler = EnhancedCrawler(concurrency=1, use_playwright=False)
    await crawler.process_domain({'id': domain_id, 'domain': domain})
    
    # Check results
    async with aiosqlite.connect(DB_PATH) as db:
        # General results
        cursor = await db.execute("""
            SELECT company_name, emails, phones, address, 
                   industry, confidence_score
            FROM results_enhanced
            WHERE domain = ?
        """, (domain,))
        enhanced = await cursor.fetchone()
        
        if enhanced:
            print(f"\n[BUSINESS DATA EXTRACTED]")
            print(f"  Company: {enhanced[0] or 'N/A'}")
            print(f"  Emails: {enhanced[1] or 'None'}")
            print(f"  Phones: {enhanced[2] or 'None'}")
            print(f"  Address: {enhanced[3] or 'None'}")
            print(f"  Industry: {enhanced[4] or 'N/A'}")
            print(f"  Confidence: {enhanced[5]:.1f}%")
        else:
            print(f"\n[NO BUSINESS DATA]")
        
        # Legal entity results
        cursor = await db.execute("""
            SELECT legal_name, legal_form, registration_number,
                   vat_id, register_court, ceo_name,
                   registered_street, registered_city, registered_country,
                   legal_email, fax_number,
                   legal_notice_url, extraction_confidence
            FROM legal_entities
            WHERE domain = ?
        """, (domain,))
        legal = await cursor.fetchone()
        
        if legal:
            print(f"\n[LEGAL ENTITY EXTRACTED] SUCCESS")
            print(f"  Legal Name: {legal[0] or 'N/A'}")
            print(f"  Legal Form: {legal[1] or 'N/A'}")
            print(f"  Registration: {legal[2] or 'N/A'}")
            print(f"  VAT ID: {legal[3] or 'N/A'}")
            print(f"  Court: {legal[4] or 'N/A'}")
            print(f"  CEO: {legal[5] or 'N/A'}")
            
            if legal[6] or legal[7]:
                addr = f"{legal[6] or ''}, {legal[7] or ''} {legal[8] or ''}".strip(', ')
                print(f"  Address: {addr}")
                
            print(f"  Legal Email: {legal[9] or 'N/A'}")
            print(f"  Fax: {legal[10] or 'N/A'}")
            print(f"  Legal URL: {legal[11] or 'N/A'}")
            print(f"  Confidence: {legal[12]:.1f}%")
        else:
            print(f"\n[NO LEGAL ENTITY] FAILED")

async def final_test_suite():
    """Run final test on key German domains."""
    
    # Test domains - mix of German companies
    test_domains = [
        'heise.de',       # Tech news (should have impressum)
        'sap.com',        # German software company
        'siemens.de',     # German industrial
        'volkswagen.de',  # German auto
        'lufthansa.com',  # German airline
        'zalando.de',     # German e-commerce
        'dm.de',          # German retail
        'otto.de',        # German retail
    ]
    
    print("\n" + "="*70)
    print("[FINAL AGGRESSIVE TEST - LEGAL EXTRACTION]")
    print("="*70)
    print(f"Testing {len(test_domains)} German domains...")
    
    success_count = 0
    
    for domain in test_domains:
        await test_domain_with_details(domain)
        
        # Check if legal entity was found
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("""
                SELECT COUNT(*) FROM legal_entities WHERE domain = ?
            """, (domain,))
            count = (await cursor.fetchone())[0]
            if count > 0:
                success_count += 1
        
        await asyncio.sleep(3)  # Be polite between domains
    
    # Final summary
    print(f"\n{'='*70}")
    print(f"[FINAL RESULTS]")
    print(f"{'='*70}")
    print(f"Legal entities extracted: {success_count}/{len(test_domains)}")
    print(f"Success rate: {success_count/len(test_domains)*100:.1f}%")
    
    # Show all legal entities found
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT domain, legal_form, registration_number, vat_id
            FROM legal_entities
            WHERE domain IN ({})
            ORDER BY extraction_confidence DESC
        """.format(','.join('?' * len(test_domains))), test_domains)
        
        results = await cursor.fetchall()
        
        if results:
            print(f"\nLegal Entities Found:")
            for domain, form, reg, vat in results:
                print(f"  {domain:20} | {form or '-':10} | {reg or '-':15} | {vat or '-'}")

async def main():
    await final_test_suite()

if __name__ == "__main__":
    asyncio.run(main())
