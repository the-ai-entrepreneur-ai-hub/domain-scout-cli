"""
AGGRESSIVE TEST SCRIPT - Test crawler with real domains!
"""
import asyncio
import aiosqlite
from pathlib import Path
from datetime import datetime
import json

DB_PATH = Path("data/crawler_data.db")

async def show_domains(limit=10, status=None):
    """Show domains from queue."""
    async with aiosqlite.connect(DB_PATH) as db:
        if status:
            query = "SELECT domain, status FROM queue WHERE status = ? LIMIT ?"
            params = (status, limit)
        else:
            query = "SELECT domain, status FROM queue LIMIT ?"
            params = (limit,)
            
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        
        print(f"\n{'='*60}")
        print(f"DOMAINS IN QUEUE (showing {len(rows)})")
        print(f"{'='*60}")
        for domain, status in rows:
            print(f"  {domain:40} [{status}]")
        
        # Get status counts
        cursor = await db.execute("""
            SELECT status, COUNT(*) 
            FROM queue 
            GROUP BY status
        """)
        stats = await cursor.fetchall()
        
        print(f"\n{'='*60}")
        print("STATUS BREAKDOWN")
        print(f"{'='*60}")
        for status, count in stats:
            print(f"  {status:20}: {count:6}")
            
        return rows

async def run_crawler_test(limit=5):
    """Run enhanced crawler on pending domains."""
    print(f"\n{'='*60}")
    print(f"STARTING ENHANCED CRAWLER TEST")
    print(f"{'='*60}")
    print(f"Testing {limit} domains with legal extraction...")
    
    # Import here to avoid issues
    from src.enhanced_crawler import EnhancedCrawler
    
    crawler = EnhancedCrawler(concurrency=2, use_playwright=False)
    
    # Get pending domains
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, domain FROM queue WHERE status = 'PENDING' LIMIT ?",
            (limit,)
        )
        domains = await cursor.fetchall()
        
    if not domains:
        print("No pending domains found!")
        return
        
    print(f"Crawling {len(domains)} domains...")
    
    # Process each domain
    for domain_row in domains:
        domain_dict = {'id': domain_row[0], 'domain': domain_row[1]}
        print(f"\nProcessing: {domain_dict['domain']}")
        await crawler.process_domain(domain_dict)
        
        # Small delay between domains
        await asyncio.sleep(2)
    
    print("\nCrawling completed!")

async def check_results():
    """Check extraction results."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Check enhanced results
        cursor = await db.execute("""
            SELECT domain, company_name, emails, phones, 
                   confidence_score
            FROM results_enhanced
            ORDER BY confidence_score DESC
            LIMIT 10
        """)
        enhanced = await cursor.fetchall()
        
        print(f"\n{'='*60}")
        print("ENHANCED EXTRACTION RESULTS")
        print(f"{'='*60}")
        
        if enhanced:
            for row in enhanced:
                domain, company, emails, phones, confidence = row
                print(f"\n{domain}")
                print(f"  Company: {company or 'N/A'}")
                print(f"  Emails: {emails or 'None'}")
                print(f"  Phones: {phones or 'None'}")
                print(f"  Confidence: {confidence:.1f}%")
        else:
            print("No enhanced results found.")
            
        # Check legal entities
        cursor = await db.execute("""
            SELECT domain, legal_name, legal_form, 
                   registration_number, vat_id,
                   extraction_confidence
            FROM legal_entities
            ORDER BY extraction_confidence DESC
            LIMIT 10
        """)
        legal = await cursor.fetchall()
        
        print(f"\n{'='*60}")
        print("LEGAL ENTITY EXTRACTION RESULTS")
        print(f"{'='*60}")
        
        if legal:
            for row in legal:
                domain, name, form, reg_num, vat, confidence = row
                print(f"\n{domain}")
                print(f"  Legal Name: {name or 'N/A'}")
                print(f"  Legal Form: {form or 'N/A'}")
                print(f"  Registration: {reg_num or 'N/A'}")
                print(f"  VAT ID: {vat or 'N/A'}")
                print(f"  Confidence: {confidence:.1f}%")
        else:
            print("No legal entities found.")

async def reset_failed_for_retry():
    """Reset failed domains for retry."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE queue 
            SET status = 'PENDING' 
            WHERE status IN ('FAILED_DNS', 'FAILED_CONNECTION', 'FAILED_FETCH')
        """)
        await db.commit()
        
        cursor = await db.execute("SELECT changes()")
        count = (await cursor.fetchone())[0]
        print(f"\nReset {count} failed domains to PENDING for retry.")

async def aggressive_test():
    """Run aggressive testing cycle."""
    print("\n" + "="*60)
    print("[AGGRESSIVE CRAWLER TEST - LIVE DOMAINS]")
    print("="*60)
    
    # 1. Show discovered domains
    await show_domains(10)
    
    # 2. Run crawler on some domains
    print("\n[PHASE 1: Initial Crawl]")
    await run_crawler_test(5)
    
    # 3. Check results
    await check_results()
    
    # 4. Reset failed domains and retry
    print("\n[PHASE 2: Retry Failed Domains]")
    await reset_failed_for_retry()
    await run_crawler_test(3)
    
    # 5. Final results
    print("\n[FINAL RESULTS]")
    await check_results()
    
    # Show final statistics
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT 
                (SELECT COUNT(*) FROM queue) as total_domains,
                (SELECT COUNT(*) FROM queue WHERE status = 'COMPLETED') as completed,
                (SELECT COUNT(*) FROM results_enhanced) as enhanced_results,
                (SELECT COUNT(*) FROM legal_entities) as legal_entities,
                (SELECT AVG(confidence_score) FROM results_enhanced) as avg_confidence
        """)
        stats = await cursor.fetchone()
        
        print(f"\n{'='*60}")
        print("FINAL STATISTICS")
        print(f"{'='*60}")
        print(f"  Total Domains: {stats[0]}")
        print(f"  Completed: {stats[1]}")
        print(f"  Enhanced Results: {stats[2]}")
        print(f"  Legal Entities: {stats[3]}")
        print(f"  Avg Confidence: {stats[4]:.1f}%" if stats[4] else "  Avg Confidence: N/A")

async def main():
    await aggressive_test()

if __name__ == "__main__":
    asyncio.run(main())
