import aiosqlite
from src.database import DB_PATH
from src.utils import logger

async def reset_failed_domains():
    """
    Resets domains with FAILED_ or PROCESSING status back to PENDING.
    This allows retrying after fixing bugs or dependencies.
    """
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            # Count before
            async with db.execute("SELECT count(*) FROM queue WHERE status LIKE 'FAILED_%' OR status = 'PROCESSING'") as cursor:
                count = (await cursor.fetchone())[0]
            
            if count == 0:
                logger.info("No failed or stuck domains to reset.")
                return

            # Update
            await db.execute("""
                UPDATE queue 
                SET status = 'PENDING', updated_at = CURRENT_TIMESTAMP 
                WHERE status LIKE 'FAILED_%' OR status = 'PROCESSING'
            """)
            await db.commit()
            
            logger.info(f"Reset {count} domains to PENDING state.")
            
    except Exception as e:
        logger.error(f"Reset failed: {e}")
