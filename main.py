import argparse
import sys
import asyncio
import io
from pathlib import Path

# Fix Windows console encoding for Crawl4AI's Rich output
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from src.discovery import run_discovery
from src.database import init_db, get_sample_domains
from src.utils import logger

async def async_main():
    parser = argparse.ArgumentParser(description="TLD-Based Web Crawler PoC")
    
    subparsers = parser.add_subparsers(dest='task', required=True, help='Task to run')
    
    # Discovery Command
    discover_parser = subparsers.add_parser('discover', help='Discover domains and populate DB')
    discover_parser.add_argument("--tld", required=True, help="Top-Level Domain (e.g., .de). Use 'all' or '*' for any TLD.")
    discover_parser.add_argument("--limit", type=int, default=100, help="Max domains to find")
    discover_parser.add_argument("--print-sample", action="store_true", help="Print discovered domains after discovery")
    discover_parser.add_argument("--print-limit", type=int, default=50, help="Number of domains to print with --print-sample")
    
    # Crawl Command
    crawl_parser = subparsers.add_parser('crawl', help='Crawl domains from DB')
    crawl_parser.add_argument("--concurrency", type=int, default=10, help="Worker count")
    crawl_parser.add_argument("--limit", type=int, default=0, help="Max domains to crawl (0 = unlimited)")
    crawl_parser.add_argument("--enhanced", action="store_true", help="Use enhanced crawler with JS rendering")
    crawl_parser.add_argument("--playwright", action="store_true", help="Use Playwright for JavaScript rendering")
    crawl_parser.add_argument("--use-llm", action="store_true", help="Use LLM (Ollama) for intelligent extraction")
    crawl_parser.add_argument("--llm-provider", default="ollama/deepseek-r1:7b", help="LLM provider string")
    crawl_parser.add_argument("--llm-api-base", default="http://localhost:11434", help="Ollama API base URL")
    crawl_parser.add_argument("--ignore-robots", action="store_true", help="Ignore robots.txt rules (CAUTION: May get banned)")

    # Export Command
    export_parser = subparsers.add_parser('export', help='Export results to CSV')
    export_parser.add_argument("--output", help="Output file path (timestamp auto-added)")
    export_parser.add_argument("--tld", help="Filter by TLD")
    export_parser.add_argument("--enhanced", action="store_true", help="Export enhanced results")
    export_parser.add_argument("--json", action="store_true", help="Export as JSON instead of CSV")
    export_parser.add_argument("--legal-only", action="store_true", help="Export only legal entity information")
    export_parser.add_argument("--run-id", help="Export data for a specific Run ID (defaults to latest run)")
    export_parser.add_argument("--include-incomplete", action="store_true", 
                               help="Include entries without full metadata (default: only export complete records)")
    
    # Reset Command
    subparsers.add_parser('reset', help='Reset FAILED domains to PENDING')
    
    # Stats Command
    subparsers.add_parser('stats', help='Show crawling statistics')

    args = parser.parse_args()
    
    # Always init DB
    await init_db()
    
    if args.task == 'discover':
        raw_tld = args.tld.strip()
        any_mode = raw_tld.lower() in {"all", "any", "*", ""}
        tld = None if any_mode else raw_tld
        if tld and not tld.startswith('.'):
            tld = f".{tld}"
            
        logger.info(f"Starting Discovery for {tld or 'ANY'}")
        await run_discovery(tld, args.limit)
        logger.info("Discovery complete. Check 'queue' table in DB.")
        if args.print_sample:
            rows = await get_sample_domains(tld, args.print_limit)
            if not rows:
                logger.info("No domains available to print.")
            else:
                logger.info(f"Sample of discovered domains (up to {args.print_limit}):")
                for row in rows:
                    logger.info(f"{row['domain']} (source={row['source']})")
        
    elif args.task == 'crawl':
        if args.enhanced:
            from src.enhanced_crawler import EnhancedCrawler
            crawler = EnhancedCrawler(
                concurrency=args.concurrency,
                use_playwright=args.playwright,
                limit=args.limit,
                use_llm=getattr(args, 'use_llm', False),
                llm_provider=getattr(args, 'llm_provider', 'ollama/deepseek-r1:7b'),
                llm_api_base=getattr(args, 'llm_api_base', 'http://localhost:11434'),
                ignore_robots=getattr(args, 'ignore_robots', False)
            )
            await crawler.run()
        else:
            from src.crawler import Crawler
            crawler = Crawler(
                concurrency=args.concurrency,
                ignore_robots=getattr(args, 'ignore_robots', False)
            )
            await crawler.run()
        
    elif args.task == 'export':
        if getattr(args, 'legal_only', False):
            from src.enhanced_storage import export_legal_entities_to_csv
            full_metadata_only = not getattr(args, 'include_incomplete', False)
            await export_legal_entities_to_csv(args.output, args.tld, args.run_id, full_metadata_only)
        elif args.enhanced:
            from src.enhanced_storage import export_enhanced_to_csv, export_enhanced_to_json
            if args.json:
                await export_enhanced_to_json(args.output, args.tld, args.run_id)
            else:
                await export_enhanced_to_csv(args.output, args.tld, True, args.run_id)
        else:
            from src.storage import export_to_csv
            await export_to_csv(args.output, args.tld)
        
    elif args.task == 'reset':
        from src.reset_tool import reset_failed_domains
        await reset_failed_domains()
        
    elif args.task == 'stats':
        from src.enhanced_storage import print_statistics
        await print_statistics()

def main():
    try:
        # Note: Do NOT use WindowsSelectorEventLoopPolicy on Windows
        # Playwright/Crawl4AI requires ProactorEventLoop for subprocess support
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
    except Exception as e:
        logger.exception(f"Critical error: {e}")

if __name__ == "__main__":
    main()
