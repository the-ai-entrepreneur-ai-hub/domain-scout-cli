"""
Enhanced storage module for exporting enriched crawl data.
"""
import csv
import json
import aiosqlite
from pathlib import Path
from datetime import datetime
from .database import DB_PATH
from .utils import logger

async def get_latest_run_id():
    """Fetch the most recent run_id from the database."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT run_id FROM results_enhanced ORDER BY crawled_at DESC LIMIT 1") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

async def export_enhanced_to_csv(output_path: str = None, tld_filter: str = None, include_legal: bool = True, run_id: str = None):
    """Export enhanced results to CSV with all fields including legal information."""
    
    # Default to latest run if not specified
    # CHANGED: Default to ALL runs to match user expectation of "exporting what I see in stats"
    # User can still provide specific run_id if needed
    if run_id == 'latest':
        run_id = await get_latest_run_id()
        if run_id:
            logger.info(f"Exporting latest run: {run_id}")
    elif not run_id:
        logger.info("No run_id specified, exporting aggregated results from ALL runs")
    
    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_suffix = f"_{run_id[:8]}" if run_id else "_all"
        output_path = f"data/enhanced_results_{timestamp}{run_suffix}.csv"
        
    output_path = Path(output_path)
    output_path.parent.mkdir(exist_ok=True)
    
    async with aiosqlite.connect(DB_PATH) as db:
        # Build query - join with legal_entities if requested
        if include_legal:
            query = """
                SELECT 
                    r.*,
                    l.legal_name, l.legal_form, l.trading_name,
                    l.register_type, l.register_court, l.registration_number,
                    l.vat_id as legal_vat_id, l.tax_id, l.siret, l.siren,
                    l.ceo_name, l.directors, l.authorized_reps,
                    l.registered_street, l.registered_zip, l.registered_city,
                    l.registered_state, l.registered_country,
                    l.postal_street, l.postal_zip, l.postal_city,
                    l.postal_state, l.postal_country,
                    l.legal_email, l.legal_phone, l.fax_number,
                    l.dpo_name, l.dpo_email,
                    l.registrant_name, l.registrant_address, l.registrant_city, l.registrant_country,
                    l.legal_notice_url, l.extraction_confidence as legal_confidence
                FROM results_enhanced r
                LEFT JOIN legal_entities l ON r.domain = l.domain
                WHERE 1=1
            """
        else:
            query = "SELECT * FROM results_enhanced WHERE 1=1"
        
        params = []
        
        if run_id:
            query += " AND r.run_id = ?"
            params.append(run_id)
        
        if tld_filter:
            tld = tld_filter if tld_filter.startswith('.') else f'.{tld_filter}'
            if include_legal:
                query += " AND r.domain LIKE ?"
            else:
                query += " AND domain LIKE ?"
            params.append(f'%{tld}')
            
        if include_legal:
            query += " ORDER BY r.confidence_score DESC, r.crawled_at DESC"
        else:
            query += " ORDER BY confidence_score DESC, crawled_at DESC"
        
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            
    if not rows:
        logger.warning(f"No enhanced results found to export (Run ID: {run_id})")
        return
        
    # Write to CSV with JSON field unpacking
    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        
        for row in rows:
            row_dict = dict(zip(columns, row))
            
            # Gap Fix #6: Unpack JSON fields to human-readable strings
            for json_field in ['directors', 'authorized_reps']:
                if json_field in row_dict and row_dict[json_field]:
                    try:
                        parsed = json.loads(row_dict[json_field])
                        if isinstance(parsed, list):
                            row_dict[json_field] = '; '.join(str(x) for x in parsed if x)
                    except (json.JSONDecodeError, TypeError):
                        pass  # Keep original value if not valid JSON
            
            writer.writerow(row_dict)
            
    logger.info(f"Exported {len(rows)} enhanced results to {output_path}")
    
async def export_enhanced_to_json(output_path: str = None, tld_filter: str = None, run_id: str = None):
    """Export enhanced results to JSON format."""
    
    if run_id == 'latest':
        run_id = await get_latest_run_id()
    elif not run_id:
        # Default to ALL runs
        pass
        
    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_suffix = f"_{run_id[:8]}" if run_id else "_all"
        output_path = f"data/enhanced_results_{timestamp}{run_suffix}.json"
        
    output_path = Path(output_path)
    output_path.parent.mkdir(exist_ok=True)
    
    async with aiosqlite.connect(DB_PATH) as db:
        query = "SELECT * FROM results_enhanced WHERE 1=1"
        params = []
        
        if run_id:
            query += " AND run_id = ?"
            params.append(run_id)
        
        if tld_filter:
            tld = tld_filter if tld_filter.startswith('.') else f'.{tld_filter}'
            query += " AND domain LIKE ?"
            params.append(f'%{tld}')
            
        query += " ORDER BY confidence_score DESC, crawled_at DESC"
        
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            
    if not rows:
        logger.warning(f"No enhanced results found to export (Run ID: {run_id})")
        return
        
    # Convert to list of dicts
    results = []
    for row in rows:
        row_dict = dict(zip(columns, row))
        
        # Parse comma-separated fields back to lists
        if row_dict.get('emails'):
            row_dict['emails'] = row_dict['emails'].split(',')
        if row_dict.get('phones'):
            row_dict['phones'] = row_dict['phones'].split(',')
            
        # Parse JSON fields if stored as strings
        if row_dict.get('business_hours'):
            try:
                row_dict['business_hours'] = json.loads(row_dict['business_hours'])
            except:
                pass
                
        results.append(row_dict)
        
    # Write to JSON
    with open(output_path, 'w', encoding='utf-8-sig') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
        
    logger.info(f"Exported {len(results)} enhanced results to {output_path}")

async def get_statistics():
    """Get crawling statistics from the database."""
    async with aiosqlite.connect(DB_PATH) as db:
        stats = {}
        
        # Total domains in queue
        cursor = await db.execute("SELECT COUNT(*) FROM queue")
        stats['total_domains'] = (await cursor.fetchone())[0]
        
        # Status breakdown
        cursor = await db.execute("""
            SELECT status, COUNT(*) 
            FROM queue 
            GROUP BY status
        """)
        stats['status_breakdown'] = dict(await cursor.fetchall())
        
        # Enhanced results count
        cursor = await db.execute("SELECT COUNT(*) FROM results_enhanced")
        stats['enhanced_results'] = (await cursor.fetchone())[0]
        
        # Average confidence score
        cursor = await db.execute("""
            SELECT AVG(confidence_score) 
            FROM results_enhanced 
            WHERE confidence_score > 0
        """)
        avg_score = await cursor.fetchone()
        stats['avg_confidence'] = avg_score[0] if avg_score[0] else 0
        
        # High quality results (confidence > 70)
        cursor = await db.execute("""
            SELECT COUNT(*) 
            FROM results_enhanced 
            WHERE confidence_score > 70
        """)
        stats['high_quality_results'] = (await cursor.fetchone())[0]
        
        # Legal entities statistics
        cursor = await db.execute("SELECT COUNT(*) FROM legal_entities")
        stats['legal_entities'] = (await cursor.fetchone())[0]
        
        # Legal entities with registration numbers
        cursor = await db.execute("""
            SELECT COUNT(*) 
            FROM legal_entities 
            WHERE registration_number IS NOT NULL AND registration_number != ''
        """)
        stats['entities_with_registration'] = (await cursor.fetchone())[0]
        
        # Legal entities with VAT IDs
        cursor = await db.execute("""
            SELECT COUNT(*) 
            FROM legal_entities 
            WHERE vat_id IS NOT NULL AND vat_id != ''
        """)
        stats['entities_with_vat'] = (await cursor.fetchone())[0]
        
        # Fields coverage
        cursor = await db.execute("""
            SELECT 
                COUNT(CASE WHEN emails IS NOT NULL AND emails != '' THEN 1 END) as with_email,
                COUNT(CASE WHEN phones IS NOT NULL AND phones != '' THEN 1 END) as with_phone,
                COUNT(CASE WHEN address IS NOT NULL AND address != '' THEN 1 END) as with_address,
                COUNT(CASE WHEN industry IS NOT NULL AND industry != '' THEN 1 END) as with_industry,
                COUNT(CASE WHEN vat_id IS NOT NULL AND vat_id != '' THEN 1 END) as with_vat,
                COUNT(*) as total
            FROM results_enhanced
        """)
        coverage = await cursor.fetchone()
        if coverage and coverage[5] > 0:
            stats['field_coverage'] = {
                'email': f"{coverage[0]/coverage[5]*100:.1f}%",
                'phone': f"{coverage[1]/coverage[5]*100:.1f}%",
                'address': f"{coverage[2]/coverage[5]*100:.1f}%",
                'industry': f"{coverage[3]/coverage[5]*100:.1f}%",
                'vat_id': f"{coverage[4]/coverage[5]*100:.1f}%"
            }
            
        return stats

async def export_legal_entities_to_csv(output_path: str = None, tld_filter: str = None, run_id: str = None, full_metadata_only: bool = True):
    """
    Export legal entity information to CSV.
    """
    
    # Handle 'latest' keyword
    if run_id == 'latest':
        run_id = await get_latest_run_id()
        if run_id:
            logger.info(f"Exporting latest run (Legal): {run_id}")
    elif not run_id:
        logger.info("No run_id specified, exporting aggregated Legal entities from ALL runs")
    
    # Always use timestamp in filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Filename Enhancement: Include TLD and/or Run ID for context
    # Example: legal_entities_ch_20251127.csv or legal_entities_all_20251127_runid.csv
    filename_parts = ["legal_entities"]
    if tld_filter:
        filename_parts.append(tld_filter.replace('.', ''))
    else:
        filename_parts.append("all")
        
    filename_parts.append(timestamp)
    
    if run_id:
        filename_parts.append(run_id[:8])
        
    default_filename = "_".join(filename_parts) + ".csv"

    if not output_path:
        output_path = f"data/{default_filename}"
    else:
        # If path provided, ensure parent dir exists but maybe append timestamp if not present?
        # User might provide specific name "my_export.csv". Let's respect it but ensure directory.
        p = Path(output_path)
        # Check if user path already has timestamp-like pattern? 
        # Actually, let's just use what they gave if they gave it, or default if not.
        pass
        
    output_path = Path(output_path)
    output_path.parent.mkdir(exist_ok=True)
    
    async with aiosqlite.connect(DB_PATH) as db:
        # Query with structured address fields for completeness check
        query = """
            SELECT 
                domain, legal_name, legal_form, trading_name,
                register_type, register_court, registration_number,
                vat_id, tax_id, siret, siren,
                ceo_name, directors, authorized_reps,
                COALESCE(street_address, registered_street, '') as street_address,
                COALESCE(postal_code, registered_zip, '') as postal_code,
                COALESCE(city, registered_city, '') as city,
                COALESCE(country, registered_country, '') as country,
                COALESCE(phone, legal_phone, '') as phone,
                COALESCE(email, legal_email, '') as email,
                fax_number as fax,
                dpo_name, dpo_email,
                legal_notice_url, extraction_confidence, last_updated
            FROM legal_entities
            WHERE 1=1
        """
        
        params = []
        
        # STRICT REQUIREMENT: Only export entries with FULL metadata
        if full_metadata_only:
            query += """
                AND legal_name IS NOT NULL AND legal_name != ''
                AND (
                    (street_address != '' AND city != '') 
                    OR (registered_street != '' AND registered_city != '')
                )
                AND (
                    email != '' OR phone != '' OR legal_email != '' OR legal_phone != ''
                )
            """
        
        if run_id:
            query += " AND run_id = ?"
            params.append(run_id)
            
        if tld_filter:
            tld = tld_filter if tld_filter.startswith('.') else f'.{tld_filter}'
            query += " AND domain LIKE ?"
            params.append(f'%{tld}')
            
        query += " ORDER BY extraction_confidence DESC, last_updated DESC"
        
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            
    if not rows:
        logger.warning(f"No legal entities with full metadata found to export (Run ID: {run_id or 'ANY'})")
        if not full_metadata_only:
             logger.info("Tip: Try running crawl again or checking logs for failures.")
        else:
             logger.info("Tip: Use --include-incomplete to see partial results.")
        return output_path
        
    # Write to CSV with JSON field unpacking and UTF-8 BOM for Windows Excel compatibility
    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        
        for row in rows:
            row_dict = dict(zip(columns, row))
            
            # Unpack JSON fields to human-readable strings
            for json_field in ['directors', 'authorized_reps']:
                if json_field in row_dict and row_dict[json_field]:
                    try:
                        parsed = json.loads(row_dict[json_field])
                        if isinstance(parsed, list):
                            row_dict[json_field] = '; '.join(str(x) for x in parsed if x)
                    except (json.JSONDecodeError, TypeError):
                        pass
            
            writer.writerow(row_dict)
            
    logger.info(f"Exported {len(rows)} legal entities with full metadata to {output_path}")
    return output_path


# New v4.0 export function with structured address fields
ROBUST_LEGAL_CSV_COLUMNS = [
    # Identification
    'domain',
    'legal_name',
    'registrant_name', # WHOIS Name
    'legal_form',
    
    # Structured Address (v4.0)
    'street_address',
    'postal_code',
    'city',
    'country',
    
    # Registrant Address (WHOIS)
    'registrant_address',
    'registrant_city',
    'registrant_country',
    
    # Registration
    'register_type',
    'register_court',
    'registration_number',
    'vat_id',
    
    # Representatives
    'ceo_name',
    'directors',
    
    # Contact
    'phone',
    'email',
    'fax',
    
    # Metadata
    'legal_notice_url',
    'extraction_confidence',
    'extraction_date',
]


async def export_robust_legal_to_csv(output_path: str = None, tld_filter: str = None):
    """
    Export legal entities with v4.0 robust extraction schema.
    Uses structured address fields (street, zip, city, country).
    """
    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"data/robust_legal_{timestamp}.csv"
        
    output_path = Path(output_path)
    output_path.parent.mkdir(exist_ok=True)
    
    async with aiosqlite.connect(DB_PATH) as db:
        # Build query with v4.0 structured fields
        query = """
            SELECT 
                domain,
                legal_name,
                registrant_name,
                legal_form,
                COALESCE(street_address, registered_street, '') as street_address,
                COALESCE(postal_code, registered_zip, '') as postal_code,
                COALESCE(city, registered_city, '') as city,
                COALESCE(country, registered_country, '') as country,
                registrant_address,
                registrant_city,
                registrant_country,
                register_type,
                register_court,
                registration_number,
                vat_id,
                ceo_name,
                directors,
                COALESCE(phone, legal_phone, '') as phone,
                COALESCE(email, legal_email, '') as email,
                COALESCE(fax, fax_number, '') as fax,
                legal_notice_url,
                extraction_confidence,
                extraction_date
            FROM legal_entities
            WHERE legal_name IS NOT NULL AND legal_name != ''
        """
        
        params = []
        if tld_filter:
            tld = tld_filter if tld_filter.startswith('.') else f'.{tld_filter}'
            query += " AND domain LIKE ?"
            params.append(f'%{tld}')
            
        query += " ORDER BY extraction_confidence DESC, last_updated DESC"
        
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            
    if not rows:
        logger.warning("No legal entities found to export")
        return output_path
        
    # Write to CSV with robust schema
    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=ROBUST_LEGAL_CSV_COLUMNS)
        writer.writeheader()
        
        for row in rows:
            row_dict = dict(zip(ROBUST_LEGAL_CSV_COLUMNS, row))
            writer.writerow(row_dict)
            
    logger.info(f"Exported {len(rows)} legal entities (robust schema) to {output_path}")
    return output_path


async def save_robust_legal_entity(data: dict):
    """
    Save a legal entity with v4.0 robust extraction schema.
    Uses UPSERT to update existing records.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO legal_entities (
                domain, legal_name, legal_form,
                street_address, postal_code, city, country,
                register_type, register_court, registration_number,
                vat_id, siret, siren,
                ceo_name, directors,
                phone, email, fax,
                legal_notice_url, extraction_confidence, extraction_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(domain) DO UPDATE SET
                legal_name = excluded.legal_name,
                legal_form = excluded.legal_form,
                street_address = excluded.street_address,
                postal_code = excluded.postal_code,
                city = excluded.city,
                country = excluded.country,
                register_type = excluded.register_type,
                register_court = excluded.register_court,
                registration_number = excluded.registration_number,
                vat_id = excluded.vat_id,
                siret = excluded.siret,
                siren = excluded.siren,
                ceo_name = excluded.ceo_name,
                directors = excluded.directors,
                phone = excluded.phone,
                email = excluded.email,
                fax = excluded.fax,
                legal_notice_url = excluded.legal_notice_url,
                extraction_confidence = excluded.extraction_confidence,
                extraction_date = excluded.extraction_date,
                last_updated = CURRENT_TIMESTAMP
        """, (
            data.get('domain'),
            data.get('legal_name'),
            data.get('legal_form'),
            data.get('street_address'),
            data.get('postal_code'),
            data.get('city'),
            data.get('country'),
            data.get('register_type'),
            data.get('register_court'),
            data.get('registration_number'),
            data.get('vat_id'),
            data.get('siret'),
            data.get('siren'),
            data.get('ceo_name'),
            data.get('directors'),
            data.get('phone'),
            data.get('email'),
            data.get('fax'),
            data.get('legal_notice_url'),
            data.get('extraction_confidence'),
            data.get('extraction_date'),
        ))
        await db.commit()

async def print_statistics():
    """Print crawling statistics."""
    stats = await get_statistics()
    
    print("\n" + "="*50)
    print("CRAWLER STATISTICS")
    print("="*50)
    print(f"Total domains: {stats.get('total_domains', 0)}")
    print(f"Enhanced results: {stats.get('enhanced_results', 0)}")
    print(f"Average confidence: {stats.get('avg_confidence', 0):.1f}%")
    print(f"High quality results: {stats.get('high_quality_results', 0)}")
    
    print("\nLegal Entity Information:")
    print(f"  Legal entities found: {stats.get('legal_entities', 0)}")
    print(f"  With registration numbers: {stats.get('entities_with_registration', 0)}")
    print(f"  With VAT IDs: {stats.get('entities_with_vat', 0)}")
    
    print("\nStatus Breakdown:")
    for status, count in stats.get('status_breakdown', {}).items():
        print(f"  {status}: {count}")
        
    if stats.get('field_coverage'):
        print("\nField Coverage:")
        for field, coverage in stats['field_coverage'].items():
            print(f"  {field}: {coverage}")
            
    print("="*50)

# Known enterprise domains (root domain names)
ENTERPRISE_DOMAINS = {
    'google', 'facebook', 'amazon', 'microsoft', 'apple', 'netflix', 'twitter',
    'linkedin', 'instagram', 'youtube', 'ebay', 'alibaba', 'tencent', 'baidu',
    'yahoo', 'bing', 'adobe', 'oracle', 'ibm', 'sap', 'salesforce', 'cisco',
    'intel', 'nvidia', 'amd', 'samsung', 'sony', 'huawei', 'dell', 'hp',
    'siemens', 'bosch', 'volkswagen', 'bmw', 'daimler', 'mercedes', 'allianz',
    'basf', 'bayer', 'henkel', 'lufthansa', 'telekom', 'vodafone', 'telefonica',
    'spotify', 'airbnb', 'booking', 'uber', 'lyft', 'paypal', 'stripe', 'visa',
    'mastercard', 'zoom', 'slack', 'atlassian', 'zendesk', 'hubspot', 'shopify',
    'cloudflare', 'digitalocean', 'heroku', 'github', 'gitlab', 'bitbucket',
    'stackoverflow', 'wikipedia', 'reddit', 'quora', 'medium', 'wordpress',
    'zalando', 'otto', 'focus', 'spiegel', 'bild', 'welt', 'zeit', 'faz',
    'tagesschau', 'zdf', 'ard', 'rtl', 'prosieben', 'commerzbank', 'deutschebank',
}

def is_enterprise_domain(domain: str) -> bool:
    """Check if domain belongs to a known enterprise."""
    if not domain:
        return False
    
    domain_lower = domain.lower()
    
    # Extract root domain (e.g., "google" from "google.de")
    parts = domain_lower.split('.')
    if len(parts) >= 2:
        root = parts[-2]  # Second to last part (before TLD)
        if root in ENTERPRISE_DOMAINS:
            return True
    
    # Also check if any enterprise name is contained
    for enterprise in ENTERPRISE_DOMAINS:
        if enterprise in domain_lower:
            return True
    
    return False

# Government domain indicators
GOV_INDICATORS = [
    '.gov', '.gv.', 'bundesamt', 'ministerium', 'verwaltung', 
    'stadt.', 'gemeinde', 'landratsamt', 'bezirksamt', 'rathaus',
    'bundesregierung', 'landesregierung', 'government', 'municipality',
    'bundesanstalt', 'bundesbehörde', 'behörde'
]

def classify_company_size(legal_form: str, employee_count: int = 0, domain: str = None) -> str:
    """
    Heuristic classification of company size based on legal form, domain, and data.
    Returns: solo, sme, enterprise, government, or unknown
    """
    domain_lower = (domain or "").lower()
    
    # 1. Check for government/public sector
    if any(g in domain_lower for g in GOV_INDICATORS):
        return "government"
    
    # 2. Check if domain is known enterprise
    if domain and is_enterprise_domain(domain):
        return "enterprise"
    
    # 3. Check employee count
    if employee_count > 250:
        return "enterprise"
    if employee_count > 10:
        return "sme"
        
    form = (legal_form or "").lower()
    
    # 4. Government legal forms
    if any(x in form for x in ['körperschaft', 'anstalt des öffentlichen rechts', 'aör', 'k.d.ö.r.']):
        return "government"
    
    # 5. Enterprise indicators from legal form
    if any(x in form for x in ['ag', 'se', 'kgaa', 'aktiengesellschaft', 'plc', 'corporation', 'corp']):
        return "enterprise"
        
    # 6. SME indicators (GmbH is standard, could be large but default to SME)
    if any(x in form for x in ['gmbh', 'co. kg', 'limited', 'ltd', 'sarl', 's.a.', 's.r.l', 'llc']):
        return "sme"
        
    # 7. Solo/Micro indicators
    if any(x in form for x in ['ug', 'gbr', 'e.k.', 'einzelunternehmen', 'freiberufler', 'selbstständig', 'sole']):
        return "solo"
        
    # 8. Default fallback
    return "unknown"

def validate_ceo_name(name: str) -> str:
    """Validate CEO/director name - must be real person name."""
    if not name:
        return ""
    
    name = name.strip()
    name_lower = name.lower()
    
    # Garbage names and patterns to reject
    INVALID_NAMES = {
        'wir', 'uns', 'sie', 'ihr', 'du', 'we', 'you', 'they', 'us', 'i',
        'nginx', 'apache', 'wordpress', 'cloudflare', 'google', 'microsoft',
        'server', 'hosting', 'domain', 'admin', 'webmaster', 'root', 'user',
        'kontakt', 'contact', 'impressum', 'legal', 'info', 'support',
        'kunden', 'customer', 'service', 'team', 'staff', 'management',
        'geschäftsführer', 'director', 'manager', 'ceo', 'inhaber',
        'natürliche personen', 'juristische person', 'person des anbieters',
        'vertretungsberechtigter', 'verantwortlicher', 'betreiber',
        'redaktion', 'herausgeber', 'autor', 'editor', 'publisher',
        'firma', 'company', 'organisation', 'organization',
    }
    
    if name_lower in INVALID_NAMES:
        return ""
    
    # Reject if contains these patterns (not exact match)
    GARBAGE_PATTERNS = [
        'natürliche person', 'juristische person', 'person des',
        'vertretungsberechtigt', 'verantwortlich', 'im sinne',
        'gemäß', 'nach § ', 'i.s.d.', 'gemass', 'gemaess',
        'nicht verfügbar', 'n/a', 'none', 'unknown', 'unbekannt',
        'betroffene person', 'betroffenen', 'der gesellschaft',
        'die gesellschaft', 'in allen', 'gerichtlichen', 'außergerichtlichen',
        'angelegenheiten', 'handelsregister', 'amtsgericht',
    ]
    if any(p in name_lower for p in GARBAGE_PATTERNS):
        return ""
    
    # Must have at least 2 words (first + last name) or be a title+name
    words = name.split()
    if len(words) < 2:
        return ""
    
    # Reject if too short or too long
    if len(name) < 5 or len(name) > 80:
        return ""
    
    return name

def validate_street(street: str) -> str:
    """Validate street - must be street + house number only."""
    if not street:
        return ""
    
    street = street.strip()
    
    # Reject if just a country code
    if len(street) <= 3 and street.upper() in {'DE', 'AT', 'CH', 'US', 'UK', 'FR', 'NL', 'BE', 'IT'}:
        return ""
    
    # Reject multi-line content
    if '\n' in street or '\r' in street:
        return ""
    
    # Reject if too short (just country code or garbage)
    if len(street) < 5:
        return ""
    
    # Reject if too long (likely garbage)
    if len(street) > 80:
        return ""
    
    # Reject if contains garbage patterns
    garbage = ['http', '@', 'gmbh', 'ag', 'tel', 'fax', 'email', 'kontakt', 'geschäftsführer',
               'server at', 'port ', 'www.', 'cookie', 'javascript', 'datenschutz']
    if any(g in street.lower() for g in garbage):
        return ""
    
    # If street contains multiple commas (full address mixed in), try to extract just street
    if street.count(',') >= 2:
        # Likely format: "Street 123, 12345, City, Country"
        parts = street.split(',')
        if parts[0].strip():
            street = parts[0].strip()
    
    return street

def validate_postal_code(code: str) -> str:
    """Validate postal code - supports international formats (DE, CH, AT, FR, NL, UK, etc.)."""
    if not code:
        return ""
    
    code = code.strip()
    import re
    
    # German/French/Italian: 5 digits
    if re.match(r'^\d{5}$', code):
        return code
    
    # Swiss/Austrian/Belgian: 4 digits (with optional country prefix)
    if re.match(r'^(?:CH-?|A-?|B-?)?\d{4}$', code.upper()):
        return code
    
    # Dutch: 4 digits + 2 letters (e.g., "1012 LG")
    if re.match(r'^\d{4}\s*[A-Z]{2}$', code.upper()):
        return code.upper()
    
    # UK: Various alphanumeric formats (e.g., "SW1A 2AA")
    if re.match(r'^[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}$', code.upper()):
        return code.upper()
    
    return ""

def validate_city(city: str) -> str:
    """Validate city - must be letters only, 2-40 chars."""
    if not city:
        return ""
    
    city = city.strip()
    
    # Reject if too long or short
    if len(city) < 2 or len(city) > 40:
        return ""
    
    # Reject if contains garbage
    garbage = ['tel', 'fax', 'http', 'email', 'phone', 'gmbh', '@', 'www']
    if any(g in city.lower() for g in garbage):
        return ""
    
    # Should be mostly letters
    import re
    letter_count = len(re.findall(r'[a-zA-ZäöüÄÖÜß]', city))
    if letter_count < len(city) * 0.7:
        return ""
    
    return city

async def export_unified(output_path: str = None, tld_filter: str = None, run_id: str = None, complete_only: bool = False):
    """
    Export Unified Results (Client Spec Compliance).
    A single "Golden Record" CSV with EXACTLY 23 columns.
    
    Args:
        complete_only: If True, only export entries with company_name AND at least one address field
    """
    # Handle 'latest' keyword
    if run_id == 'latest':
        run_id = await get_latest_run_id()
    
    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"data/unified_results_{timestamp}.csv"
        
    output_path = Path(output_path)
    output_path.parent.mkdir(exist_ok=True)
    
    async with aiosqlite.connect(DB_PATH) as db:
        # Join results_enhanced, legal_entities, and queue (for robots status)
        # FIXED: Now correctly fetching robots_status and robots_reason from queue table
        query = """
            SELECT 
                r.domain, r.crawled_at, r.run_id,
                l.legal_name, r.company_name as web_company_name,
                l.legal_form,
                l.registration_number,
                l.ceo_name, l.directors,
                r.industry,
                r.emails, r.phones,
                COALESCE(l.fax, l.fax_number, '') as fax_number,
                COALESCE(l.street_address, l.registered_street, '') as street,
                COALESCE(l.postal_code, l.registered_zip, '') as postal_code,
                COALESCE(l.city, l.registered_city, '') as city,
                COALESCE(l.country, l.registered_country, '') as country,
                r.description as service_product_description,
                r.social_linkedin, r.social_twitter, r.social_facebook, r.social_instagram, r.social_youtube,
                q.robots_status,
                q.robots_reason
            FROM results_enhanced r
            LEFT JOIN legal_entities l ON r.domain = l.domain
            LEFT JOIN queue q ON r.domain = q.domain
            WHERE 1=1
        """
        
        params = []
        if run_id:
            query += " AND r.run_id = ?"
            params.append(run_id)
            
        if tld_filter:
            tld = tld_filter if tld_filter.startswith('.') else f'.{tld_filter}'
            query += " AND r.domain LIKE ?"
            params.append(f'%{tld}')
            
        query += " ORDER BY r.confidence_score DESC"
        
        try:
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
        except Exception as e:
            logger.error(f"Unified export query failed: {e}")
            return None
            
    if not rows:
        logger.warning("No results found for unified export.")
        return None

    # Client Spec Columns - EXACTLY 23 columns in specified order
    columns = [
        # REGISTRY (7)
        'company_name', 'legal_form', 'registration_number', 'ceo_names', 
        'owner_organization', 'industry', 'company_size',
        # CONTACT (3)
        'emails', 'phone_numbers', 'fax_numbers',
        # LOCATION (4)
        'street', 'postal_code', 'city', 'country',
        # PRODUCT (1)
        'service_product_description',
        # SOCIAL (1)
        'social_links',
        # META (2)
        'website_created_at', 'website_last_updated_at',
        # TECH (3)
        'domain', 'crawled_at', 'run_id',
        # PERMS (2)
        'robots_allowed', 'robots_reason'
    ]
    
    exported_count = 0
    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        
        for row in rows:
            # Unpack row tuple (index based on query order)
            (domain, crawled_at, run_id_val,
             legal_name, web_company_name,
             legal_form, reg_num,
             ceo_name, directors,
             industry,
             emails, phones, fax,
             street, postal_code, city, country,
             desc,
             li, tw, fb, ig, yt,
             robots_status, robots_reason) = row
            
            # Validate and clean company name
            final_name = legal_name if legal_name else web_company_name
            if final_name:
                final_name = final_name.strip()[:100]  # Max 100 chars
            
            # Validate CEO names - filter garbage
            ceos = []
            validated_ceo = validate_ceo_name(ceo_name or "")
            if validated_ceo:
                ceos.append(validated_ceo)
            if directors:
                try:
                    dirs = json.loads(directors)
                    if isinstance(dirs, list):
                        for d in dirs:
                            validated_dir = validate_ceo_name(d)
                            if validated_dir:
                                ceos.append(validated_dir)
                except: 
                    pass
            final_ceos = "; ".join(list(set(ceos)))
            
            # Build social links JSON
            socials = {}
            if li: socials['linkedin'] = li
            if fb: socials['facebook'] = fb
            if ig: socials['instagram'] = ig
            if tw: socials['twitter'] = tw
            if yt: socials['youtube'] = yt
            social_str = json.dumps(socials) if socials else ""
            
            # Classify company size (includes government)
            size = classify_company_size(legal_form, domain=domain)
            
            # Format contact fields
            email_str = emails.replace(',', '; ') if emails else ""
            phone_str = phones.replace(',', '; ') if phones else ""
            
            # Validate location fields
            clean_street = validate_street(street or "")
            clean_postal = validate_postal_code(postal_code or "")
            clean_city = validate_city(city or "")
            
            # Map robots_status to true/false
            robots_allowed_bool = "true" if robots_status == "ALLOWED" else "false"
            robots_reason_str = robots_reason or ("allowed" if robots_status == "ALLOWED" else "unknown")
            
            # Skip incomplete records if complete_only is set
            if complete_only:
                has_company = bool(final_name and len(final_name) > 2)
                has_address = bool(clean_street or clean_postal or clean_city)
                if not (has_company and has_address):
                    continue
            
            record = {
                'company_name': final_name or "",
                'legal_form': (legal_form or "").strip(),
                'registration_number': (reg_num or "").strip(),
                'ceo_names': final_ceos,
                'owner_organization': "",  # Not reliably extracted
                'industry': (industry or "").strip(),
                'company_size': size,
                'emails': email_str,
                'phone_numbers': phone_str,
                'fax_numbers': (fax or "").strip(),
                'street': clean_street,
                'postal_code': clean_postal,
                'city': clean_city,
                'country': (country or "").strip(),
                'service_product_description': (desc or "")[:500],
                'social_links': social_str,
                'website_created_at': "",  # Future: from WHOIS
                'website_last_updated_at': "",  # Future: from HTTP headers
                'domain': domain,
                'crawled_at': crawled_at,
                'run_id': run_id_val,
                'robots_allowed': robots_allowed_bool,
                'robots_reason': robots_reason_str
            }
            
            writer.writerow(record)
            exported_count += 1
            
    if complete_only:
        logger.info(f"Exported {exported_count} complete records (of {len(rows)} total) to {output_path}")
    else:
        logger.info(f"Exported {exported_count} unified results to {output_path}")
    return output_path


# CLIENT SPEC: Export ONLY the 6 required fields
CLIENT_SPEC_COLUMNS = [
    'domain',
    # 1. Company/Person Name
    'company_name',
    # 2. Legal Form
    'legal_form',
    # 3. Full Address
    'street', 'postal_code', 'city', 'country',
    # 4. Authorized Representatives
    'ceo_name', 'directors',
    # 5. Contact Information
    'email', 'phone',
    # 6. Register Details
    'register_type', 'register_court', 'registration_number',
]


async def export_client_spec(output_path: str = None, tld_filter: str = None, run_id: str = None):
    """
    Export ONLY the 6 required fields per client spec.
    
    Fields:
    1. Company or responsible person's name
    2. Legal form of the entity
    3. Full postal address (street, ZIP code, city, country)
    4. Authorized representatives
    5. Contact information (email and phone number)
    6. Register details (type of register, register court, and registration number)
    """
    if run_id == 'latest':
        run_id = await get_latest_run_id()
    
    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"data/client_spec_{timestamp}.csv"
        
    output_path = Path(output_path)
    output_path.parent.mkdir(exist_ok=True)
    
    async with aiosqlite.connect(DB_PATH) as db:
        query = """
            SELECT 
                l.domain,
                COALESCE(l.legal_name, r.company_name, '') as company_name,
                l.legal_form,
                COALESCE(l.street_address, l.registered_street, '') as street,
                COALESCE(l.postal_code, l.registered_zip, '') as postal_code,
                COALESCE(l.city, l.registered_city, '') as city,
                COALESCE(l.country, l.registered_country, 'Germany') as country,
                l.ceo_name,
                l.directors,
                COALESCE(l.email, l.legal_email, '') as email,
                COALESCE(l.phone, l.legal_phone, '') as phone,
                l.register_type,
                l.register_court,
                l.registration_number
            FROM legal_entities l
            LEFT JOIN results_enhanced r ON l.domain = r.domain
            WHERE 1=1
        """
        
        params = []
        if run_id:
            query += " AND l.run_id = ?"
            params.append(run_id)
            
        if tld_filter:
            tld = tld_filter if tld_filter.startswith('.') else f'.{tld_filter}'
            query += " AND l.domain LIKE ?"
            params.append(f'%{tld}')
            
        query += " ORDER BY l.extraction_confidence DESC"
        
        try:
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
        except Exception as e:
            logger.error(f"Client spec export query failed: {e}")
            return None
            
    if not rows:
        logger.warning("No legal entities found for client spec export.")
        return None

    exported_count = 0
    complete_count = 0
    
    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=CLIENT_SPEC_COLUMNS)
        writer.writeheader()
        
        for row in rows:
            (domain, company_name, legal_form, street, postal_code, city, country,
             ceo_name, directors, email, phone, reg_type, reg_court, reg_num) = row
            
            # Parse directors JSON if present
            directors_str = ""
            if directors:
                try:
                    dirs = json.loads(directors)
                    if isinstance(dirs, list):
                        directors_str = "; ".join(str(d) for d in dirs if d)
                except:
                    directors_str = str(directors)
            
            record = {
                'domain': domain,
                'company_name': (company_name or "").strip(),
                'legal_form': (legal_form or "").strip(),
                'street': (street or "").strip(),
                'postal_code': (postal_code or "").strip(),
                'city': (city or "").strip(),
                'country': (country or "").strip(),
                'ceo_name': (ceo_name or "").strip(),
                'directors': directors_str,
                'email': (email or "").strip(),
                'phone': (phone or "").strip(),
                'register_type': (reg_type or "").strip(),
                'register_court': (reg_court or "").strip(),
                'registration_number': (reg_num or "").strip(),
            }
            
            writer.writerow(record)
            exported_count += 1
            
            # Count complete records (all 6 fields filled)
            has_name = bool(record['company_name'])
            has_form = bool(record['legal_form'])
            has_addr = bool(record['street'] and record['postal_code'] and record['city'])
            has_rep = bool(record['ceo_name'] or record['directors'])
            has_contact = bool(record['email'] or record['phone'])
            has_register = bool(record['registration_number'])
            
            if has_name and has_form and has_addr and has_rep and has_contact and has_register:
                complete_count += 1
            
    logger.info(f"Client Spec Export: {exported_count} records ({complete_count} complete) to {output_path}")
    logger.info(f"Completion rate: {complete_count}/{exported_count} ({complete_count/exported_count*100:.1f}%)" if exported_count > 0 else "No records")
    return output_path
