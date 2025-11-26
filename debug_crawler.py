"""
Debug crawler to see what's happening during the crawl process.
"""
import asyncio
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin

async def find_impressum_link(domain: str):
    """Find the impressum link on a website."""
    base_url = f"https://{domain}"
    
    print(f"\nSearching for legal links on {domain}...")
    
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True, verify=False) as client:
            response = await client.get(base_url)
            
            if response.status_code != 200:
                print(f"  Failed to fetch homepage: HTTP {response.status_code}")
                return
                
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Find all links
            legal_links = []
            all_links = []
            
            for link in soup.find_all('a', href=True):
                href = link['href'].lower()
                text = link.get_text().lower().strip()
                full_url = urljoin(base_url, link['href'])
                
                all_links.append((link['href'], text))
                
                # Check for legal keywords
                legal_keywords = ['impressum', 'imprint', 'legal', 'rechtlich', 
                                'datenschutz', 'privacy', 'agb']
                
                if any(kw in href or kw in text for kw in legal_keywords):
                    legal_links.append((full_url, text, link['href']))
                    print(f"  Found legal link: {link['href']} (text: '{text[:50]}')")
            
            if not legal_links:
                print(f"  No legal links found out of {len(all_links)} total links")
                
                # Show footer links
                footer = soup.find('footer')
                if footer:
                    print("\n  Footer links found:")
                    for link in footer.find_all('a', href=True)[:10]:
                        print(f"    - {link['href']} : '{link.get_text().strip()[:30]}'")
            else:
                print(f"\n  Testing first legal link: {legal_links[0][0]}")
                
                # Test if it's actually a legal page
                resp = await client.get(legal_links[0][0])
                if resp.status_code == 200:
                    from src.legal_extractor import LegalExtractor
                    extractor = LegalExtractor()
                    result = extractor.extract(resp.text, legal_links[0][0])
                    
                    if result.get('status') == 'SUCCESS':
                        print(f"  [SUCCESS] Legal page confirmed! Confidence: {result.get('confidence'):.1f}%")
                        if result.get('legal_form'):
                            print(f"    Legal Form: {result['legal_form']}")
                        if result.get('registration_number'):
                            print(f"    Registration: {result['registration_number']}")
                    else:
                        print(f"  [NOT LEGAL] Status: {result.get('status')}")
                        
    except Exception as e:
        print(f"  Error: {e}")

async def debug_crawl_process(domain: str):
    """Debug the entire crawl process for a domain."""
    print(f"\n{'='*60}")
    print(f"DEBUG CRAWL: {domain}")
    print(f"{'='*60}")
    
    # Step 1: Find impressum link
    await find_impressum_link(domain)
    
    # Step 2: Check what the crawler would do
    from src.link_discoverer import LinkDiscoverer
    
    base_url = f"https://{domain}"
    
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True, verify=False) as client:
            response = await client.get(base_url)
            
            if response.status_code == 200:
                discoverer = LinkDiscoverer()
                links = discoverer.find_legal_links(response.text, base_url)
                
                print(f"\nLink Discoverer Results:")
                print(f"  Legal links: {len(links['legal'])}")
                for link in links['legal'][:5]:
                    print(f"    - {link}")
                    
                print(f"  Contact links: {len(links['contact'])}")
                print(f"  About links: {len(links['about'])}")
                print(f"  Footer links: {len(links['footer'])}")
                
                # Get smart extraction
                smart_links = discoverer.extract_legal_links_smart(response.text, base_url)
                print(f"\nSmart extraction (top priority):")
                for link in smart_links[:5]:
                    print(f"    - {link}")
                    
    except Exception as e:
        print(f"Error: {e}")

async def main():
    # Test German sites
    test_domains = [
        'heise.de',
        'spiegel.de',
        'zeit.de'
    ]
    
    for domain in test_domains:
        await debug_crawl_process(domain)
        await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())
