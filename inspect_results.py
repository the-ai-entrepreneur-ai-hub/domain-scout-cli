import asyncio
import aiosqlite
import sys
import json
from src.database import DB_PATH

# Windows fix
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

async def inspect_results():
    async with aiosqlite.connect(DB_PATH) as db:
        # Get 3 distinct results with good data
        query = """
            SELECT 
                domain, 
                legal_name, 
                registration_number, 
                registered_city, 
                ceo_name,
                register_court
            FROM legal_entities 
            WHERE legal_name IS NOT NULL AND legal_name != ''
            ORDER BY extraction_confidence DESC, last_updated DESC
            LIMIT 3
        """
        
        async with db.execute(query) as cursor:
            rows = await cursor.fetchall()
            
        print("\n" + "="*60)
        print("TOP 3 EXTRACTED RESULTS (VERIFICATION)")
        print("="*60)
        
        if not rows:
            print("No results found in database.")
            return

        for i, row in enumerate(rows, 1):
            domain, name, reg, city, ceo, court = row
            print(f"\nResult #{i}: {domain}")
            print(f"-"*30)
            print(f"Legal Name:   {name}")
            print(f"City:         {city}")
            print(f"Register:     {reg} ({court or 'Court not found'})")
            print(f"CEO/Mgmt:     {ceo}")
            print(f"-"*30)

if __name__ == "__main__":
    asyncio.run(inspect_results())
