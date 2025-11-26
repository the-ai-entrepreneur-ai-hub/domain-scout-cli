"""
UK Legal Extractor - Specialized for UK company legal notices.
"""
import re
from typing import Dict, Optional, List
from ..field_validators import FieldValidators

class UKExtractor:
    """Extracts legal information from UK legal notice pages."""
    
    PATTERNS = {
        # Company name patterns
        'company_name': re.compile(
            r'(?:Company Name|Registered Name|Trading As)[:\s]+([A-Za-z\s&\-\.]+(?:Limited|Ltd\.?|PLC|LLP|CIC))',
            re.IGNORECASE
        ),
        'company_with_form': re.compile(
            r'([A-Za-z][A-Za-z\s&\-\.]{2,50})\s+(Limited|Ltd\.?|PLC|LLP|CIC)\b',
            re.IGNORECASE
        ),
        
        # Company number (8 digits)
        'company_number': re.compile(
            r'(?:Company\s*(?:Number|No\.?)|Registration\s*(?:Number|No\.?)|Registered\s*(?:Number|No\.?))[:\s]*(\d{8})',
            re.IGNORECASE
        ),
        'company_number_short': re.compile(
            r'(?:Company\s*No\.?|Reg\.?\s*No\.?)[:\s]*(\d{8})',
            re.IGNORECASE
        ),
        
        # Registered office address
        'registered_office': re.compile(
            r'Registered\s+(?:Office|Address)[:\s]+([^\n]+(?:\n[^\n]+)?)',
            re.IGNORECASE
        ),
        'address_uk': re.compile(
            r'([A-Za-z\s\-\.]+\d*[A-Za-z\s\-\.]*)[,\n]\s*([A-Za-z\s\-\.]+)[,\n]\s*([A-Z]{1,2}\d{1,2}\s*\d[A-Z]{2})',
            re.IGNORECASE
        ),
        
        # Directors
        'directors': re.compile(
            r'Directors?[:\s]+([A-Za-z\s,\.]+?)(?:\n|Company|Registered|VAT|$)',
            re.IGNORECASE
        ),
        
        # VAT
        'vat_number': re.compile(
            r'VAT\s*(?:Number|No\.?|Registration)[:\s]*(GB\s*\d{9,12})',
            re.IGNORECASE
        ),
        'vat_simple': re.compile(
            r'VAT[:\s]*(GB\s*\d{9,12})',
            re.IGNORECASE
        ),
        
        # Contact
        'telephone': re.compile(
            r'(?:Telephone|Tel\.?|Phone)[:\s]*([\+\d\s\-\(\)]+)',
            re.IGNORECASE
        ),
        'email': re.compile(
            r'(?:Email|E-mail)[:\s]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
            re.IGNORECASE
        ),
        
        # Registered in England
        'registered_in': re.compile(
            r'Registered\s+in\s+(England(?:\s+(?:and|&)\s+Wales)?|Scotland|Northern Ireland)',
            re.IGNORECASE
        ),
    }

    def extract(self, text: str) -> Dict:
        """Extract legal information from UK text."""
        result = {}
        
        # Extract company name
        company_name = self._extract_company_name(text)
        if company_name:
            result['legal_name'] = company_name
            form = self._extract_legal_form(company_name)
            if form:
                result['legal_form'] = form
                
        # Extract company number
        company_number = self._extract_company_number(text)
        if company_number:
            result['registration_number'] = company_number
            result['register_type'] = 'Companies House'
            
        # Extract registered location
        registered_in = self._extract_registered_location(text)
        if registered_in:
            result['register_court'] = f"Companies House ({registered_in})"
            
        # Extract address
        address = self._extract_address(text)
        result.update(address)
        
        # Extract directors
        directors = self._extract_directors(text)
        if directors:
            result['ceo_name'] = directors[0] if directors else None
            result['directors'] = directors
            
        # Extract VAT
        vat = self._extract_vat(text)
        if vat:
            result['vat_id'] = vat
            
        # Extract contact
        contact = self._extract_contact(text)
        result.update(contact)
        
        # Set country
        result['country'] = 'United Kingdom'
        
        return result

    def _extract_company_name(self, text: str) -> Optional[str]:
        """Extract company name."""
        match = self.PATTERNS['company_name'].search(text)
        if match:
            name = FieldValidators.validate_company_name(match.group(1))
            if name:
                return name
                
        match = self.PATTERNS['company_with_form'].search(text)
        if match:
            name = f"{match.group(1).strip()} {match.group(2)}"
            return FieldValidators.validate_company_name(name)
            
        return None

    def _extract_legal_form(self, company_name: str) -> Optional[str]:
        """Extract legal form."""
        forms = {'Limited': 'Ltd', 'Ltd.': 'Ltd', 'Ltd': 'Ltd', 
                 'PLC': 'PLC', 'LLP': 'LLP', 'CIC': 'CIC'}
        for form, normalized in forms.items():
            if form in company_name:
                return normalized
        return None

    def _extract_company_number(self, text: str) -> Optional[str]:
        """Extract Companies House number."""
        for pattern_name in ['company_number', 'company_number_short']:
            match = self.PATTERNS[pattern_name].search(text)
            if match:
                number = match.group(1)
                if len(number) == 8:
                    return number
        return None

    def _extract_registered_location(self, text: str) -> Optional[str]:
        """Extract where company is registered."""
        match = self.PATTERNS['registered_in'].search(text)
        if match:
            return match.group(1)
        return None

    def _extract_address(self, text: str) -> Dict:
        """Extract UK address."""
        result = {}
        
        # Try registered office pattern
        match = self.PATTERNS['registered_office'].search(text)
        if match:
            address_text = match.group(1)
            # Try to parse UK postcode
            postcode_match = re.search(r'([A-Z]{1,2}\d{1,2}\s*\d[A-Z]{2})', address_text, re.IGNORECASE)
            if postcode_match:
                result['postal_code'] = postcode_match.group(1).upper()
                # Extract street (before postcode)
                street_part = address_text[:postcode_match.start()].strip().rstrip(',')
                parts = [p.strip() for p in street_part.split(',')]
                if parts:
                    result['street_address'] = parts[0]
                    if len(parts) > 1:
                        result['city'] = parts[-1]
                        
        # Try address pattern
        if not result:
            match = self.PATTERNS['address_uk'].search(text)
            if match:
                validated = FieldValidators.validate_address(
                    street=match.group(1),
                    zip_code=match.group(3),
                    city=match.group(2),
                    country='United Kingdom'
                )
                result.update(validated)
                
        return result

    def _extract_directors(self, text: str) -> List[str]:
        """Extract directors."""
        directors = []
        match = self.PATTERNS['directors'].search(text)
        if match:
            names_text = match.group(1)
            names = re.split(r'[,;]|\s+and\s+|\s+&\s+', names_text)
            for name in names:
                validated = FieldValidators.validate_person_name(name.strip())
                if validated:
                    directors.append(validated)
        return directors

    def _extract_vat(self, text: str) -> Optional[str]:
        """Extract VAT number."""
        for pattern_name in ['vat_number', 'vat_simple']:
            match = self.PATTERNS[pattern_name].search(text)
            if match:
                vat = match.group(1).replace(' ', '')
                return FieldValidators.validate_vat_id(vat)
        return None

    def _extract_contact(self, text: str) -> Dict:
        """Extract contact information."""
        result = {}
        
        match = self.PATTERNS['telephone'].search(text)
        if match:
            phone = FieldValidators.validate_phone(match.group(1), 'GB')
            if phone:
                result['phone'] = phone
                
        match = self.PATTERNS['email'].search(text)
        if match:
            email = FieldValidators.validate_email(match.group(1))
            if email:
                result['email'] = email
                
        return result
