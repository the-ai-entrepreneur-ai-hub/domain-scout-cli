import aiosqlite
from pathlib import Path
from typing import Optional
from src.utils import logger
import asyncio

DB_PATH = Path("data/crawler_data.db")

async def init_db():
    """Initializes the database with required tables."""
    DB_PATH.parent.mkdir(exist_ok=True)
    
    async with aiosqlite.connect(DB_PATH) as db:
        # Queue Table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain TEXT UNIQUE NOT NULL,
                source TEXT NOT NULL,
                status TEXT DEFAULT 'PENDING',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Results Table (Original)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain TEXT UNIQUE NOT NULL,
                company_name TEXT,
                description TEXT,
                email TEXT,
                phone TEXT,
                address TEXT,
                crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Enhanced Results Table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS results_enhanced (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain TEXT UNIQUE NOT NULL,
                company_name TEXT,
                description TEXT,
                emails TEXT,
                phones TEXT,
                address TEXT,
                industry TEXT,
                vat_id TEXT,
                social_linkedin TEXT,
                social_facebook TEXT,
                social_twitter TEXT,
                social_instagram TEXT,
                social_youtube TEXT,
                language TEXT,
                confidence_score REAL,
                business_hours TEXT,
                website_type TEXT,
                crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                run_id TEXT
            )
        """)
        
        # Legal Entities Table (v4.0 - Robust Extraction)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS legal_entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain TEXT UNIQUE NOT NULL,
                legal_name TEXT,
                legal_form TEXT,
                trading_name TEXT,
                
                -- Registration
                register_type TEXT,
                register_court TEXT,
                registration_number TEXT,
                vat_id TEXT,
                tax_id TEXT,
                siret TEXT,
                siren TEXT,
                data_protection_id TEXT,
                
                -- Representatives
                ceo_name TEXT,
                directors TEXT,  -- JSON array or comma-separated
                authorized_reps TEXT,  -- JSON array
                
                -- Structured Address (new in v4.0)
                street_address TEXT,
                postal_code TEXT,
                city TEXT,
                state TEXT,
                country TEXT,
                
                -- Legacy Address fields (for backwards compatibility)
                registered_street TEXT,
                registered_zip TEXT,
                registered_city TEXT,
                registered_state TEXT,
                registered_country TEXT,
                
                -- Postal Address
                postal_street TEXT,
                postal_zip TEXT,
                postal_city TEXT,
                postal_state TEXT,
                postal_country TEXT,
                
                -- Contact Information
                phone TEXT,
                email TEXT,
                fax TEXT,
                legal_email TEXT,
                legal_phone TEXT,
                fax_number TEXT,
                dpo_name TEXT,
                dpo_email TEXT,
                
                -- Domain Registrant (WHOIS Data)
                registrant_name TEXT,
                registrant_address TEXT,
                registrant_city TEXT,
                registrant_zip TEXT,
                registrant_country TEXT,
                registrant_email TEXT,
                registrant_phone TEXT,
                
                -- Metadata
                legal_notice_url TEXT,
                extraction_confidence REAL,
                extraction_date TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                run_id TEXT
            )
        """)
        
        # Add run_id column to existing tables if missing
        try:
            await db.execute("ALTER TABLE results_enhanced ADD COLUMN run_id TEXT")
        except Exception:
            pass
            
        try:
            await db.execute("ALTER TABLE legal_entities ADD COLUMN run_id TEXT")
        except Exception:
            pass
            
        # Add registrant columns if missing (migration)
        for col in ['registrant_name', 'registrant_address', 'registrant_city', 'registrant_zip', 'registrant_country', 'registrant_email', 'registrant_phone']:
            try:
                await db.execute(f"ALTER TABLE legal_entities ADD COLUMN {col} TEXT")
            except Exception:
                pass
        
        # Index for faster queue lookup
        await db.execute("CREATE INDEX IF NOT EXISTS idx_queue_status ON queue(status)")
        await db.commit()
        logger.info("Database initialized.")

async def insert_domains(domains: list[tuple[str, str]]):
    """
    Bulk inserts domains into the queue.
    domains: list of (domain, source) tuples.
    Ignores duplicates via INSERT OR IGNORE.
    """
    if not domains:
        return

    async with aiosqlite.connect(DB_PATH) as db:
        await db.executemany(
            "INSERT OR IGNORE INTO queue (domain, source) VALUES (?, ?)",
            domains
        )
        await db.commit()
        logger.info(f"Inserted/Processed {len(domains)} domains into DB.")

async def get_pending_domains(limit: int = 100, tld_filter: Optional[str] = None):
    """
    Fetches pending domains from the queue.
    Optionally filters by TLD.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        if tld_filter:
            tld = tld_filter if tld_filter.startswith('.') else f".{tld_filter}"
            pattern = f"%{tld}"
            cursor = await db.execute(
                "SELECT id, domain FROM queue WHERE status = 'PENDING' AND domain LIKE ? LIMIT ?",
                (pattern, limit)
            )
        else:
            cursor = await db.execute(
                "SELECT id, domain FROM queue WHERE status = 'PENDING' LIMIT ?",
                (limit,)
            )
            
        rows = await cursor.fetchall()
        return rows

async def update_domain_status(domain_id: int, status: str):
    """Updates the status of a domain in the queue."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE queue SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, domain_id)
        )
        await db.commit()

async def get_sample_domains(tld: Optional[str] = None, limit: int = 50):
    """
    Fetches a sample of domains (optionally filtered by TLD) ordered by newest first.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if tld:
            suffix = tld if tld.startswith('.') else f".{tld}"
            like_pattern = f"%{suffix}"
            cursor = await db.execute(
                "SELECT domain, source, created_at FROM queue WHERE domain LIKE ? ORDER BY created_at DESC LIMIT ?",
                (like_pattern, limit)
            )
        else:
            cursor = await db.execute(
                "SELECT domain, source, created_at FROM queue ORDER BY created_at DESC LIMIT ?",
                (limit,)
            )
        rows = await cursor.fetchall()
        return rows
