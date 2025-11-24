import argparse
import sys
import asyncio
from pathlib import Path
from src.discovery import run_discovery
from src.database import init_db
from src.utils import logger

async def async_main():
    parser = argparse.ArgumentParser(description="TLD-Based Web Crawler PoC")
    
    subparsers = parser.add_subparsers(dest='task', required=True, help='Task to run')
    
    # Discovery Command
    discover_parser = subparsers.add_parser('discover', help='Discover domains and populate DB')
    discover_parser.add_argument("--tld", required=True, help="Top-Level Domain (e.g., .de)")
    discover_parser.add_argument("--limit", type=int, default=100, help="Max domains to find")
    
    # Crawl Command
    crawl_parser = subparsers.add_parser('crawl', help='Crawl domains from DB')
    crawl_parser.add_argument("--concurrency", type=int, default=10, help="Worker count")

    # Export Command
    export_parser = subparsers.add_parser('export', help='Export results to CSV')
    export_parser.add_argument("--output", help="Output CSV file path")
    export_parser.add_argument("--tld", help="Filter by TLD")
    
    # Reset Command
    subparsers.add_parser('reset', help='Reset FAILED domains to PENDING')

    args = parser.parse_args()
    
    # Always init DB
    await init_db()
    
    if args.task == 'discover':
        tld = args.tld.strip()
        if not tld.startswith('.'):
            tld = f".{tld}"
            
        logger.info(f"Starting Discovery for {tld}")
        await run_discovery(tld, args.limit)
        logger.info("Discovery complete. Check 'queue' table in DB.")
        
    elif args.task == 'crawl':
        from src.crawler import Crawler
        crawler = Crawler(concurrency=args.concurrency)
        await crawler.run()
        
    elif args.task == 'export':
        from src.storage import export_to_csv
        await export_to_csv(args.output, args.tld)
        
    elif args.task == 'reset':
        from src.reset_tool import reset_failed_domains
        await reset_failed_domains()

def main():
    try:
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
    except Exception as e:
        logger.exception(f"Critical error: {e}")

if __name__ == "__main__":
    main()
