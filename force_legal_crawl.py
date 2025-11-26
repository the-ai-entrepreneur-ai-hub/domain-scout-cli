"""
Force crawl legal pages for domains that are already completed.
"""
import asyncio
import aiosqlite
import httpx
from pathlib import Path
from src.legal_extractor import LegalExtractor
from src.link_discoverer import LinkDiscoverer

DB_PATH = Path("data/crawler_data.db")

async def force_legal_extraction():
    """Force extract legal info from completed domains."""
    
    async with aiosqlite.connect(DB_PATH) as db:
        # Get completed domains without legal entities
        cursor = await db.execute("""
            SELECT q.domain 
            FROM queue q
            WHERE q.status = 'COMPLETED'
            AND NOT EXISTS (
                SELECT 1 FROM legal_entities l 
                WHERE l.domain = q.domain
            )
            LIMIT 50
        """)
        domains = await cursor.fetchall()
    
    print(f"Found {len(domains)} domains to process for legal info")
    
    extractor = LegalExtractor()
    discoverer = LinkDiscoverer()
    success_count = 0
    
    for (domain,) in domains:
        print(f"\nProcessing {domain}...")
        base_url = f"https://{domain}"
        
        try:
            # Get homepage to find legal links
            async with httpx.AsyncClient(timeout=20, verify=False, follow_redirects=True) as client:
                resp = await client.get(base_url)
                if resp.status_code != 200:
                    continue
                    
                # Find legal links
                legal_links = discoverer.extract_legal_links_smart(resp.text, base_url)
                
                if not legal_links:
                    # Try common German paths
                    legal_links = [
                        f"{base_url}/impressum",
                        f"{base_url}/impressum.html",
                        f"{base_url}/legal",
                    ]
                
                # Try each legal link
                for legal_url in legal_links[:3]:
                    try:
                        legal_resp = await client.get(legal_url)
                        if legal_resp.status_code == 200:
                            result = extractor.extract(legal_resp.text, legal_url)
                            
                            if result.get('status') == 'SUCCESS' and result.get('confidence', 0) > 40:
                                # Save to database
                                await save_legal_entity(domain, result)
                                print(f"  SUCCESS: Found legal info (confidence: {result['confidence']:.1f}%)")
                                success_count += 1
                                break
                    except:
                        continue
                        
        except Exception as e:
            print(f"  Error: {e}")
            
    print(f"\n\nExtracted legal info for {success_count}/{len(domains)} domains")

async def save_legal_entity(domain, legal_info):
    """Save legal entity to database."""
    async with aiosqlite.connect(DB_PATH) as db:
        import json
        
        directors_json = json.dumps(legal_info.get('directors', [])) if legal_info.get('directors') else None
        auth_reps_json = json.dumps(legal_info.get('authorized_reps', [])) if legal_info.get('authorized_reps') else None
        
        await db.execute("""
            INSERT OR REPLACE INTO legal_entities
            (domain, legal_name, legal_form, 
             register_type, register_court, registration_number,
             vat_id, tax_id, siret, siren,
             ceo_name, directors, authorized_reps,
             registered_street, registered_zip, registered_city,
             registered_state, registered_country,
             legal_email, legal_phone, fax_number,
             legal_notice_url, extraction_confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            domain,
            legal_info.get('legal_name', ''),
            legal_info.get('legal_form', ''),
            legal_info.get('register_type', ''),
            legal_info.get('register_court', ''),
            legal_info.get('registration_number', ''),
            legal_info.get('vat_id', ''),
            legal_info.get('tax_id', ''),
            legal_info.get('siret', ''),
            legal_info.get('siren', ''),
            legal_info.get('ceo', ''),
            directors_json,
            auth_reps_json,
            legal_info.get('registered_street', ''),
            legal_info.get('registered_zip', ''),
            legal_info.get('registered_city', ''),
            legal_info.get('registered_state', ''),
            legal_info.get('registered_country', ''),
            legal_info.get('legal_email', ''),
            legal_info.get('legal_phone', ''),
            legal_info.get('fax', ''),
            legal_info.get('legal_notice_url', ''),
            legal_info.get('confidence', 0)
        ))
        await db.commit()

if __name__ == "__main__":
    asyncio.run(force_legal_extraction())
