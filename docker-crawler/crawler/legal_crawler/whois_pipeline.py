import whois
import logging
from datetime import datetime

class WhoisPipeline:
    """Pipeline to enrich items with Whois data"""
    
    # Cache to avoid duplicate lookups
    _cache = {}
    
    def process_item(self, item, spider):
        domain = item.get('domain')
        if not domain:
            return item
        
        # Check cache first
        if domain in self._cache:
            cached = self._cache[domain]
            item['whois_registrar'] = cached.get('registrar')
            item['whois_creation_date'] = cached.get('creation_date')
            item['whois_expiration_date'] = cached.get('expiration_date')
            item['whois_owner'] = cached.get('owner')
            item['whois_emails'] = cached.get('emails')
            return item
            
        try:
            spider.logger.info(f"Fetching Whois for {domain}...")
            w = whois.whois(domain)
            
            # Extract relevant fields
            registrar = w.registrar or (w.name_servers[0] if w.name_servers else None)
            item['whois_registrar'] = registrar
            
            # Handle dates (can be list or single object)
            creation = None
            if w.creation_date:
                if isinstance(w.creation_date, list):
                    creation = w.creation_date[0].isoformat() if w.creation_date[0] else None
                else:
                    creation = w.creation_date.isoformat() if w.creation_date else None
            elif hasattr(w, 'updated_date') and w.updated_date:
                # Fallback to updated_date if no creation
                if isinstance(w.updated_date, list):
                    creation = w.updated_date[0] if isinstance(w.updated_date[0], str) else w.updated_date[0].isoformat()
                else:
                    creation = w.updated_date if isinstance(w.updated_date, str) else w.updated_date.isoformat()
            item['whois_creation_date'] = creation
            
            expiration = None
            if w.expiration_date:
                if isinstance(w.expiration_date, list):
                    expiration = w.expiration_date[0].isoformat() if w.expiration_date[0] else None
                else:
                    expiration = w.expiration_date.isoformat() if w.expiration_date else None
            item['whois_expiration_date'] = expiration
                
            item['whois_owner'] = w.org or w.name or None
            item['whois_emails'] = ', '.join(w.emails) if isinstance(w.emails, list) else w.emails
            
            # Cache result
            self._cache[domain] = {
                'registrar': item['whois_registrar'],
                'creation_date': item['whois_creation_date'],
                'expiration_date': item['whois_expiration_date'],
                'owner': item['whois_owner'],
                'emails': item['whois_emails'],
            }
            
        except Exception as e:
            spider.logger.warning(f"Whois lookup failed for {domain}: {e}")
            self._cache[domain] = {}
            
        return item
