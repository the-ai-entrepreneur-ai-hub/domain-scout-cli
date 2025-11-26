# -*- coding: utf-8 -*-
"""
German Legal Extractor - Specialized for German Impressum pages.
IMPROVED: Better VAT and CEO extraction patterns.
"""
import re
from typing import Dict, Optional, List
from ..field_validators import FieldValidators

class GermanExtractor:
    """Extracts legal information from German Impressum pages."""
    
    PATTERNS = {
        # Company name patterns
        'company_tmg': re.compile(
            r'Angaben\s+gem.{1,3}\s+.{1,2}\s*5\s+TMG[:\s]*\n*([A-Za-z\u00C4\u00D6\u00DC\u00E4\u00F6\u00FC\u00DF\s&\-\.]{3,60}(?:GmbH|AG|UG|KG|OHG|GbR|e\.K\.|KGaA|PartG|eG|e\.V\.))',
            re.IGNORECASE | re.MULTILINE
        ),
        'company_betreiber': re.compile(
            r'(?:Betreiber|Anbieter|Diensteanbieter)[:\s]+([A-Za-z\u00C4\u00D6\u00DC\u00E4\u00F6\u00FC\u00DF\s&\-\.]{3,60}(?:GmbH|AG|UG|KG|OHG|GbR|e\.K\.|KGaA|PartG|eG|e\.V\.))',
            re.IGNORECASE
        ),
        'company_with_form': re.compile(
            r'(?:^|\n)([A-Za-z\u00C4\u00D6\u00DC\u00E4\u00F6\u00FC\u00DF][A-Za-z\u00C4\u00D6\u00DC\u00E4\u00F6\u00FC\u00DF\s&\-\.]{2,50})\s+(GmbH|AG|UG|KG|OHG|GbR|e\.K\.|KGaA|PartG|eG|e\.V\.)\s*(?:\n|$|Sitz|Gesch)',
            re.IGNORECASE | re.MULTILINE
        ),
        'company_impressum': re.compile(
            r'Impressum\s+(?:der|des)\s+([A-Za-z\u00C4\u00D6\u00DC\u00E4\u00F6\u00FC\u00DF\s&\-\.]{3,60}(?:GmbH|AG|UG|KG|OHG|GbR|e\.K\.|KGaA))',
            re.IGNORECASE
        ),
        
        # Address patterns
        'address_full': re.compile(
            r'(?:^|\n)([A-Za-z\u00C4\u00D6\u00DC\u00E4\u00F6\u00FC\u00DF\-\.\s]{3,40}(?:stra.e|str\.|weg|platz|allee|ring|gasse|damm|ufer)\s*\d{1,5}[a-z]?)\s*[,\n]\s*(\d{5})\s+([A-Za-z\u00C4\u00D6\u00DC\u00E4\u00F6\u00FC\u00DF\-\s]{3,30})(?:\s*\n|$|,|Tel)',
            re.IGNORECASE | re.MULTILINE
        ),
        'address_simple': re.compile(
            r'(?:^|\n)([A-Za-z\u00C4\u00D6\u00DC\u00E4\u00F6\u00FC\u00DF\-\s]{3,40}\s+\d{1,5}[a-z]?)\s*\n\s*(\d{5})\s+([A-Za-z\u00C4\u00D6\u00DC\u00E4\u00F6\u00FC\u00DF\-\s]{3,30})(?:\s*\n|$|,|Tel)',
            re.IGNORECASE | re.MULTILINE
        ),
        'address_labeled': re.compile(
            r'(?:Anschrift|Adresse|Sitz|Gesch.ftssitz)[:\s]+([A-Za-z\u00C4\u00D6\u00DC\u00E4\u00F6\u00FC\u00DF\-\.\s]{3,40}\s+\d{1,5}[a-z]?)[,\s]+(\d{5})\s+([A-Za-z\u00C4\u00D6\u00DC\u00E4\u00F6\u00FC\u00DF\-\s]{3,30})',
            re.IGNORECASE
        ),
        
        # CEO patterns - EXPANDED
        'geschaeftsfuehrer': re.compile(
            r'Gesch.ftsf.hr(?:er|ung|erin)?[:\s]+([A-Za-z\u00C4\u00D6\u00DC\u00E4\u00F6\u00FC\u00DF\.\-\s,]+?)(?:\n|Handelsregister|Registergericht|USt|Telefon|E-Mail|Amtsgericht|HRB|Sitz|$)',
            re.IGNORECASE
        ),
        'vorstand': re.compile(
            r'(?:Vorstand|Vorstandsvorsitzender)[:\s]+([A-Za-z\u00C4\u00D6\u00DC\u00E4\u00F6\u00FC\u00DF\.\-\s,]+?)(?:\n|Handelsregister|Registergericht|USt|Telefon|E-Mail|Amtsgericht|$)',
            re.IGNORECASE
        ),
        'vertretungsberechtigter': re.compile(
            r'Vertretungsberechtigte?r?[:\s]+([A-Za-z\u00C4\u00D6\u00DC\u00E4\u00F6\u00FC\u00DF\.\-\s,]+?)(?:\n|Handelsregister|Registergericht|USt|$)',
            re.IGNORECASE
        ),
        'vertreten_durch': re.compile(
            r'[Vv]ertreten\s+durch[:\s]+(?:den\s+Gesch.ftsf.hrer\s+)?([A-Za-z\u00C4\u00D6\u00DC\u00E4\u00F6\u00FC\u00DF\.\-\s,]+?)(?:\n|Handelsregister|Registergericht|USt|Amtsgericht|$)',
            re.IGNORECASE
        ),
        'inhaber': re.compile(
            r'(?:Inhaber|Inhaberin)[:\s]+([A-Za-z\u00C4\u00D6\u00DC\u00E4\u00F6\u00FC\u00DF\.\-\s]+?)(?:\n|Telefon|E-Mail|$)',
            re.IGNORECASE
        ),
        
        # Registration patterns
        'hrb': re.compile(r'HRB\s*(\d+)\s*([A-Z])?', re.IGNORECASE),
        'hra': re.compile(r'HRA\s*(\d+)\s*([A-Z])?', re.IGNORECASE),
        'amtsgericht': re.compile(
            r'(?:Amtsgericht|AG|Registergericht)[:\s]+([A-Za-z\u00C4\u00D6\u00DC\u00E4\u00F6\u00FC\u00DF\s\-]+?)(?:\s*,|\s*HRB|\s*HRA|\s*\n|$)',
            re.IGNORECASE
        ),
        
        # VAT patterns - EXPANDED
        'ust_idnr': re.compile(
            r'(?:USt\.?-?Id\.?-?Nr\.?|Umsatzsteuer-?(?:Identifikations)?-?(?:nummer|Nr\.?)?|Umsatzsteuer-?ID(?:-?Nr\.?)?|UID(?:-?Nr\.?)?|VAT(?:\s*ID)?)[:\s\.]*\s*(DE\s*\d{3}\s*\d{3}\s*\d{3}|DE\s*\d{9})',
            re.IGNORECASE
        ),
        'vat_standalone': re.compile(
            r'(?:^|\s|:)(DE\s*\d{9})(?:\s|$|[,\.\)])',
            re.MULTILINE
        ),
        'steuernummer': re.compile(
            r'Steuernummer[:\s]*(\d{2,3}/\d{3}/\d{5})',
            re.IGNORECASE
        ),
        
        # Contact patterns
        'telefon': re.compile(
            r'(?:Telefon|Tel\.?|Fon|Phone)[:\s]*([\+\d\s\-\(\)/]+)',
            re.IGNORECASE
        ),
        'fax': re.compile(
            r'(?:Telefax|Fax)[:\s]*([\+\d\s\-\(\)/]+)',
            re.IGNORECASE
        ),
        'email': re.compile(
            r'(?:E-?Mail|Mail|Kontakt)[:\s]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
            re.IGNORECASE
        ),
        'email_standalone': re.compile(
            r'(?:^|\s)([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})(?:\s|$)',
            re.MULTILINE
        ),
    }

    def extract(self, text):
        result = {}
        company_name = self._extract_company_name(text)
        if company_name:
            result['legal_name'] = company_name
            form = self._extract_legal_form(company_name)
            if form:
                result['legal_form'] = form
        address = self._extract_address(text)
        result.update(address)
        ceo = self._extract_ceo(text)
        if ceo:
            result['ceo_name'] = ceo
        directors = self._extract_directors(text)
        if directors:
            result['directors'] = directors
        registration = self._extract_registration(text)
        result.update(registration)
        vat = self._extract_vat(text)
        if vat:
            result['vat_id'] = vat
        contact = self._extract_contact(text)
        result.update(contact)
        return result

    def _extract_company_name(self, text):
        match = self.PATTERNS['company_impressum'].search(text)
        if match:
            name = FieldValidators.validate_company_name(match.group(1))
            if name and len(name) < 80:
                return name
        for pattern_name in ['company_tmg', 'company_betreiber']:
            match = self.PATTERNS[pattern_name].search(text)
            if match:
                name = FieldValidators.validate_company_name(match.group(1))
                if name and len(name) < 80:
                    return name
        match = self.PATTERNS['company_with_form'].search(text)
        if match:
            name = f"{match.group(1).strip()} {match.group(2)}"
            validated = FieldValidators.validate_company_name(name)
            if validated and len(validated) < 80:
                return validated
        legal_forms = ['GmbH', 'AG', 'KG', 'UG', 'e.K.', 'KGaA']
        for form in legal_forms:
            pattern = re.compile(rf'([A-Za-z\u00C4\u00D6\u00DC\u00E4\u00F6\u00FC\u00DF][A-Za-z\u00C4\u00D6\u00DC\u00E4\u00F6\u00FC\u00DF\s&\-\.]+)\s+{re.escape(form)}\b', re.IGNORECASE)
            match = pattern.search(text)
            if match:
                name = f"{match.group(1).strip()} {form}"
                validated = FieldValidators.validate_company_name(name)
                if validated and len(validated) < 80:
                    return validated
        return None

    def _extract_legal_form(self, company_name):
        forms = ['GmbH', 'AG', 'UG', 'KG', 'OHG', 'GbR', 'e.K.', 'KGaA', 'PartG', 'eG', 'e.V.']
        for form in forms:
            if form in company_name:
                return form
        return None

    def _extract_address(self, text):
        result = {}
        match = self.PATTERNS['address_labeled'].search(text)
        if not match:
            match = self.PATTERNS['address_full'].search(text)
        if not match:
            match = self.PATTERNS['address_simple'].search(text)
        if match:
            street = match.group(1).strip()
            zip_code = match.group(2).strip()
            city = match.group(3).strip()
            city = re.sub(r'\s*(Telefon|Tel|Fax|E-Mail|Gesch|Deutschland).*$', '', city, flags=re.IGNORECASE).strip()
            validated = FieldValidators.validate_address(street=street, zip_code=zip_code, city=city, country='Germany')
            if validated.get('street'):
                result['street_address'] = validated['street']
            if validated.get('zip'):
                result['postal_code'] = validated['zip']
            if validated.get('city'):
                result['city'] = validated['city']
            result['country'] = 'Germany'
        return result

    def _extract_ceo(self, text):
        for pattern_name in ['geschaeftsfuehrer', 'vorstand', 'vertretungsberechtigter', 'vertreten_durch', 'inhaber']:
            match = self.PATTERNS[pattern_name].search(text)
            if match:
                names_text = match.group(1)
                names = re.split(r'[,;]|\s+und\s+|\s+&\s+', names_text)
                for name in names:
                    validated = FieldValidators.validate_person_name(name.strip())
                    if validated:
                        return validated
        return None

    def _extract_directors(self, text):
        directors = []
        for pattern_name in ['geschaeftsfuehrer', 'vorstand', 'vertretungsberechtigter']:
            match = self.PATTERNS[pattern_name].search(text)
            if match:
                names_text = match.group(1)
                names = re.split(r'[,;]|\s+und\s+|\s+&\s+', names_text)
                for name in names:
                    validated = FieldValidators.validate_person_name(name.strip())
                    if validated and validated not in directors:
                        directors.append(validated)
        return directors

    def _extract_registration(self, text):
        result = {}
        hrb_match = self.PATTERNS['hrb'].search(text)
        if hrb_match:
            suffix = hrb_match.group(2) or ''
            result['registration_number'] = f"HRB {hrb_match.group(1)}{suffix}"
            result['register_type'] = 'Handelsregister B'
        else:
            hra_match = self.PATTERNS['hra'].search(text)
            if hra_match:
                suffix = hra_match.group(2) or ''
                result['registration_number'] = f"HRA {hra_match.group(1)}{suffix}"
                result['register_type'] = 'Handelsregister A'
        match = self.PATTERNS['amtsgericht'].search(text)
        if match:
            court = match.group(1).strip()
            if 3 < len(court) < 50:
                result['register_court'] = f"Amtsgericht {court}" if 'Amtsgericht' not in court else court
        return result

    def _extract_vat(self, text):
        match = self.PATTERNS['ust_idnr'].search(text)
        if match:
            vat = match.group(1).replace(' ', '')
            validated = FieldValidators.validate_vat_id(vat)
            if validated:
                return validated
        match = self.PATTERNS['vat_standalone'].search(text)
        if match:
            vat = match.group(1).replace(' ', '')
            validated = FieldValidators.validate_vat_id(vat)
            if validated:
                return validated
        return None

    def _extract_contact(self, text):
        result = {}
        match = self.PATTERNS['telefon'].search(text)
        if match:
            phone = FieldValidators.validate_phone(match.group(1), 'DE')
            if phone:
                result['phone'] = phone
        match = self.PATTERNS['fax'].search(text)
        if match:
            fax = FieldValidators.validate_fax(match.group(1), 'DE')
            if fax:
                result['fax'] = fax
        match = self.PATTERNS['email'].search(text)
        if match:
            email = FieldValidators.validate_email(match.group(1))
            if email:
                result['email'] = email
        if not result.get('email'):
            match = self.PATTERNS['email_standalone'].search(text)
            if match:
                email = FieldValidators.validate_email(match.group(1))
                if email:
                    result['email'] = email
        return result
