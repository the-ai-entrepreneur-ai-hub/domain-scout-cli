import asyncio
from src.enhanced_crawler import EnhancedCrawler
from src.legal_extractor import LegalExtractor
import aiohttp
from bs4 import BeautifulSoup

async def debug_url(url):
    print(f"--- Debugging: {url} ---")
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers={'User-Agent': 'Mozilla/5.0'}) as resp:
            html = await resp.text()
            
    extractor = LegalExtractor()
    
    # 1. Check is_legal_page logic
    soup = BeautifulSoup(html, 'lxml')
    clean_text = soup.get_text(separator=' ', strip=True)
    
    is_legal, confidence = extractor.is_legal_page(soup, url, clean_text)
    print(f"Is Legal Page: {is_legal} (Confidence: {confidence})")
    
    # 2. Run full extraction
    data = extractor.extract(html, url)
    print("\nExtraction Result:")
    for k, v in data.items():
        if v:
            print(f"  {k}: {v}")

async def main():
    # Test cases that failed in the wild
    urls = [
        "https://www.hostpoint.ch/impressum",
        "https://www.hostpoint.ch/en/about-us/legal/", # Guessing URL
        "https://home.cern/about",
        "https://www.google.ch/impressum"
    ]
    
    for u in urls:
        try:
            await debug_url(u)
        except Exception as e:
            print(f"Error fetching {u}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
