import os

BOT_NAME = 'legal_crawler'

SPIDER_MODULES = ['legal_crawler.spiders']
NEWSPIDER_MODULE = 'legal_crawler.spiders'

# Crawl responsibly
ROBOTSTXT_OBEY = False  # Many Impressum pages are blocked by robots.txt

# Stealth User-Agent (rotated by middleware)
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

# Playwright settings
DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}

TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

PLAYWRIGHT_BROWSER_TYPE = "chromium"
PLAYWRIGHT_LAUNCH_OPTIONS = {
    "headless": True,
    "args": [
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars",
    ],
}

# Stealth & Anti-Detection Settings
STEALTH_ENABLED = True
ROTATE_USER_AGENT = True
RANDOM_DELAY_MIN = 0.5
RANDOM_DELAY_MAX = 2.5

# Proxy Settings (Enabled for production)
PROXY_ENABLED = True

# Downloader Middlewares
DOWNLOADER_MIDDLEWARES = {
    'scrapy.downloadermiddlewares.httpcompression.HttpCompressionMiddleware': 810,
    'legal_crawler.stealth_middleware.StealthMiddleware': 550,
    'legal_crawler.stealth_middleware.RandomDelayMiddleware': 100,
    'legal_crawler.stealth_middleware.ProxyRotationMiddleware': 750,
}

# Concurrency settings (balanced for stealth)
CONCURRENT_REQUESTS = 8
CONCURRENT_REQUESTS_PER_DOMAIN = 2
DOWNLOAD_DELAY = 1
RANDOMIZE_DOWNLOAD_DELAY = True

# Retry settings
RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429, 403]

# Timeout settings
DOWNLOAD_TIMEOUT = 90

# AutoThrottle for polite crawling
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1
AUTOTHROTTLE_MAX_DELAY = 10
AUTOTHROTTLE_TARGET_CONCURRENCY = 4.0

# Pipeline settings
ITEM_PIPELINES = {
    'legal_crawler.pipelines.ExtractionPipeline': 100,
    # 'legal_crawler.pipelines.LLMEnhancementPipeline': 150,  # Disabled - uses too much memory
    'legal_crawler.whois_pipeline.WhoisPipeline': 200,
    'legal_crawler.pipelines.PostgresPipeline': 300,
    'legal_crawler.pipelines.CsvPipeline': 400,
}

# Database settings
DATABASE_URL = os.getenv('DATABASE_URL')
REDIS_URL = os.getenv('REDIS_URL')
OLLAMA_URL = os.getenv('OLLAMA_URL')

# Output settings
FEED_EXPORT_ENCODING = 'utf-8'
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# Request fingerprinting
REQUEST_FINGERPRINTER_IMPLEMENTATION = '2.7'

# Memory management
MEMUSAGE_ENABLED = True
MEMUSAGE_LIMIT_MB = 2048
MEMUSAGE_WARNING_MB = 1536
