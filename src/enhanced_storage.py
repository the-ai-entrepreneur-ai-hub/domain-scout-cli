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
    if not run_id:
        run_id = await get_latest_run_id()
        if run_id:
            logger.info(f"No run_id specified, defaulting to latest run: {run_id}")
    
    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_suffix = f"_{run_id[:8]}" if run_id else ""
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
    
    if not run_id:
        run_id = await get_latest_run_id()
        
    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_suffix = f"_{run_id[:8]}" if run_id else ""
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
    
    By default (full_metadata_only=True), only exports entries with COMPLETE metadata:
    1) Company name (legal_name)
    2) Legal form
    3) Full postal address (street, ZIP, city, country)
    4) Authorized representatives (CEO/directors)
    5) Contact info (email AND phone)
    6) Register details (type, court, number)
    """
    
    # NOTE: Don't default to latest run - export ALL data if no run specified
    # This allows exporting accumulated data across multiple runs
    
    # Always use timestamp in filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if not output_path:
        run_suffix = f"_{run_id[:8]}" if run_id else ""
        output_path = f"data/legal_entities_{timestamp}{run_suffix}.csv"
    else:
        # Add timestamp to user-provided path
        p = Path(output_path)
        output_path = str(p.parent / f"{p.stem}_{timestamp}{p.suffix}")
        
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
                AND legal_form IS NOT NULL AND legal_form != ''
                AND (street_address != '' OR registered_street != '')
                AND (postal_code != '' OR registered_zip != '')
                AND (city != '' OR registered_city != '')
                AND (country != '' OR registered_country != '')
                AND (ceo_name != '' OR directors != '' OR directors != '[]' OR authorized_reps != '' OR authorized_reps != '[]')
                AND (phone != '' OR legal_phone != '' OR email != '' OR legal_email != '')
                AND register_type IS NOT NULL AND register_type != ''
                AND register_court IS NOT NULL AND register_court != ''
                AND registration_number IS NOT NULL AND registration_number != ''
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
        logger.warning(f"No legal entities with full metadata found to export (Run ID: {run_id})")
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
    'legal_form',
    
    # Structured Address (v4.0)
    'street_address',
    'postal_code',
    'city',
    'country',
    
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
                legal_form,
                COALESCE(street_address, registered_street, '') as street_address,
                COALESCE(postal_code, registered_zip, '') as postal_code,
                COALESCE(city, registered_city, '') as city,
                COALESCE(country, registered_country, '') as country,
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
