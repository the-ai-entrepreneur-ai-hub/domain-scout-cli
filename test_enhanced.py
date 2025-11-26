"""
Test script to demonstrate the enhanced crawler's improved accuracy.
"""
import asyncio
from src.enhanced_extractor import EnhancedExtractor
from src.enhanced_crawler import EnhancedCrawler
import httpx

async def test_extraction():
    """Test the enhanced extraction on a sample website."""
    extractor = EnhancedExtractor()
    
    # Test domains with different types of content
    test_domains = [
        "https://www.example.com",  # Simple test
        "https://httpbin.org",      # API documentation site
        "https://www.python.org"    # Organization site
    ]
    
    print("=" * 60)
    print("ENHANCED EXTRACTOR TEST")
    print("=" * 60)
    
    for url in test_domains:
        print(f"\nTesting: {url}")
        print("-" * 40)
        
        try:
            # Fetch HTML
            async with httpx.AsyncClient(timeout=30, verify=False) as client:
                response = await client.get(url)
                if response.status_code != 200:
                    print(f"  [FAIL] Failed to fetch: HTTP {response.status_code}")
                    continue
                    
                html = response.text
                
            # Extract data
            domain = url.split("//")[1].split("/")[0]
            result = extractor.extract(html, domain, url)
            
            if result.get('status') == 'PARKED':
                print("  [WARNING] Parked domain detected")
            elif result.get('status') == 'EXTRACTION_FAILED':
                print(f"  [FAIL] Extraction failed: {result.get('error')}")
            else:
                print(f"  [OK] Company: {result.get('company_name', 'N/A')}")
                print(f"  [EMAIL] Emails: {', '.join(result.get('emails', [])) or 'None found'}")
                print(f"  [PHONE] Phones: {', '.join(result.get('phones', [])) or 'None found'}")
                print(f"  [ADDR] Address: {result.get('address', 'N/A')}")
                print(f"  [IND] Industry: {result.get('industry', 'N/A')}")
                print(f"  [LANG] Language: {result.get('language', 'N/A')}")
                print(f"  [SCORE] Confidence: {result.get('confidence_score', 0):.1f}%")
                
                if result.get('social_profiles'):
                    print("  [SOCIAL] Links:")
                    for platform, url in result['social_profiles'].items():
                        print(f"     - {platform}: {url}")
                        
        except Exception as e:
            print(f"  [ERROR] {e}")
            
    print("\n" + "=" * 60)

async def compare_extractors():
    """Compare old vs new extractor on the same content."""
    from src.extractor import Extractor as OldExtractor
    
    old_extractor = OldExtractor()
    new_extractor = EnhancedExtractor()
    
    # Sample HTML with structured data
    sample_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Acme Corporation - Leading Tech Solutions</title>
        <meta name="description" content="Acme Corp provides innovative technology solutions worldwide">
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "Corporation",
            "name": "Acme Corporation",
            "url": "https://acme.com",
            "telephone": "+1-555-123-4567",
            "email": "info@acme.com",
            "address": {
                "@type": "PostalAddress",
                "streetAddress": "123 Tech Street",
                "addressLocality": "San Francisco",
                "addressRegion": "CA",
                "postalCode": "94105",
                "addressCountry": "US"
            },
            "sameAs": [
                "https://linkedin.com/company/acme",
                "https://twitter.com/acmecorp"
            ]
        }
        </script>
    </head>
    <body>
        <header>
            <h1>Welcome to Acme Corporation</h1>
        </header>
        <main>
            <p>We are a leading technology company specializing in cloud computing and AI solutions.</p>
            <footer>
                <p>© 2024 Acme Corporation. All rights reserved.</p>
                <p>VAT ID: US123456789</p>
                <a href="mailto:support@acme.com">Contact Support</a>
                <a href="tel:+1-555-987-6543">Call Sales</a>
            </footer>
        </main>
    </body>
    </html>
    """
    
    print("\n" + "=" * 60)
    print("EXTRACTOR COMPARISON")
    print("=" * 60)
    
    # Test old extractor
    print("\n[OLD EXTRACTOR]:")
    print("-" * 40)
    old_result = old_extractor.extract(sample_html, "acme.com")
    print(f"Company: {old_result.get('company_name', 'N/A')}")
    print(f"Email: {old_result.get('email', 'N/A')}")
    print(f"Phone: {old_result.get('phone', 'N/A')}")
    print(f"Address: {old_result.get('address', 'N/A')}")
    
    # Test new extractor
    print("\n[ENHANCED EXTRACTOR]:")
    print("-" * 40)
    new_result = new_extractor.extract(sample_html, "acme.com", "https://acme.com")
    print(f"Company: {new_result.get('company_name', 'N/A')}")
    print(f"Emails: {', '.join(new_result.get('emails', []))}")
    print(f"Phones: {', '.join(new_result.get('phones', []))}")
    print(f"Address: {new_result.get('address', 'N/A')}")
    print(f"VAT ID: {new_result.get('vat_id', 'N/A')}")
    print(f"Industry: {new_result.get('industry', 'N/A')}")
    print(f"Confidence: {new_result.get('confidence_score', 0):.1f}%")
    print("Social Profiles:")
    for platform, url in new_result.get('social_profiles', {}).items():
        print(f"  - {platform}: {url}")
        
    print("\n" + "=" * 60)
    print("IMPROVEMENTS:")
    print("=" * 60)
    print("[+] Structured data extraction (JSON-LD)")
    print("[+] Multiple email/phone extraction")
    print("[+] International phone validation")
    print("[+] Full address parsing")
    print("[+] VAT/Tax ID extraction")
    print("[+] Social media profiles")
    print("[+] Industry classification")
    print("[+] Confidence scoring")
    print("=" * 60)

async def main():
    print("\n[ENHANCED WEB CRAWLER - ACCURACY TEST]\n")
    
    # Run comparison first
    await compare_extractors()
    
    # Then test real websites
    await test_extraction()
    
    print("\n[COMPLETED] Test finished successfully!")

if __name__ == "__main__":
    asyncio.run(main())
