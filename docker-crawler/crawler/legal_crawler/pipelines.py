import re
import os
import csv
import psycopg2
from datetime import datetime
from urllib.parse import urlparse
import logging

# Third-party libraries
try:
    import trafilatura
except ImportError:
    trafilatura = None

try:
    import phonenumbers
except ImportError:
    phonenumbers = None

try:
    from thefuzz import fuzz
except ImportError:
    fuzz = None

try:
    from legal_crawler.spacy_extractor import SpacyExtractor
except ImportError:
    SpacyExtractor = None


class ExtractionPipeline:
    """
    Hybrid Extraction Pipeline using NLP + Structural Anchoring
    replaces the old Regex-only approach.
    """
    
    def __init__(self):
        self.nlp = SpacyExtractor() if SpacyExtractor else None
        self.logger = logging.getLogger(__name__)
    
    # Keep some regexes as fallback or helpers
    LEGAL_FORMS = [
        'GmbH', 'AG', 'KG', 'OHG', 'UG', 'e.V.', 'GbR', 'SE', 'SA', 'S.à r.l.', 'Ltd', 'Inc', 'Limited'
    ]

    def process_item(self, item, spider):
        """Extract structured data using Hybrid Strategy"""
        raw_html = item.get('raw_html', '')
        domain = item.get('domain', '')
        
        # 1. Improved Text Extraction with Trafilatura
        text = self._get_clean_text(raw_html, item.get('extracted_text'))
        item['extracted_text'] = text  # Update item with better text

        # 2. Detect Country (Crucial for formatting)
        country = self.detect_country(text, domain)
        item['country'] = country

        # 3. Address Extraction (The Anchor Strategy)
        address = self.extract_address_hybrid(text, country)
        item['street'] = address.get('street')
        item['postal_code'] = address.get('postal_code')
        item['city'] = address.get('city')

        # 4. Company Name Extraction (Context-Aware)
        item['company_name'] = self.extract_company_hybrid(text, domain, address.get('match_start_index'))

        # 5. Contact Info (Standardized)
        item['phone_numbers'] = self.extract_phones_global(text, country)
        item['emails'] = self.extract_emails(text)
        item['fax_numbers'] = self.extract_fax(text)

        # 6. Legal & Registration
        item['legal_form'] = self.extract_legal_form(item['company_name'] or text)
        item['registration_number'] = self.extract_registration(text)
        item['vat_id'] = self.extract_vat(text)
        item['ceo_names'] = self.extract_ceo(text)

        return item

    def _get_clean_text(self, html, fallback_text):
        """Get high-quality text using Trafilatura"""
        if trafilatura and html:
            try:
                # standard extraction
                clean = trafilatura.extract(html, include_comments=False, include_tables=True, no_fallback=False)
                if clean:
                    return clean
            except Exception:
                pass
        return fallback_text or ""

    def detect_country(self, text, domain):
        """Detect country from TLD and Content"""
        if domain.endswith('.ch'): return 'Switzerland'
        if domain.endswith('.at'): return 'Austria'
        if domain.endswith('.de'): return 'Germany'
        
        text_lower = text.lower()
        if 'schweiz' in text_lower or 'suisse' in text_lower: return 'Switzerland'
        if 'österreich' in text_lower: return 'Austria'
        if 'deutschland' in text_lower: return 'Germany'
        
        return 'Germany' # Default

    def extract_address_hybrid(self, text, country):
        """
        Extracts address by finding the ZIP+City Anchor first,
        then looking at the line ABOVE for the street.
        """
        result = {'street': None, 'postal_code': None, 'city': None, 'match_start_index': -1}
        
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        # Regex for Zip+City line
        if country == 'Switzerland':
            zip_city_re = re.compile(r'(?:CH-?)?(\d{4})\s+([A-Za-zäöüÄÖÜß\.\-\s]+)')
        else:
            zip_city_re = re.compile(r'\b(\d{5})\s+([A-Za-zäöüÄÖÜß\.\-\s]+)')
            
        for i, line in enumerate(lines):
            match = zip_city_re.search(line)
            if match:
                zip_code = match.group(1)
                city = match.group(2).strip()
                
                # Aggressive City Cleaning
                city = self.clean_city(city)
                
                if not city or len(city) < 3 or re.search(r'[0-9]', city):
                    continue
                    
                result['postal_code'] = zip_code
                result['city'] = city
                result['match_start_index'] = text.find(line)
                
                # Look for Street
                # Case 1: Same line ("Musterstraße 1, 12345 Berlin")
                pre_match_text = line[:match.start()].strip()
                if len(pre_match_text) > 5 and self._is_valid_street(pre_match_text):
                    result['street'] = self._clean_street(pre_match_text)
                    break
                
                # Case 2: Line above (Most common)
                if i > 0 and self._is_valid_street(lines[i-1]):
                    result['street'] = self._clean_street(lines[i-1])
                    break
                        
                # Case 3: Two lines above
                if i > 1 and self._is_valid_street(lines[i-2]):
                    result['street'] = self._clean_street(lines[i-2])
                    break
                
                break 
                
        return result

    def clean_city(self, city):
        # Remove country names
        city = re.sub(r'\s*(Deutschland|Germany|Schweiz|Switzerland|Österreich|Austria).*', '', city, flags=re.IGNORECASE)
        # Remove common garbage suffixes
        city = city.split('Tel')[0].split('Email')[0].split('Kontakt')[0].split('Postfach')[0]
        return city.strip()

    def _is_valid_street(self, text):
        if len(text) < 3 or len(text) > 80: return False
        if not re.search(r'\d', text): # Must have number usually
             if not re.search(r'(straße|str\.|weg|gasse|platz|allee|damm|ring|hof|markt)', text.lower()):
                return False
        if any(form in text for form in ['GmbH', 'AG', 'KG', 'Tel:', 'Fax:', 'Email', '@', 'www.']):
            return False
        return True

    def _clean_street(self, text):
        return re.sub(r'[,\.]+$', '', text).strip()

    def extract_company_hybrid(self, text, domain, address_index):
        """Score lines to find company name"""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        best_candidate = None
        best_score = 0
        
        domain_clean = domain.split('.')[0].replace('www.', '').lower()
        
        for i, line in enumerate(lines):
            if len(line) > 80 or len(line) < 3: continue
            
            score = 0
            line_lower = line.lower()
            
            # Factor 1: Fuzzy Match
            if fuzz:
                ratio = fuzz.partial_ratio(domain_clean, line_lower)
                if ratio > 85: score += 40
            
            # Factor 2: NLP
            if self.nlp and self.nlp.is_company(line): score += 30
            
            # Factor 3: Legal Form
            if any(form in line for form in self.LEGAL_FORMS): score += 30
                
            # Factor 4: Position (Top of page)
            if i < 5: score += 20
            elif i < 15: score += 10
            
            # Penalties
            if 'Impressum' in line: score -= 20
            if '@' in line or 'http' in line: score -= 100
            
            if score > best_score:
                best_score = score
                best_candidate = line
                
        if best_candidate:
            return re.sub(r'^(Firma|Betreiber|Herausgeber)[:\s]+', '', best_candidate).strip()
        return None

    def extract_phones_global(self, text, country_name):
        if not phonenumbers:
            # Fallback regex
            return '; '.join(re.findall(r'(?:\+49|0)[0-9\s\-]{6,}', text)[:3])
            
        region = "DE"
        if country_name == "Switzerland": region = "CH"
        if country_name == "Austria": region = "AT"
        
        found = []
        try:
            for match in phonenumbers.PhoneNumberMatcher(text, region):
                formatted = phonenumbers.format_number(match.number, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
                found.append(formatted)
        except Exception:
            pass
            
        return '; '.join(set(found[:5])) if found else None

    def extract_emails(self, text):
        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text.lower())
        valid = [e for e in emails if not any(x in e for x in ['example', 'test', '.png', '.jpg'])]
        return '; '.join(set(valid[:5])) if valid else None

    def extract_fax(self, text):
        matches = re.findall(r'(?:Fax|Telefax)[\s:]*([+\d\s\-/()]{8,20})', text)
        return '; '.join(set(matches[:3])) if matches else None

    def extract_legal_form(self, text):
        if not text: return None
        for form in self.LEGAL_FORMS:
            if re.search(r'\b' + re.escape(form) + r'\b', text):
                return form
        return None

    def extract_registration(self, text):
        patterns = [
            r'(?:HRB|HRA)[\s\-:]*(\d+)',
            r'(?:Handelsregister|Registergericht)[\s:]*([A-Za-zäöüÄÖÜß\s]+)',
        ]
        for p in patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m: return m.group(1).strip()
        return None

    def extract_vat(self, text):
        patterns = [
            r'(?:USt-?IdNr\.?|UID|VAT)[\s:]*([A-Z]{2}\s*\d{9,11})',
            r'\b(DE\s*\d{9})\b',
            r'\b(CHE[-\s]?\d{3}\.?\d{3}\.?\d{3})\b'
        ]
        for p in patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m: return m.group(1).replace(' ', '')
        return None

    def extract_ceo(self, text):
        patterns = [
            r'(?:Geschäftsführer|Vorstand|Inhaber|CEO)[\s:]*([A-Za-zäöüÄÖÜß\.\-\s,]+)',
            r'(?:Vertreten durch)[\s:]*([A-Za-zäöüÄÖÜß\.\-\s,]+)'
        ]
        for p in patterns:
            m = re.search(p, text)
            if m:
                name = m.group(1).strip()
                name = name.split('Kontakt')[0].split('Tel')[0].split('USt-ID')[0].split('Register')[0]
                if len(name) < 3 or len(name) > 50: continue
                return name
        return None

# Keep PostgresPipeline and CsvPipeline classes as they were
class PostgresPipeline:
    def __init__(self):
        self.conn = None
        self.cursor = None
    
    def open_spider(self, spider):
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            spider.logger.error("DATABASE_URL environment variable not set")
            return
            
        try:
            self.conn = psycopg2.connect(database_url)
            self.cursor = self.conn.cursor()
        except Exception as e:
            spider.logger.error(f"DB Connection failed: {e}")
    
    def close_spider(self, spider):
        if self.cursor: self.cursor.close()
        if self.conn: self.conn.close()
    
    def process_item(self, item, spider):
        if not self.cursor: return item
        try:
            self.cursor.execute('''
                INSERT INTO results (
                    domain, url, company_name, legal_form, street, postal_code, city, country,
                    ceo_names, emails, phone_numbers, fax_numbers, registration_number, vat_id,
                    whois_registrar, whois_creation_date, whois_expiration_date, whois_owner, whois_emails,
                    raw_html, extracted_text
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (domain, url) DO UPDATE SET
                    company_name = EXCLUDED.company_name,
                    legal_form = EXCLUDED.legal_form,
                    street = EXCLUDED.street,
                    postal_code = EXCLUDED.postal_code,
                    city = EXCLUDED.city,
                    country = EXCLUDED.country,
                    ceo_names = EXCLUDED.ceo_names,
                    emails = EXCLUDED.emails,
                    phone_numbers = EXCLUDED.phone_numbers,
                    fax_numbers = EXCLUDED.fax_numbers,
                    registration_number = EXCLUDED.registration_number,
                    vat_id = EXCLUDED.vat_id,
                    whois_registrar = EXCLUDED.whois_registrar,
                    whois_creation_date = EXCLUDED.whois_creation_date,
                    whois_expiration_date = EXCLUDED.whois_expiration_date,
                    whois_owner = EXCLUDED.whois_owner,
                    whois_emails = EXCLUDED.whois_emails
            ''', (
                item.get('domain'), item.get('url'), item.get('company_name'), item.get('legal_form'),
                item.get('street'), item.get('postal_code'), item.get('city'), item.get('country'),
                item.get('ceo_names'), item.get('emails'), item.get('phone_numbers'), item.get('fax_numbers'),
                item.get('registration_number'), item.get('vat_id'),
                item.get('whois_registrar'), item.get('whois_creation_date'), item.get('whois_expiration_date'),
                item.get('whois_owner'), item.get('whois_emails'),
                item.get('raw_html'), item.get('extracted_text')
            ))
            self.conn.commit()
        except Exception as e:
            spider.logger.error(f'Database error: {e}')
            self.conn.rollback()
        return item

class CsvPipeline:
    def __init__(self):
        self.file = None
        self.writer = None
        self.output_path = None
    
    def open_spider(self, spider):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'legal_notices_{timestamp}.csv'
        self.output_path = os.path.join('/app/data', filename)
        self.file = open(self.output_path, 'w', newline='', encoding='utf-8')
        self.writer = csv.writer(self.file)
        self.writer.writerow([
            'domain', 'url', 'company_name', 'legal_form', 'street', 'postal_code',
            'city', 'country', 'ceo_names', 'emails', 'phone_numbers', 'fax_numbers',
            'registration_number', 'vat_id', 'crawled_at',
            'whois_registrar', 'whois_creation_date', 'whois_expiration_date', 'whois_owner', 'whois_emails'
        ])
        print(f"\033[96m[*] Output file: {self.output_path}\033[0m")
    
    def close_spider(self, spider):
        if self.file: self.file.close()
    
    def process_item(self, item, spider):
        self.writer.writerow([
            item.get('domain', ''), item.get('url', ''), item.get('company_name', ''),
            item.get('legal_form', ''), item.get('street', ''), item.get('postal_code', ''),
            item.get('city', ''), item.get('country', ''), item.get('ceo_names', ''),
            item.get('emails', ''), item.get('phone_numbers', ''), item.get('fax_numbers', ''),
            item.get('registration_number', ''), item.get('vat_id', ''),
            datetime.now().isoformat(),
            item.get('whois_registrar', ''), item.get('whois_creation_date', ''),
            item.get('whois_expiration_date', ''), item.get('whois_owner', ''), item.get('whois_emails', '')
        ])
        self.file.flush()
        return item
