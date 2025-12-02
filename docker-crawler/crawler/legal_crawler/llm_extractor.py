"""
LLM Extractor - Uses local Ollama for intelligent extraction
FREE - No API costs, runs locally
Falls back gracefully if Ollama unavailable
"""

import os
import json
import logging
import requests
from typing import Dict, Optional
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class OllamaExtractor:
    """Extract structured data using local Ollama LLM"""
    
    EXTRACTION_PROMPT = """Du bist ein Experte für die Extraktion von Impressum-Daten aus deutschen und schweizer Webseiten.

Extrahiere die folgenden Informationen aus dem Text. Antworte NUR mit einem JSON-Objekt, keine andere Erklärung:

{
    "company_name": "Firmenname mit Rechtsform",
    "legal_form": "Rechtsform (GmbH, AG, etc.)",
    "street": "Straße mit Hausnummer",
    "postal_code": "Postleitzahl",
    "city": "Stadt",
    "country": "Land",
    "ceo_names": "Geschäftsführer/Vorstand Namen",
    "email": "E-Mail Adresse",
    "phone": "Telefonnummer",
    "registration_number": "Handelsregister-Nummer (HRB/HRA)",
    "vat_id": "USt-IdNr"
}

Wenn eine Information nicht gefunden wird, setze null.

TEXT ZUM ANALYSIEREN:
{text}

JSON ANTWORT:"""

    def __init__(self, ollama_url: str = None, model: str = "llama3.2:3b"):
        self.ollama_url = ollama_url or os.getenv('OLLAMA_URL', 'http://localhost:11434')
        self.model = model
        self.available = self._check_availability()
        
        if self.available:
            logger.info(f"Ollama available at {self.ollama_url} with model {self.model}")
        else:
            logger.warning("Ollama not available - LLM extraction disabled")
    
    def _check_availability(self) -> bool:
        """Check if Ollama is running and model is available"""
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get('models', [])
                model_names = [m.get('name', '') for m in models]
                
                # Check if our model is available
                if any(self.model in name for name in model_names):
                    return True
                
                # Try to pull the model
                logger.info(f"Pulling model {self.model}...")
                pull_response = requests.post(
                    f"{self.ollama_url}/api/pull",
                    json={"name": self.model},
                    timeout=300
                )
                return pull_response.status_code == 200
            return False
        except Exception as e:
            logger.debug(f"Ollama check failed: {e}")
            return False
    
    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=10))
    def extract(self, text: str, max_tokens: int = 1000) -> Optional[Dict]:
        """Extract structured data from text using LLM"""
        if not self.available:
            return None
        
        # Truncate text to avoid token limits
        text = text[:8000]
        
        prompt = self.EXTRACTION_PROMPT.format(text=text)
        
        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": max_tokens,
                    }
                },
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                generated_text = result.get('response', '')
                
                # Parse JSON from response
                return self._parse_json_response(generated_text)
            else:
                logger.warning(f"Ollama request failed: {response.status_code}")
                return None
                
        except Exception as e:
            logger.warning(f"LLM extraction failed: {e}")
            return None
    
    def _parse_json_response(self, text: str) -> Optional[Dict]:
        """Parse JSON from LLM response"""
        try:
            # Try to find JSON in the response
            text = text.strip()
            
            # Find JSON block
            start = text.find('{')
            end = text.rfind('}') + 1
            
            if start >= 0 and end > start:
                json_str = text[start:end]
                data = json.loads(json_str)
                
                # Validate and clean
                cleaned = {}
                for key in ['company_name', 'legal_form', 'street', 'postal_code', 
                           'city', 'country', 'ceo_names', 'email', 'phone',
                           'registration_number', 'vat_id']:
                    value = data.get(key)
                    if value and value != 'null' and str(value).lower() != 'none':
                        cleaned[key] = str(value).strip()
                
                return cleaned if cleaned else None
            
            return None
            
        except json.JSONDecodeError as e:
            logger.debug(f"JSON parse error: {e}")
            return None
    
    def enhance_extraction(self, text: str, existing: Dict) -> Dict:
        """Enhance existing extraction with LLM for missing fields"""
        if not self.available:
            return existing
        
        # Check what's missing
        required_fields = ['company_name', 'street', 'postal_code', 'city']
        missing = [f for f in required_fields if not existing.get(f)]
        
        if not missing:
            return existing  # All required fields present
        
        logger.info(f"Using LLM to extract missing fields: {missing}")
        
        llm_result = self.extract(text)
        if not llm_result:
            return existing
        
        # Merge - only fill in missing fields
        for field in missing:
            if llm_result.get(field):
                existing[field] = llm_result[field]
                logger.debug(f"LLM filled missing {field}: {llm_result[field]}")
        
        return existing


# Singleton instance
_llm_extractor = None

def get_llm_extractor() -> OllamaExtractor:
    global _llm_extractor
    if _llm_extractor is None:
        _llm_extractor = OllamaExtractor()
    return _llm_extractor
