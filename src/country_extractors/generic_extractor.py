"""
Generic Legal Extractor - Fallback for any country.
"""
import re
from typing import Dict, Optional, List
from ..field_validators import FieldValidators

class GenericExtractor:
    """Generic extractor for legal information from any country."""
    
    # All known legal forms
    ALL_LEGAL_FORMS = [
        'GmbH', 'AG', 'KG', 'UG', 'OHG', 'GbR', 'e.K.', 'KGaA', 'PartG', 'eG', 'e.V.',
        'Ltd', 'Ltd.', 'Limited', 'PLC', 'LLP', 'CIC',
        'Inc.', 'Inc', 'LLC', 'Corp.', 'Corp', 'Corporation', 'LP', 'PC',
        'SARL', 'SAS', 'SASU', 'SA', 'EURL', 'SNC', 'SCS', 'SCA',
        'S.r.l.', 'Srl', 'S.p.A.', 'SpA', 'S.a.s.', 'S.n.c.',
        'S.L.', 'SL', 'S.A.', 'S.L.L.', 'S.C.',
        'B.V.', 'BV', 'N.V.', 'NV', 'V.O.F.', 'C.V.',
        'BVBA', 'CVBA', 'VOF',
    ]
    
    PATTERNS = {
        # Generic company patterns
        'company_name': re.compile(
            r'(?:Company Name|Legal Name|Business Name|Registered Name|Firma|Raison sociale)[:\s]+([^\n]+)',
            re.IGNORECASE
        ),
        
        # Address patterns for various formats
        'address_generic': re.compile(
            r'(?:Address|Registered Office|Siège|Sitz|Indirizzo)[:\s]+([^\n]+(?:\n[^\n]+)?)',
            re.IGNORECASE
        ),
        
        # Registration patterns
        'registration_generic': re.compile(
            r'(?:Registration|Registered|Company No|Reg\.?\s*No)[:\s]*([A-Z0-9\s\-]+)',
            re.IGNORECASE
        ),
        
        # VAT patterns for multiple countries
        'vat_generic': re.compile(
            r'(?:VAT|TVA|USt|IVA|BTW|MWST|GST)[\s\-\.]*(?:No\.?|Number|ID|Nr\.?)?[:\s]*([A-Z]{2}\s*[\dA-Z\s]+)',
            re.IGNORECASE
        ),
        
        # Director/CEO patterns
        'director_generic': re.compile(
            r'(?:CEO|Director|Managing Director|Geschäftsführer|Gérant|Amministratore)[:\s]+([A-Za-zÀ-ÿ\.\-\s]+?)(?:\n|$)',
            re.IGNORECASE
        ),
        
        # Phone patterns
        'phone_generic': re.compile(
            r'(?:Phone|Telephone|Tel|Fon|Telefono|Téléphone)[:\s]*([\+\d\s\-\(\)\.]+)',
            re.IGNORECASE
        ),
        
        # Email patterns
        'email_generic': re.compile(
            r'(?:Email|E-mail|Mail|Correo)[:\s]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
            re.IGNORECASE
        ),
        
        # Fax patterns
        'fax_generic': re.compile(
            r'(?:Fax|Telefax)[:\s]*([\+\d\s\-\(\)\.]+)',
            re.IGNORECASE
        ),
    }

    def extract(self, text: str, country_hint: str = None) -> Dict:
        """Extract legal information from text."""
        result = {}
        
        # Extract company name and legal form
        company = self._extract_company(text)
        if company:
            result['legal_name'] = company['name']
            if company.get('form'):
                result['legal_form'] = company['form']
                
        # Extract address
        address = self._extract_address(text)
        result.update(address)
        
        # Extract registration
        registration = self._extract_registration(text)
        result.update(registration)
        
        # Extract VAT
        vat = self._extract_vat(text)
        if vat:
            result['vat_id'] = vat
            
        # Extract director
        director = self._extract_director(text)
        if director:
            result['ceo_name'] = director
            
        # Extract contact
        contact = self._extract_contact(text)
        result.update(contact)
        
        return result

    def _extract_company(self, text: str) -> Optional[Dict]:
        """Extract company name and legal form."""
        # Try named pattern first
        match = self.PATTERNS['company_name'].search(text)
        if match:
            name = match.group(1).strip()
            validated = FieldValidators.validate_company_name(name)
            if validated:
                form = self._find_legal_form(validated)
                return {'name': validated, 'form': form}
                
        # Try to find company with legal form
        for form in self.ALL_LEGAL_FORMS:
            pattern = re.compile(
                rf'([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s&\-\.]+)\s+{re.escape(form)}\b',
                re.IGNORECASE
            )
            match = pattern.search(text)
            if match:
                full_name = f"{match.group(1).strip()} {form}"
                validated = FieldValidators.validate_company_name(full_name)
                if validated:
                    return {'name': validated, 'form': form}
                    
        return None

    def _find_legal_form(self, company_name: str) -> Optional[str]:
        """Find legal form in company name."""
        for form in self.ALL_LEGAL_FORMS:
            if form.lower() in company_name.lower():
                return form
        return None

    def _extract_address(self, text: str) -> Dict:
        """Extract address information."""
        result = {}
        
        match = self.PATTERNS['address_generic'].search(text)
        if match:
            address_text = match.group(1)
            
            # Try to find postal code patterns
            # European (4-5 digits)
            zip_match = re.search(r'(\d{4,5})\s+([A-Za-zÀ-ÿ\s\-]+)', address_text)
            if zip_match:
                result['postal_code'] = zip_match.group(1)
                result['city'] = zip_match.group(2).strip()
                street = address_text[:zip_match.start()].strip().rstrip(',')
                if street:
                    result['street_address'] = street
            else:
                # UK postcode
                uk_zip = re.search(r'([A-Z]{1,2}\d{1,2}\s*\d[A-Z]{2})', address_text, re.IGNORECASE)
                if uk_zip:
                    result['postal_code'] = uk_zip.group(1).upper()
                    
        return result

    def _extract_registration(self, text: str) -> Dict:
        """Extract registration information."""
        result = {}
        
        match = self.PATTERNS['registration_generic'].search(text)
        if match:
            reg_num = match.group(1).strip()
            validated = FieldValidators.validate_registration_number(reg_num)
            if validated:
                result['registration_number'] = validated
                
        return result

    def _extract_vat(self, text: str) -> Optional[str]:
        """Extract VAT number."""
        match = self.PATTERNS['vat_generic'].search(text)
        if match:
            vat = match.group(1).replace(' ', '')
            return FieldValidators.validate_vat_id(vat)
        return None

    def _extract_director(self, text: str) -> Optional[str]:
        """Extract director/CEO name."""
        match = self.PATTERNS['director_generic'].search(text)
        if match:
            return FieldValidators.validate_person_name(match.group(1).strip())
        return None

    def _extract_contact(self, text: str) -> Dict:
        """Extract contact information."""
        result = {}
        
        # Phone
        match = self.PATTERNS['phone_generic'].search(text)
        if match:
            phone = FieldValidators.validate_phone(match.group(1))
            if phone:
                result['phone'] = phone
                
        # Email
        match = self.PATTERNS['email_generic'].search(text)
        if match:
            email = FieldValidators.validate_email(match.group(1))
            if email:
                result['email'] = email
                
        # Fax
        match = self.PATTERNS['fax_generic'].search(text)
        if match:
            fax = FieldValidators.validate_fax(match.group(1))
            if fax:
                result['fax'] = fax
                
        return result
