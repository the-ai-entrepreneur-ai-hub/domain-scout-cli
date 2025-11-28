"""
Test script to demonstrate legal and company disclosure extraction capabilities.
"""
import asyncio
from src.legal_extractor import LegalExtractor
import httpx

async def test_legal_extraction():
    """Test the legal extractor with sample HTML containing legal information."""
    print("Initializing LegalExtractor (loading GLiNER model)...")
    extractor = LegalExtractor()
    
    # Sample German Impressum HTML (Standard)
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
    </body>
    </html>
    """
    
    # Messy/Complex German Impressum (The "Junk Data" Stress Test)
    messy_impressum = """
    <!DOCTYPE html>
    <html>
    <body>
        <div class="footer">
            <p>
            Impressum / Legal Notice
            
            Anbieterkennzeichnung nach § 5 TMG
            
            Adresse:
            Global Solutions Digital Services GmbH & Co. KG
            Besucheradresse: Industriepark West, Gebäude C, 3. Etage
            Willy-Brandt-Allee 42
            50670 Köln
            
            Kontakt:
            Tel: +49 221 12345
            Mail: info@global-solutions.de
            
            Rechtliche Angaben:
            Registergericht: Amtsgericht Köln, HRA 998877
            Persönlich haftende Gesellschafterin: Global Management GmbH
            Sitz: Köln, Amtsgericht Köln HRB 112233
            Geschäftsführer: Dr. Thomas Weber, Sarah Schmidt
            
            Umsatzsteuer-ID: DE 987654321
            
            Verantwortlich für den Inhalt nach § 55 Abs. 2 RStV:
            Michael Bauer
            Willy-Brandt-Allee 42
            50670 Köln
            </p>
        </div>
    </body>
    </html>
    """

    test_cases = [
        ("Standard German Impressum", german_impressum, "https://example.de/impressum"),
        ("Messy/Complex Impressum (GLiNER Test)", messy_impressum, "https://global-solutions.de/impressum")
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
            print(f"[METHOD] {result.get('extraction_method', 'regex').upper()}")
            print(f"\nExtracted Information:")
            print(f"  Legal Name: {result.get('legal_name', 'N/A')}")
            print(f"  Legal Form: {result.get('legal_form', 'N/A')}")
            print(f"  Registration Number: {result.get('registration_number', 'N/A')}")
            print(f"  Register Court: {result.get('register_court', 'N/A')}")
            print(f"  VAT ID: {result.get('vat_id', 'N/A')}")
            print(f"  CEO: {result.get('ceo', 'N/A')}")
            
            if result.get('directors'):
                print(f"  Directors: {', '.join(result['directors'])}")
                
            if result.get('registered_street'):
                addr = f"{result.get('registered_street', '')}, {result.get('registered_zip', '')} {result.get('registered_city', '')}"
                if result.get('registered_country'):
                    addr += f", {result['registered_country']}"
                print(f"  Registered Address: {addr}")
        else:
            print(f"[FAIL] {result.get('status', 'Unknown error')}")
    
    print("\n" + "=" * 70)

async def main():
    print("\n[LEGAL & COMPANY DISCLOSURE EXTRACTION TEST]\n")
    await test_legal_extraction()
    print("\n[TEST COMPLETED]")

if __name__ == "__main__":
    asyncio.run(main())
