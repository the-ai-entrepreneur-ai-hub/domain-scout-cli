"""
Test script to demonstrate legal and company disclosure extraction capabilities.
"""
import asyncio
from src.legal_extractor import LegalExtractor
import httpx

async def test_legal_extraction():
    """Test the legal extractor with sample HTML containing legal information."""
    extractor = LegalExtractor()
    
    # Sample German Impressum HTML
    german_impressum = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Impressum</title>
    </head>
    <body>
        <h1>Impressum</h1>
        
        <h2>Angaben gemäß § 5 TMG</h2>
        <p>
            TechCorp GmbH<br>
            Musterstraße 123<br>
            12345 Berlin<br>
            Deutschland
        </p>
        
        <h2>Vertreten durch</h2>
        <p>
            Geschäftsführer: Max Mustermann, Maria Musterfrau
        </p>
        
        <h2>Kontakt</h2>
        <p>
            Telefon: +49 30 123456789<br>
            Telefax: +49 30 123456780<br>
            E-Mail: legal@techcorp.de
        </p>
        
        <h2>Registereintrag</h2>
        <p>
            Eintragung im Handelsregister.<br>
            Registergericht: Amtsgericht Berlin Charlottenburg<br>
            Registernummer: HRB 123456
        </p>
        
        <h2>Umsatzsteuer-ID</h2>
        <p>
            Umsatzsteuer-Identifikationsnummer gemäß § 27 a Umsatzsteuergesetz:<br>
            USt-IdNr.: DE123456789
        </p>
        
        <h2>Datenschutzbeauftragter</h2>
        <p>
            Datenschutzbeauftragter: Dr. Privacy Expert<br>
            E-Mail: dpo@techcorp.de
        </p>
    </body>
    </html>
    """
    
    # Sample UK Legal Notice
    uk_legal = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Legal Notice</title>
    </head>
    <body>
        <h1>Legal Notice</h1>
        
        <h2>Company Information</h2>
        <p>
            Company Name: TechCorp Limited<br>
            Legal Form: Limited Company<br>
            Registered Office: 123 Tech Street, London, EC1A 1BB, United Kingdom<br>
            Company Number: 12345678<br>
            Registered in England and Wales
        </p>
        
        <h2>Directors</h2>
        <p>
            John Smith (CEO)<br>
            Jane Doe (CTO)<br>
            Robert Johnson (CFO)
        </p>
        
        <h2>VAT Information</h2>
        <p>
            VAT Number: GB123456789
        </p>
        
        <h2>Contact</h2>
        <p>
            Legal Department: legal@techcorp.co.uk<br>
            Phone: +44 20 7946 0958<br>
            Fax: +44 20 7946 0959
        </p>
    </body>
    </html>
    """
    
    # Sample French Mentions Légales
    french_legal = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Mentions Légales</title>
    </head>
    <body>
        <h1>Mentions Légales</h1>
        
        <h2>Éditeur du site</h2>
        <p>
            Raison sociale : TechCorp SARL<br>
            Siège social : 123 Rue de la Tech, 75001 Paris, France<br>
            Capital social : 50 000 €<br>
            RCS Paris B 123 456 789<br>
            SIRET : 12345678900012<br>
            TVA intracommunautaire : FR12345678901
        </p>
        
        <h2>Directeur de la publication</h2>
        <p>
            Monsieur Pierre Dupont, Gérant
        </p>
        
        <h2>Contact</h2>
        <p>
            Téléphone : +33 1 23 45 67 89<br>
            Email : contact@techcorp.fr
        </p>
    </body>
    </html>
    """
    
    test_cases = [
        ("German Impressum", german_impressum, "https://example.de/impressum"),
        ("UK Legal Notice", uk_legal, "https://example.co.uk/legal"),
        ("French Mentions Légales", french_legal, "https://example.fr/mentions-legales")
    ]
    
    print("=" * 70)
    print("LEGAL EXTRACTION TEST")
    print("=" * 70)
    
    for name, html, url in test_cases:
        print(f"\n[TEST CASE: {name}]")
        print("-" * 50)
        
        result = extractor.extract(html, url)
        
        if result.get('status') == 'SUCCESS':
            print(f"[OK] Legal page detected (Confidence: {result.get('confidence', 0):.1f}%)")
            print(f"\nExtracted Information:")
            print(f"  Legal Name: {result.get('legal_name', 'N/A')}")
            print(f"  Legal Form: {result.get('legal_form', 'N/A')}")
            print(f"  Registration Number: {result.get('registration_number', 'N/A')}")
            print(f"  Register Court: {result.get('register_court', 'N/A')}")
            print(f"  VAT ID: {result.get('vat_id', 'N/A')}")
            print(f"  Tax ID: {result.get('tax_id', 'N/A')}")
            print(f"  SIRET: {result.get('siret', 'N/A')}")
            print(f"  CEO: {result.get('ceo', 'N/A')}")
            
            if result.get('directors'):
                print(f"  Directors: {', '.join(result['directors'])}")
                
            if result.get('registered_street'):
                addr = f"{result.get('registered_street', '')}, {result.get('registered_zip', '')} {result.get('registered_city', '')}"
                if result.get('registered_country'):
                    addr += f", {result['registered_country']}"
                print(f"  Registered Address: {addr}")
                
            print(f"  Legal Email: {result.get('legal_email', 'N/A')}")
            print(f"  Legal Phone: {result.get('legal_phone', 'N/A')}")
            print(f"  Fax: {result.get('fax', 'N/A')}")
            
            if result.get('dpo_name'):
                print(f"  DPO: {result['dpo_name']} ({result.get('dpo_email', 'N/A')})")
        else:
            print(f"[FAIL] {result.get('status', 'Unknown error')}")
    
    print("\n" + "=" * 70)

async def test_real_website():
    """Test extraction on a real website (if provided)."""
    test_url = input("\nEnter a URL to test legal extraction (or press Enter to skip): ").strip()
    
    if not test_url:
        return
        
    print(f"\nFetching {test_url}...")
    
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True, verify=False) as client:
            response = await client.get(test_url)
            
            if response.status_code != 200:
                print(f"[ERROR] Failed to fetch: HTTP {response.status_code}")
                return
                
            extractor = LegalExtractor()
            result = extractor.extract(response.text, test_url)
            
            if result.get('status') == 'SUCCESS':
                print(f"\n[SUCCESS] Legal information extracted!")
                print(f"Confidence: {result.get('confidence', 0):.1f}%")
                
                # Display all extracted fields
                fields = [
                    'legal_name', 'legal_form', 'registration_number', 'register_court',
                    'vat_id', 'tax_id', 'siret', 'siren', 'ceo', 'legal_email', 'legal_phone',
                    'fax', 'dpo_name', 'dpo_email'
                ]
                
                for field in fields:
                    if result.get(field):
                        print(f"{field.replace('_', ' ').title()}: {result[field]}")
            else:
                print(f"\n[INFO] Not a legal page or extraction failed")
                print(f"Status: {result.get('status')}")
                print(f"Confidence: {result.get('confidence', 0):.1f}%")
                
    except Exception as e:
        print(f"[ERROR] {e}")

async def main():
    print("\n[LEGAL & COMPANY DISCLOSURE EXTRACTION TEST]\n")
    
    # Run test cases
    await test_legal_extraction()
    
    # Optional: Test on real website
    await test_real_website()
    
    print("\n[TEST COMPLETED]")

if __name__ == "__main__":
    asyncio.run(main())
