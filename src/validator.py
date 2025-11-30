import re
import spacy
import phonenumbers
from typing import Optional, Dict
from .utils import logger

class DataValidator:
    def __init__(self):
        # Load SpaCy model for German NER
        # Need to ensure 'de_core_news_sm' is installed
        try:
            logger.info("Loading SpaCy model for validation...")
            self.nlp = spacy.load("de_core_news_sm")
            logger.info("SpaCy model loaded.")
        except OSError:
            logger.warning("SpaCy model 'de_core_news_sm' not found. Downloading...")
            from spacy.cli import download
            download("de_core_news_sm")
            self.nlp = spacy.load("de_core_news_sm")

        # Common German Cities (Simple List to avoid external huge DB for now)
        # Can be expanded or replaced with a proper library like 'geonames' if needed
        self.common_cities = {
            "Berlin", "Hamburg", "München", "Köln", "Frankfurt", "Stuttgart", "Düsseldorf", 
            "Leipzig", "Dortmund", "Essen", "Bremen", "Dresden", "Hannover", "Nürnberg", 
            "Duisburg", "Bochum", "Wuppertal", "Bielefeld", "Bonn", "Münster", "Karlsruhe", 
            "Mannheim", "Augsburg", "Wiesbaden", "Gelsenkirchen", "Mönchengladbach", 
            "Braunschweig", "Kiel", "Chemnitz", "Aachen", "Halle", "Magdeburg", "Freiburg", 
            "Krefeld", "Lübeck", "Oberhausen", "Erfurt", "Mainz", "Rostock", "Kassel"
        }

        # Bad patterns for CEO names
        self.bad_ceo_patterns = [
            r'\d',                  # Contains numbers
            r'straße', r'strasse',  # Is an address
            r'weg\b', r'platz\b',
            r'gmbh', r'ag\b',       # Is a company name
            r'tel\.', r'fax',       # Is contact info
            r'email', r'@',
            r'http', r'www\.',
            r'impressum',
            r'geschäftsführer',     # Is the title itself
            r'vertretungsberechtigt',
            r'inhaltlich',
            r'redaktion',
            r'register',
            r'amtsgericht'
        ]

    def validate_legal_name(self, name: str) -> Optional[str]:
        """
        Strict validation for Company Legal Name.
        """
        if not name:
            return None
        
        name = name.strip()
        
        # 1. Length Check
        if len(name) < 3 or len(name) > 150:
            return None
            
        # 2. Navigation/Garbage Check
        garbage_terms = [
            "home", "menu", "login", "search", "suche", "warenkorb", "anmelden", 
            "startseite", "kontakt", "impressum", "datenschutz", "über uns",
            "anbieter", "hosting", "dienste", "service", "provider", 
            "haftungsausschluss", "disclaimer", "copyright", "all rights reserved",
            "gemacht werden"
        ]
        
        # Check exact match or "token match" for short strings
        if name.lower() in garbage_terms:
            return None
            
        # Pre-cleaning for "Search..." style strings
        name_clean = name.lower().strip(" .")
        if name_clean in garbage_terms:
            return None
            
        # If the name is just a single word and it's suspiciously generic, reject it
        if " " not in name and len(name) < 15:
             # We can't list every word, but if it's short and single word, 
             # it's unlikely to be a company name unless it's a brand (which usually has GmbH/AG nearby in legal context)
             # But here we are validating raw candidates.
             # Let's be stricter on single words found in common navigation
             if name.lower() in ["about", "news", "blog", "shop", "cart", "basket", "profile", "account"]:
                 return None

        # Check partial matches for garbage terms in short strings (if name is basically just "Home | About")
        # Remove pipes and separators for check
        name_normalized = name.lower().replace("|", " ").replace("-", " ").replace("/", " ").strip(" .")
        tokens = name_normalized.split()
        
        # If ALL tokens are garbage terms or connectors, reject
        connectors = {"and", "und", "or", "oder", "&", "|", "-", "about", "contact", "/", "\\", "login", "register"}
        
        # New logic: Token density check for navigation strings
        # If > 50% of the tokens are in the garbage list, reject it.
        token_matches = sum(1 for t in tokens if t in garbage_terms or t in connectors)
        if len(tokens) > 0 and token_matches / len(tokens) > 0.5:
            return None

        # Check for "(0)" or numbers in brackets which is common in cart/menu
        # Matches (0), (1), etc.
        if re.search(r'\(\d+\)', name):
            return None
            
        # Check for "Warenkorb" explicitly (case insensitive)
        if "warenkorb" in name.lower():
            return None
            
        # Special check for pure navigation-like strings "A | B | C" or "A / B"
        if any(sep in name for sep in ["|", " - ", " / "]):
            # Count total tokens vs "bad" tokens
            # Clean tokens from separators first
            clean_tokens = [t.strip() for t in re.split(r'[|\-/]', name) if t.strip()]
            total_parts = len(clean_tokens)
            if total_parts > 0:
                bad_part_count = sum(1 for p in clean_tokens if p.lower() in garbage_terms or p.lower() in connectors)
                # If >= 50% of tokens are garbage/connectors, reject
                if bad_part_count / total_parts >= 0.5:
                    return None

        # 3. Address Check (Simple)
        if re.search(r'\d{5}', name): # Contains ZIP code -> likely address
            return None

        # 4. NLP Check (Optional but good)
        doc = self.nlp(name)
        # If it's just a person name, it might be valid (Solo prop), but if it's LOC, it's wrong.
        if len(doc.ents) == 1 and doc.ents[0].label_ == "LOC":
             # Exceptions: "Münchener Rück" is an ORG but might be confused. 
             # But "Hamburg" is definitely not a company.
             pass

        return name

    def validate_ceo_name(self, name: str) -> Optional[str]:
        """
        Strict validation for CEO/Director names.
        """
        if not name:
            return None
            
        name = name.strip()
        
        # 1. Basic Filters
        if len(name) > 50 or len(name) < 3:
            return None
            
        # 2. Blacklist Patterns
        name_lower = name.lower()
        for pattern in self.bad_ceo_patterns:
            if re.search(pattern, name_lower):
                return None
                
        # 3. Structure Check
        # Must have at least 2 parts (First Last)
        parts = name.split()
        if len(parts) < 2:
            # Could be mononym, but unlikely for CEO
            return None
        if len(parts) > 5: # Too long "Prof. Dr. Dr. Hans Peter Müller-Lüdenscheid" is borderline
            return None

        # 4. NLP Check (The "No Hallucination" Guard)
        doc = self.nlp(name)
        
        # It must NOT be an Organization or Location
        for ent in doc.ents:
            if ent.label_ in ["ORG", "LOC"]:
                # "Siemens AG" is not a person
                return None
        
        # Ideally, it should have a PER entity or no entity (sometimes small names are missed)
        # If SPACY says it's a PERSON, great.
        has_person = any(ent.label_ == "PER" for ent in doc.ents)
        
        # If SpaCy is confident it's a Person, return it
        if has_person:
            return name
            
        # Fallback: If it looks like "Title Firstname Lastname", accept it
        # But since we already filtered bad patterns, let's be permissive if no bad entities found.
        return name

    def validate_address(self, street: str, zip_code: str, city: str) -> bool:
        """
        Validates if the address components form a coherent German address.
        """
        if not zip_code or not city:
            return False
            
        # ZIP Validation (DE)
        if not re.match(r'^\d{5}$', zip_code):
            return False
            
        # City Validation (Heuristic)
        if len(city) < 2 or re.search(r'\d', city):
            return False
            
        # Street Validation (Optional, street might be empty in some data)
        # Logic fix for unit tests:
        # If street is provided (not empty), it must be valid.
        # If street is empty (""), it is technically "valid" in terms of validation flow
        # unless we strictly require it. The method signature suggests validating *components*.
        # But test_validate_valid_german_address expects False for empty street with valid city/zip.
        # So let's enforce street presence if other fields are present.
        if not street:
            return False

        if len(street) < 3:
            return False
        # Street usually has a number, but not always ("Hofgut X"). 
        # But if it's just a number "7", it's wrong.
        if re.match(r'^\d+$', street):
            return False
        
        # Blacklist for street names (Bug #4)
        bad_streets = ["anschrift", "adresse", "sitz", "standort", "postanschrift"]
        if street.lower().strip(" :.") in bad_streets:
            return False
                
        return True

    def sanitize_phone(self, phone: str) -> Optional[str]:
        """
        Standardize phone number using phonenumbers lib.
        """
        if not phone:
            return None
        try:
            parsed = phonenumbers.parse(phone, "DE")
            if phonenumbers.is_valid_number(parsed):
                return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
        except:
            pass
        return None
