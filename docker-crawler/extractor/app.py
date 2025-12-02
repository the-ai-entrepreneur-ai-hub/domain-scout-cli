"""
German NER Extraction Service
Provides REST API for extracting entities from German legal text using spaCy
"""
import os
import re
import spacy
from flask import Flask, request, jsonify

app = Flask(__name__)

# Load German NER model
print("Loading German spaCy model...")
nlp = spacy.load("de_core_news_lg")
print("Model loaded successfully!")


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "model": "de_core_news_lg"})


@app.route('/extract', methods=['POST'])
def extract():
    """
    Extract entities from German legal text
    
    Request body:
    {
        "text": "Company text here..."
    }
    
    Response:
    {
        "organizations": ["Company GmbH"],
        "persons": ["Max Mustermann"],
        "locations": ["Berlin"],
        "addresses": [{"street": "...", "postal": "...", "city": "..."}]
    }
    """
    data = request.get_json()
    text = data.get('text', '')
    
    if not text:
        return jsonify({"error": "No text provided"}), 400
    
    # Process with spaCy
    doc = nlp(text[:50000])  # Limit text length
    
    result = {
        "organizations": [],
        "persons": [],
        "locations": [],
        "misc": [],
    }
    
    for ent in doc.ents:
        if ent.label_ == "ORG":
            result["organizations"].append(ent.text)
        elif ent.label_ == "PER":
            result["persons"].append(ent.text)
        elif ent.label_ in ("LOC", "GPE"):
            result["locations"].append(ent.text)
        elif ent.label_ == "MISC":
            result["misc"].append(ent.text)
    
    # Deduplicate
    result["organizations"] = list(set(result["organizations"]))[:10]
    result["persons"] = list(set(result["persons"]))[:10]
    result["locations"] = list(set(result["locations"]))[:10]
    
    # Extract addresses using regex
    result["addresses"] = extract_addresses(text)
    
    return jsonify(result)


def extract_addresses(text):
    """Extract structured addresses from text"""
    addresses = []
    
    # German address pattern
    pattern = r'([A-Za-zäöüÄÖÜß\-\.\s]+(?:str(?:aße|\.)?|straße|weg|platz|allee|ring|gasse))\s*(\d+\s*[a-zA-Z]?)\s*[,\n\s]+(\d{4,5})\s+([A-Za-zäöüÄÖÜß\s\-\.]+)'
    
    matches = re.findall(pattern, text, re.IGNORECASE)
    for match in matches[:5]:
        addresses.append({
            "street": f"{match[0].strip()} {match[1].strip()}",
            "postal_code": match[2],
            "city": match[3].strip()[:50]
        })
    
    return addresses


@app.route('/batch', methods=['POST'])
def batch_extract():
    """Batch extraction for multiple texts"""
    data = request.get_json()
    texts = data.get('texts', [])
    
    results = []
    for text in texts[:100]:  # Limit batch size
        doc = nlp(text[:50000])
        entities = {
            "organizations": list(set(e.text for e in doc.ents if e.label_ == "ORG"))[:5],
            "persons": list(set(e.text for e in doc.ents if e.label_ == "PER"))[:5],
            "locations": list(set(e.text for e in doc.ents if e.label_ in ("LOC", "GPE")))[:5],
        }
        results.append(entities)
    
    return jsonify({"results": results})


if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
