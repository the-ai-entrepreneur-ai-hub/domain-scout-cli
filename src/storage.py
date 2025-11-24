import pandas as pd
from pathlib import Path
import aiosqlite
from .database import DB_PATH
from .utils import logger

async def export_to_csv(output_file: str = None, tld: str = None):
    """
    Exports the results table to a CSV file.
    """
    try:
        if not output_file:
            timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"data/results_{tld or 'all'}_{timestamp}.csv"
            
        Path(output_file).parent.mkdir(exist_ok=True)
        
        async with aiosqlite.connect(DB_PATH) as db:
            # Load to pandas
            # aiosqlite doesn't support direct pandas read, so we fetchall
            async with db.execute("SELECT * FROM results") as cursor:
                rows = await cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                
        if not rows:
            logger.warning("No results to export.")
            return
            
        df = pd.DataFrame(rows, columns=columns)
        
        # Filter by TLD if requested (though currently results might mix TLDs if used generally)
        if tld:
            suffix = tld if tld.startswith('.') else f".{tld}"
            df = df[df['domain'].str.endswith(suffix, na=False)]
            
        df.to_csv(output_file, index=False)
        logger.info(f"Exported {len(df)} rows to {output_file}")
        
    except Exception as e:
        logger.error(f"Export failed: {e}")
