import spacy
import logging

class SpacyExtractor:
    _instance = None
    _model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SpacyExtractor, cls).__new__(cls)
            cls._instance._initialize_model()
        return cls._instance

    def _initialize_model(self):
        self.logger = logging.getLogger(__name__)
        try:
            self.logger.info("Loading spaCy German model (de_core_news_md)...")
            self._model = spacy.load("de_core_news_md")
            self.logger.info("spaCy model loaded successfully.")
        except Exception as e:
            self.logger.error(f"Failed to load spaCy model: {e}")
            self._model = None

    def get_doc(self, text):
        if not self._model or not text:
            return None
        # Limit text length to avoid memory issues with massive pages
        return self._model(text[:100000])

    def extract_entities(self, text):
        """Extract entities from text"""
        doc = self.get_doc(text)
        if not doc:
            return {'orgs': [], 'locs': [], 'pers': []}
        
        return {
            'orgs': [ent.text for ent in doc.ents if ent.label_ == 'ORG'],
            'locs': [ent.text for ent in doc.ents if ent.label_ in ['LOC', 'GPE']],
            'pers': [ent.text for ent in doc.ents if ent.label_ == 'PER'],
        }

    def validate_city(self, city_candidate):
        """Check if a string is a valid location"""
        if not city_candidate or not self._model:
            return False
        
        # Simple heuristic: Capitalized?
        if not city_candidate[0].isupper():
            return False
            
        doc = self._model(city_candidate)
        if not doc.ents:
            # Maybe it's just one token and model needs context? 
            # Try context: "in [City]"
            doc_ctx = self._model(f"in {city_candidate}")
            for ent in doc_ctx.ents:
                if ent.label_ in ['LOC', 'GPE'] and city_candidate in ent.text:
                    return True
            return False
        
        for ent in doc.ents:
            if ent.label_ in ['LOC', 'GPE']:
                return True
        return False

    def is_company(self, name_candidate):
        """Check if a string looks like a company"""
        if not name_candidate or not self._model:
            return False
            
        doc = self._model(name_candidate)
        for ent in doc.ents:
            if ent.label_ == 'ORG':
                return True
        return False
