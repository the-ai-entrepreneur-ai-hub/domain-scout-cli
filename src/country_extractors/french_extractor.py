"""
French Legal Extractor - Specialized for French Mentions Légales pages.
"""
import re
from typing import Dict, Optional, List
from ..field_validators import FieldValidators

class FrenchExtractor:
    """Extracts legal information from French legal notice pages."""
    
    PATTERNS = {
        # Company name patterns
        'raison_sociale': re.compile(
            r'(?:Raison sociale|Dénomination sociale)[:\s]+([A-Za-zÀ-ÿ\s&\-\.]+(?:SARL|SAS|SASU|SA|EURL|SNC|SCS|SCA))',
            re.IGNORECASE
        ),
        'editeur': re.compile(
            r'(?:Éditeur|Editeur)[:\s]+([A-Za-zÀ-ÿ\s&\-\.]+)',
            re.IGNORECASE
        ),
        'company_with_form': re.compile(
            r'([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s&\-\.]{2,50})\s+(SARL|SAS|SASU|SA|EURL|SNC|SCS|SCA)\b',
            re.IGNORECASE
        ),
        
        # Address patterns
        'siege_social': re.compile(
            r'(?:Siège social|Siége social|Adresse)[:\s]+([^\n]+(?:\n[^\n]+)?)',
            re.IGNORECASE
        ),
        'address_fr': re.compile(
            r'([A-Za-zÀ-ÿ\s\-\.]+\d+[A-Za-zÀ-ÿ\s\-\.]*)[,\n]\s*(\d{5})\s+([A-Za-zÀ-ÿ\s\-\.]+)',
            re.IGNORECASE
        ),
        
        # RCS (Registre du Commerce et des Sociétés)
        'rcs': re.compile(
            r'RCS\s+([A-Za-zÀ-ÿ\-\s]+)\s+(\d+)',
            re.IGNORECASE
        ),
        'rcs_simple': re.compile(
            r'RCS[:\s]+([A-Za-zÀ-ÿ\-\s]+\s+\d+)',
            re.IGNORECASE
        ),
        
        # SIRET/SIREN
        'siret': re.compile(
            r'SIRET[:\s]*(\d{14})',
            re.IGNORECASE
        ),
        'siren': re.compile(
            r'SIREN[:\s]*(\d{9})',
            re.IGNORECASE
        ),
        
        # Capital social
        'capital': re.compile(
            r'Capital\s+(?:social)?[:\s]*(\d[\d\s]*(?:€|EUR|euros?))',
            re.IGNORECASE
        ),
        
        # TVA (VAT)
        'tva': re.compile(
            r'(?:TVA|N°\s*TVA|Numéro\s*TVA)[:\s]*(FR\s*[A-Z0-9]{2}\s*\d{9})',
            re.IGNORECASE
        ),
        
        # Director/Gérant
        'gerant': re.compile(
            r'(?:Gérant|Directeur|Président)[:\s]+([A-Za-zÀ-ÿ\.\-\s]+?)(?:\n|Capital|RCS|SIRET|$)',
            re.IGNORECASE
        ),
        'directeur_publication': re.compile(
            r'Directeur\s+(?:de\s+)?(?:la\s+)?publication[:\s]+([A-Za-zÀ-ÿ\.\-\s]+?)(?:\n|$)',
            re.IGNORECASE
        ),
        
        # Contact
        'telephone': re.compile(
            r'(?:Téléphone|Tél\.?|Tel\.?)[:\s]*([\+\d\s\-\(\)\.]+)',
            re.IGNORECASE
        ),
        'email': re.compile(
            r'(?:E-mail|Email|Mail|Courriel)[:\s]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
            re.IGNORECASE
        ),
    }

    def extract(self, text: str) -> Dict:
        """Extract legal information from French text."""
        result = {}
        
        # Extract company name
        company_name = self._extract_company_name(text)
        if company_name:
            result['legal_name'] = company_name
            form = self._extract_legal_form(company_name)
            if form:
                result['legal_form'] = form
                
        # Extract address
        address = self._extract_address(text)
        result.update(address)
        
        # Extract RCS
        rcs = self._extract_rcs(text)
        result.update(rcs)
        
        # Extract SIRET/SIREN
        siret = self._extract_siret(text)
        if siret:
            result['siret'] = siret
        siren = self._extract_siren(text)
        if siren:
            result['siren'] = siren
            
        # Extract TVA
        tva = self._extract_tva(text)
        if tva:
            result['vat_id'] = tva
            
        # Extract director
        director = self._extract_director(text)
        if director:
            result['ceo_name'] = director
            
        # Extract contact
        contact = self._extract_contact(text)
        result.update(contact)
        
        # Set country
        result['country'] = 'France'
        
        return result

    def _extract_company_name(self, text: str) -> Optional[str]:
        """Extract company name."""
        for pattern_name in ['raison_sociale', 'editeur']:
            match = self.PATTERNS[pattern_name].search(text)
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
        forms = ['SARL', 'SAS', 'SASU', 'SA', 'EURL', 'SNC', 'SCS', 'SCA']
        for form in forms:
            if form in company_name.upper():
                return form
        return None

    def _extract_address(self, text: str) -> Dict:
        """Extract French address."""
        result = {}
        
        match = self.PATTERNS['siege_social'].search(text)
        if match:
            address_text = match.group(1)
            # Try to parse French postal code (5 digits)
            zip_match = re.search(r'(\d{5})\s+([A-Za-zÀ-ÿ\s\-]+)', address_text)
            if zip_match:
                result['postal_code'] = zip_match.group(1)
                result['city'] = zip_match.group(2).strip()
                # Street is before postal code
                street_part = address_text[:zip_match.start()].strip().rstrip(',')
                if street_part:
                    result['street_address'] = street_part
                    
        if not result:
            match = self.PATTERNS['address_fr'].search(text)
            if match:
                validated = FieldValidators.validate_address(
                    street=match.group(1),
                    zip_code=match.group(2),
                    city=match.group(3),
                    country='France'
                )
                result.update(validated)
                
        return result

    def _extract_rcs(self, text: str) -> Dict:
        """Extract RCS information."""
        result = {}
        
        match = self.PATTERNS['rcs'].search(text)
        if match:
            result['register_court'] = f"RCS {match.group(1).strip()}"
            result['registration_number'] = match.group(2)
            result['register_type'] = 'RCS'
        else:
            match = self.PATTERNS['rcs_simple'].search(text)
            if match:
                result['registration_number'] = match.group(1).strip()
                result['register_type'] = 'RCS'
                
        return result

    def _extract_siret(self, text: str) -> Optional[str]:
        """Extract SIRET number."""
        match = self.PATTERNS['siret'].search(text)
        if match:
            siret = match.group(1)
            if len(siret) == 14:
                return siret
        return None

    def _extract_siren(self, text: str) -> Optional[str]:
        """Extract SIREN number."""
        match = self.PATTERNS['siren'].search(text)
        if match:
            siren = match.group(1)
            if len(siren) == 9:
                return siren
        return None

    def _extract_tva(self, text: str) -> Optional[str]:
        """Extract TVA (VAT) number."""
        match = self.PATTERNS['tva'].search(text)
        if match:
            tva = match.group(1).replace(' ', '')
            return FieldValidators.validate_vat_id(tva)
        return None

    def _extract_director(self, text: str) -> Optional[str]:
        """Extract director/gérant name."""
        for pattern_name in ['gerant', 'directeur_publication']:
            match = self.PATTERNS[pattern_name].search(text)
            if match:
                name = FieldValidators.validate_person_name(match.group(1).strip())
                if name:
                    return name
        return None

    def _extract_contact(self, text: str) -> Dict:
        """Extract contact information."""
        result = {}
        
        match = self.PATTERNS['telephone'].search(text)
        if match:
            phone = FieldValidators.validate_phone(match.group(1), 'FR')
            if phone:
                result['phone'] = phone
                
        match = self.PATTERNS['email'].search(text)
        if match:
            email = FieldValidators.validate_email(match.group(1))
            if email:
                result['email'] = email
                
        return result
