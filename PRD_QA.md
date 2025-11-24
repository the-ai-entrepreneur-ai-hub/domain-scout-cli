# 50 Critical Questions regarding the TLD Crawler PRD

## I. Problem Solving & Scope (1-10)
1.  **Discovery Completeness:** Does the hybrid approach (CommonCrawl + Tranco) guarantee *fresh* domains, or will we mostly find old/established ones, missing new startups?
2.  **Search Engine Fallback:** The PRD mentions "Search Engine Fallback" as optional/limited. If CommonCrawl is outdated, isn't this actually critical for finding *active* businesses?
3.  **Target Accuracy:** How does the system differentiate between a parked domain (e.g., GoDaddy landing page) and an active business website?
4.  **False Positives:** What prevents the crawler from scraping directory sites (e.g., yellowpages.de) and treating them as a single company instead of many?
5.  **Data Freshness:** Common Crawl data can be months old. How does the PRD address the risk of crawling dead domains that no longer exist?
6.  **Scope Creep:** Is "extracting company info" too vague? How do we define a "successful" extraction for a website that is just a landing page with an email?
7.  **Language Support:** The PRD targets TLDs like `.de` or `.fr`. Does the extractor need language-specific heuristics (e.g., looking for "Impressum" vs "Contact")?
8.  **Redirect Chains:** If `example.de` redirects to `example.com`, should we still scrape it? The PRD says follow redirects, but does this violate the "TLD-specific" constraint?
9.  **Subdomains:** Does the PRD cover subdomains (e.g., `shop.example.de`) or only root domains? Many businesses live on subdomains (e.g., `blog.`, `store.`).
10. **Dynamic Content:** The PRD excludes deep crawling/SPA rendering (no Selenium/Playwright). What percentage of modern sites will be missed because they render content via JavaScript?

## II. Framework & Architecture (11-20)
11. **Concurrency Model:** Why `asyncio` over multi-threading? Is CPU usage for parsing HTML going to block the event loop, necessitating `ProcessPoolExecutor`?
12. **Scalability:** If the user inputs a popular TLD like `.com` (accidentally or intentionally), will `sqlite3` lock up under concurrent writes?
13. **State Management:** The PRD mentions a "resume" capability is nice-to-have. Without it, doesn't a crash on the 9,000th domain mean 3 hours of wasted time?
14. **Resource Limits:** With `aiohttp`, what happens if 100 workers all hit large 10MB HTML files simultaneously? Is there a global memory limit mechanism?
15. **Distributed Future:** Is the architecture modular enough to eventually split the "Discovery" and "Crawling" into separate services (e.g., Producer-Consumer pattern)?
16. **Database Choice:** Why SQLite for a potential dataset of millions of rows? Would `DuckDB` be better for analytical queries later, or `Postgres` for concurrency?
17. **Blocking I/O:** Are we ensuring that file writes (CSV logging) don't block the async event loop?
18. **Dependency Injection:** Are we hardcoding the `Crawler` class dependencies, or injecting them to make unit testing `discovery.py` easier?
19. **Configuration Management:** Is `config.yaml` flexible enough to handle per-TLD rules (e.g., different regex for `.de` vs `.uk` phone numbers)?
20. **Queue System:** We are using a simple list/set for URLs. Should we use a priority queue to prioritize "promising" domains (e.g., those with "gmbh" in the name)?

## III. Tools & Libraries (21-30)
21. **Network Client:** Why `aiohttp` instead of `httpx`? `httpx` has better modern defaults and HTTP/2 support.
22. **HTML Parsing:** `BeautifulSoup4` is slow. If we need speed (1-2 pages/sec/worker), shouldn't we strictly use `lxml` or `selectolax`?
23. **Retry Logic:** Is `tenacity` configured to handle specific HTTP status codes (429 Too Many Requests) with exponential backoff, or just generic retries?
24. **User-Agent:** `fake-useragent` can sometimes generate outdated agents. Is it better to have a static, curated list of high-quality "Chrome/Win10" headers?
25. **Robots.txt:** Which library handles `robots.txt` parsing? Standard `urllib.robotparser` or a more robust 3rd party lib that handles wildcards correctly?
26. **Data Validation:** Are we using `pydantic` for data validation before storage? It ensures the CSV/DB schema is respected strictly.
27. **DNS Resolution:** Should we use `aioDNS`? Default DNS resolution in `asyncio` can be a bottleneck when crawling thousands of domains.
28. **Logging:** Is `logging` module thread/async-safe enough for high throughput, or should we use `structlog` for structured JSON logs?
29. **CSV Handling:** `pandas` is heavy just for writing CSVs. Would the built-in `csv` module be lighter and faster for appending rows stream-wise?
30. **Testing:** What testing framework? `pytest` with `pytest-asyncio`? How do we mock live HTTP requests during tests (e.g., `aioresponses`)?

## IV. Anti-Bot & Compliance (31-40)
31. **Proxy Support:** The PRD explicitly *excludes* proxies. Without them, won't Cloudflare block the crawler after the first 50 requests?
32. **Fingerprinting:** Apart from User-Agent, are we randomizing TLS fingerprints (JA3)? `aiohttp` has a very standard fingerprint that is easily blocked.
33. **Rate Limiting:** Is the rate limit global or per-domain? If we crawl 1000 *different* domains, do we need a delay at all?
34. **Honeypots:** How does the crawler detect "trap" links (infinite calendar pages) that keep the crawler stuck on one site? (Though we only crawl depth 1).
35. **GDPR Precision:** The regex for email extraction might grab `john.doe@company.com`. Is this a violation? How strict is "no personal data"?
36. **Terms of Service:** Does "publicly available" legally cover scraping data for a database? This is a legal gray area (e.g., LinkedIn vs HiQ).
37. **Identification:** Should the User-Agent explicitly identify the bot (e.g., `Bot/1.0 +http://mydomain.com/bot`) so webmasters can contact the owner?
38. **Sensitive Data:** What if the crawler accidentally hits a configuration file (`.env`) exposed on a web server? Should we explicitly *exclude* file extensions?
39. **Redirect Loops:** How robust is the redirect handling against infinite loops between `http` and `https`?
40. **Blacklisting:** Is there a mechanism to manually blacklist domains that request to be removed or are known spam?

## V. Data Quality & Edge Cases (41-50)
41. **Encoding Hell:** How does the extractor handle mixed charsets (UTF-8 vs ISO-8859-1), common in older European sites?
42. **Email Obfuscation:** Many sites obfuscate emails (e.g., `info [at] domain.de`). Will the regex handle this?
43. **Phone Formatting:** European phone numbers vary wildly (`+49 (0) 123`, `0123 / 456`). Can we normalize this data for the DB?
44. **Date Extraction:** "Last Scraped" is easy, but can we extract "Last Updated" from the site content to know if the business is active?
45. **Empty Results:** If a site is active but has no email/phone on the home page (only a form), is it recorded as "failed" or "partial"?
46. **Duplicate Content:** If `company-a.de` and `company-b.de` are aliases for the same site, how do we deduplicate the *content* in the DB?
47. **Javascript Redirects:** `meta refresh` or JS `window.location` redirects won't be caught by `aiohttp`. Is this an acceptable loss?
48. **Large Files:** What if the "home page" is actually a 50MB PDF or video file? Do we check `Content-Type` headers before downloading body?
49. **Structured Data:** Why rely on regex if the site has JSON-LD (Schema.org) markup? Shouldn't that be the primary extraction source?
50. **Maintenance:** If the Tranco list format changes or Common Crawl API updates, how easily can the `discovery` module be patched?
