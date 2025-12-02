"""
Stats Extension - Colored summary output at the end of crawl
"""
import logging
from scrapy import signals
from datetime import datetime

# ANSI Color Codes
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


class StatsExtension:
    """Extension to print colored summary stats at the end of crawl"""
    
    def __init__(self, crawler):
        self.crawler = crawler
        self.start_time = None
        self.blocked_domains = set()
        self.error_counts = {}
    
    @classmethod
    def from_crawler(cls, crawler):
        ext = cls(crawler)
        crawler.signals.connect(ext.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(ext.spider_closed, signal=signals.spider_closed)
        return ext
    
    def spider_opened(self, spider):
        self.start_time = datetime.now()
        print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
        print(f"{Colors.CYAN}[*] Spider started at {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}{Colors.END}")
        print(f"{Colors.BOLD}{'='*60}{Colors.END}\n")
    
    def spider_closed(self, spider, reason):
        stats = self.crawler.stats.get_stats()
        end_time = datetime.now()
        duration = end_time - self.start_time if self.start_time else None
        
        # Calculate metrics
        items = stats.get('item_scraped_count', 0)
        total_requests = stats.get('downloader/request_count', 0)
        success_responses = stats.get('downloader/response_status_count/200', 0)
        blocked_403 = stats.get('downloader/response_status_count/403', 0)
        not_found_404 = stats.get('downloader/response_status_count/404', 0)
        server_errors = sum([
            stats.get('downloader/response_status_count/500', 0),
            stats.get('downloader/response_status_count/502', 0),
            stats.get('downloader/response_status_count/503', 0),
        ])
        dns_errors = stats.get('downloader/exception_type_count/twisted.internet.error.DNSLookupError', 0)
        timeout_errors = stats.get('downloader/exception_type_count/twisted.web._newclient.ResponseNeverReceived', 0)
        connection_refused = stats.get('downloader/exception_type_count/twisted.internet.error.ConnectionRefusedError', 0)
        
        # Spider stats
        spider_success = getattr(spider, 'stats', {}).get('success', items)
        spider_failed = getattr(spider, 'stats', {}).get('failed', 0)
        spider_total = getattr(spider, 'stats', {}).get('total', spider_success + spider_failed)
        
        success_rate = (spider_success / spider_total * 100) if spider_total > 0 else 0
        
        # Print summary
        print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
        print(f"{Colors.BOLD}           CRAWL SUMMARY{Colors.END}")
        print(f"{Colors.BOLD}{'='*60}{Colors.END}")
        
        # Duration
        if duration:
            minutes, seconds = divmod(duration.total_seconds(), 60)
            hours, minutes = divmod(minutes, 60)
            print(f"{Colors.CYAN}Duration:{Colors.END} {int(hours)}h {int(minutes)}m {int(seconds)}s")
        
        print(f"\n{Colors.BOLD}--- Domains ---{Colors.END}")
        print(f"  Total domains:    {Colors.CYAN}{spider_total}{Colors.END}")
        print(f"  {Colors.GREEN}Successful:{Colors.END}        {Colors.GREEN}{spider_success}{Colors.END}")
        print(f"  {Colors.RED}Failed:{Colors.END}            {Colors.RED}{spider_failed}{Colors.END}")
        print(f"  {Colors.BOLD}Success rate:{Colors.END}      {self._color_rate(success_rate)}{success_rate:.1f}%{Colors.END}")
        
        print(f"\n{Colors.BOLD}--- Items Extracted ---{Colors.END}")
        print(f"  {Colors.GREEN}Total items:{Colors.END}       {Colors.GREEN}{items}{Colors.END}")
        if duration:
            items_per_min = items / (duration.total_seconds() / 60) if duration.total_seconds() > 0 else 0
            print(f"  Items/minute:     {Colors.CYAN}{items_per_min:.1f}{Colors.END}")
        
        print(f"\n{Colors.BOLD}--- HTTP Responses ---{Colors.END}")
        print(f"  {Colors.GREEN}200 OK:{Colors.END}            {Colors.GREEN}{success_responses}{Colors.END}")
        print(f"  {Colors.YELLOW}403 Blocked:{Colors.END}       {Colors.YELLOW}{blocked_403}{Colors.END}")
        print(f"  {Colors.YELLOW}404 Not Found:{Colors.END}     {Colors.YELLOW}{not_found_404}{Colors.END}")
        print(f"  {Colors.RED}5xx Errors:{Colors.END}        {Colors.RED}{server_errors}{Colors.END}")
        
        print(f"\n{Colors.BOLD}--- Connection Errors ---{Colors.END}")
        print(f"  {Colors.RED}DNS failures:{Colors.END}      {Colors.RED}{dns_errors}{Colors.END}")
        print(f"  {Colors.RED}Timeouts:{Colors.END}          {Colors.RED}{timeout_errors}{Colors.END}")
        print(f"  {Colors.RED}Conn refused:{Colors.END}      {Colors.RED}{connection_refused}{Colors.END}")
        
        # Recommendations
        print(f"\n{Colors.BOLD}--- Recommendations ---{Colors.END}")
        if blocked_403 > 50:
            print(f"  {Colors.YELLOW}[!] High blocking rate ({blocked_403} sites). Consider:{Colors.END}")
            print(f"      - Using residential proxies")
            print(f"      - Reducing concurrency")
            print(f"      - Adding more delays between requests")
        if dns_errors > 100:
            print(f"  {Colors.YELLOW}[!] Many DNS failures ({dns_errors}). Consider:{Colors.END}")
            print(f"      - Pre-validating domains before crawling")
            print(f"      - Using a domain age filter")
        if success_rate < 30:
            print(f"  {Colors.RED}[!] Low success rate ({success_rate:.1f}%). Consider:{Colors.END}")
            print(f"      - Using targeted discovery (DDG dorks)")
            print(f"      - Filtering crt.sh results better")
        if success_rate >= 50:
            print(f"  {Colors.GREEN}[+] Good success rate! No major issues.{Colors.END}")
        
        print(f"\n{Colors.BOLD}--- Output Files ---{Colors.END}")
        print(f"  {Colors.CYAN}CSV:{Colors.END}  /app/data/legal_notices_[timestamp].csv")
        print(f"  {Colors.CYAN}DB:{Colors.END}   PostgreSQL (if configured)")
        
        print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
        print(f"{Colors.GREEN}[+] Crawl finished at {end_time.strftime('%Y-%m-%d %H:%M:%S')}{Colors.END}")
        print(f"{Colors.BOLD}{'='*60}{Colors.END}\n")
    
    def _color_rate(self, rate):
        if rate >= 50:
            return Colors.GREEN
        elif rate >= 30:
            return Colors.YELLOW
        else:
            return Colors.RED
