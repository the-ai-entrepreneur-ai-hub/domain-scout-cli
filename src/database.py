import aiosqlite
from pathlib import Path
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
        
        # Results Table
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

async def get_pending_domains(limit: int = 100):
    """Fetches pending domains from the queue."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
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
