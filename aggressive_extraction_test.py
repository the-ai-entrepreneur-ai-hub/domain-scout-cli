"""
AGGRESSIVE Legal Extraction Test Suite v2
Tests 60+ domains across DE, UK, FR with CORRECTED URLs.
"""
import asyncio
import httpx
import csv
from datetime import datetime
from collections import defaultdict
from src.robust_legal_extractor import RobustLegalExtractor
from src.enhanced_storage import save_robust_legal_entity

# German domains - CORRECTED URLS
GERMAN_DOMAINS = [
    ('heise.de', 'https://www.heise.de/impressum.html'),
    ('zeit.de', 'https://www.zeit.de/impressum/index'),
    ('spiegel.de', 'https://www.spiegel.de/impressum'),
    ('kicker.de', 'https://www.kicker.de/impressum'),
    ('t-online.de', 'https://www.t-online.de/impressum/'),
    ('web.de', 'https://web.de/impressum/'),
    ('gmx.net', 'https://www.gmx.net/impressum/'),
    ('welt.de', 'https://www.welt.de/services/article7893735/Impressum.html'),
    ('faz.net', 'https://www.faz.net/impressum/'),
    ('sueddeutsche.de', 'https://www.sueddeutsche.de/impressum'),
    ('autobild.de', 'https://www.autobild.de/impressum/'),
    ('netzwelt.de', 'https://www.netzwelt.de/impressum.html'),
    ('otto.de', 'https://www.otto.de/service/impressum/'),
    ('sap.com', 'https://www.sap.com/germany/about/legal/impressum.html'),
    ('bosch.de', 'https://www.bosch.de/impressum/'),
    ('telekom.de', 'https://www.telekom.de/impressum'),
    ('vodafone.de', 'https://www.vodafone.de/impressum.html'),
    ('sparkasse.de', 'https://www.sparkasse.de/impressum.html'),
    ('ing.de', 'https://www.ing.de/impressum/'),
    ('hetzner.com', 'https://www.hetzner.com/de/rechtliches/impressum/'),
    ('strato.de', 'https://www.strato.de/impressum/'),
    ('ionos.de', 'https://www.ionos.de/impressum'),
    # Additional German sites
    ('check24.de', 'https://www.check24.de/impressum/'),
    ('mobile.de', 'https://www.mobile.de/service/impressum/'),
    ('immobilienscout24.de', 'https://www.immobilienscout24.de/impressum/'),
    ('dhl.de', 'https://www.dhl.de/de/toolbar/footer/impressum.html'),
    ('deutsche-post.de', 'https://www.deutschepost.de/de/impressum.html'),
    ('adac.de', 'https://www.adac.de/impressum/'),
    ('eventim.de', 'https://www.eventim.de/impressum/'),
    ('thomann.de', 'https://www.thomann.de/de/compinfo.html'),
    ('conrad.de', 'https://www.conrad.de/de/service/impressum.html'),
    ('notebooksbilliger.de', 'https://www.notebooksbilliger.de/impressum'),
]

# UK domains - CORRECTED URLs
UK_DOMAINS = [
    ('sky.com', 'https://www.sky.com/help/articles/contact-sky'),
    ('tesco.com', 'https://www.tesco.com/help/terms-and-conditions/'),
    ('asda.com', 'https://www.asda.com/terms-and-conditions'),
    ('boots.com', 'https://www.boots.com/terms-and-conditions'),
    ('currys.co.uk', 'https://www.currys.co.uk/terms-and-conditions'),
    ('asos.com', 'https://www.asos.com/terms-and-conditions/'),
    ('next.co.uk', 'https://www.next.co.uk/termsandconditions'),
    ('johnlewis.com', 'https://www.johnlewis.com/customer-services/terms-and-conditions'),
]

# French domains - CORRECTED URLs
FRENCH_DOMAINS = [
    ('liberation.fr', 'https://www.liberation.fr/mentions-legales/'),
    ('bfmtv.com', 'https://www.bfmtv.com/mentions-legales/'),
    ('fnac.com', 'https://www.fnac.com/CGU'),
    ('darty.com', 'https://www.darty.com/achat/informations/mentions_legales.html'),
    ('carrefour.fr', 'https://www.carrefour.fr/mentions-legales'),
    ('auchan.fr', 'https://www.auchan.fr/mentions-legales'),
    ('laposte.fr', 'https://www.laposte.fr/mentions-legales'),
]

async def fetch_page(url, timeout=30):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'de-DE,de;q=0.9,en;q=0.7,fr;q=0.5',
    }
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers, verify=False) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text

def analyze_quality(result):
    issues = []
    score = 0
    name = result.get('legal_name', '')
    if name:
        if len(name) > 80: issues.append('NAME_TOO_LONG')
        elif len(name) < 5: issues.append('NAME_TOO_SHORT')
        elif any(w in name.lower() for w in ['navigation', 'menu', 'cookie']): issues.append('NAME_HAS_NOISE')
        else: score += 20
    else: issues.append('NO_NAME')
    if result.get('legal_form'): score += 10
    else: issues.append('NO_LEGAL_FORM')
    if result.get('street_address'):
        if len(result['street_address']) > 60: issues.append('STREET_TOO_LONG')
        else: score += 15
    else: issues.append('NO_STREET')
    if result.get('postal_code'): score += 5
    else: issues.append('NO_ZIP')
    if result.get('city'):
        if len(result['city']) > 30: issues.append('CITY_TOO_LONG')
        else: score += 10
    else: issues.append('NO_CITY')
    if result.get('registration_number'): score += 15
    else: issues.append('NO_REG_NUMBER')
    if result.get('vat_id'): score += 10
    else: issues.append('NO_VAT')
    if result.get('email'): score += 5
    else: issues.append('NO_EMAIL')
    if result.get('phone'): score += 5
    else: issues.append('NO_PHONE')
    if result.get('ceo_name'): score += 5
    else: issues.append('NO_CEO')
    grade = 'A' if score >= 80 else 'B' if score >= 60 else 'C' if score >= 40 else 'D' if score >= 20 else 'F'
    return {'score': score, 'issues': issues, 'grade': grade}

async def test_domain(domain, url, extractor, country):
    try:
        html = await fetch_page(url)
        result = extractor.extract(html, url)
        result['domain'] = domain
        quality = analyze_quality(result)
        try: await save_robust_legal_entity(result)
        except: pass
        return {'status': 'success', 'domain': domain, 'country': country, 'result': result, 'quality': quality}
    except httpx.HTTPStatusError as e:
        return {'status': 'http_error', 'domain': domain, 'country': country, 'error': str(e.response.status_code)}
    except httpx.TimeoutException:
        return {'status': 'timeout', 'domain': domain, 'country': country, 'error': 'Timeout'}
    except Exception as e:
        return {'status': 'error', 'domain': domain, 'country': country, 'error': str(e)[:80]}

async def run_tests(domains, country, extractor):
    results = []
    for domain, url in domains:
        print(f"  Testing {domain}...", end=' ', flush=True)
        result = await test_domain(domain, url, extractor, country)
        if result['status'] == 'success':
            print(f"[{result['quality']['grade']}] Score: {result['quality']['score']}")
        else:
            print(f"[FAIL] {result['error']}")
        results.append(result)
        await asyncio.sleep(0.5)
    return results

def print_report(all_results):
    print("\n" + "="*70)
    print("AGGRESSIVE EXTRACTION TEST REPORT v2")
    print("="*70)
    total = len(all_results)
    success = sum(1 for r in all_results if r['status'] == 'success')
    print(f"\nOverall: {success}/{total} successful ({success/total*100:.1f}%)")
    by_country = defaultdict(list)
    for r in all_results: by_country[r['country']].append(r)
    for country, results in by_country.items():
        cs = sum(1 for r in results if r['status'] == 'success')
        print(f"  {country}: {cs}/{len(results)}")
    print("\n" + "-"*40 + "\nGRADE DISTRIBUTION\n" + "-"*40)
    grades = defaultdict(int)
    for r in all_results:
        if r['status'] == 'success': grades[r['quality']['grade']] += 1
    for g in ['A','B','C','D','F']: print(f"  Grade {g}: {grades[g]:3d} {'#'*grades[g]}")
    print("\n" + "-"*40 + "\nCOMMON ISSUES\n" + "-"*40)
    issues = defaultdict(int)
    successful = [r for r in all_results if r['status'] == 'success']
    for r in successful:
        for i in r['quality']['issues']: issues[i] += 1
    for issue, count in sorted(issues.items(), key=lambda x: -x[1])[:10]:
        print(f"  {issue}: {count} ({count/len(successful)*100:.0f}%)")
    print("\n" + "-"*40 + "\nTOP 10 BEST\n" + "-"*40)
    successful.sort(key=lambda x: -x['quality']['score'])
    for r in successful[:10]:
        name = r['result'].get('legal_name', 'N/A')[:40]
        print(f"  [{r['quality']['grade']}] {r['quality']['score']:3d} {r['domain']:22s} {name}")
    print("\n" + "-"*40 + "\nFIELD COVERAGE\n" + "-"*40)
    for f in ['legal_name','legal_form','street_address','postal_code','city','registration_number','vat_id','ceo_name','phone','email']:
        c = sum(1 for r in successful if r['result'].get(f))
        pct = c/len(successful)*100 if successful else 0
        print(f"  {f:20s}: {pct:5.1f}% {'#'*int(pct/5)}")
    failures = [r for r in all_results if r['status'] != 'success']
    if failures:
        print(f"\n" + "-"*40 + f"\nFAILED ({len(failures)})\n" + "-"*40)
        for r in failures: print(f"  {r['domain']:25s} {r['status']}: {r.get('error','')}")

async def main():
    print("\n" + "#"*70)
    print("# AGGRESSIVE LEGAL EXTRACTION TEST v2")
    print("#"*70)
    extractor = RobustLegalExtractor()
    all_results = []
    print(f"\n[DE] Testing {len(GERMAN_DOMAINS)} German domains...")
    all_results.extend(await run_tests(GERMAN_DOMAINS, 'DE', extractor))
    print(f"\n[UK] Testing {len(UK_DOMAINS)} UK domains...")
    all_results.extend(await run_tests(UK_DOMAINS, 'UK', extractor))
    print(f"\n[FR] Testing {len(FRENCH_DOMAINS)} French domains...")
    all_results.extend(await run_tests(FRENCH_DOMAINS, 'FR', extractor))
    print_report(all_results)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = f"data/aggressive_test_v2_{ts}.csv"
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['domain','country','status','grade','score','legal_name','legal_form','street','zip','city','reg_number','vat_id','ceo','phone','email','issues'])
        for r in all_results:
            if r['status'] == 'success':
                res = r['result']
                w.writerow([r['domain'],r['country'],'SUCCESS',r['quality']['grade'],r['quality']['score'],res.get('legal_name','')[:80],res.get('legal_form',''),res.get('street_address','')[:60],res.get('postal_code',''),res.get('city',''),res.get('registration_number',''),res.get('vat_id',''),res.get('ceo_name',''),res.get('phone',''),res.get('email',''),'|'.join(r['quality']['issues'])])
            else:
                w.writerow([r['domain'],r['country'],r['status'].upper(),'F',0,'','','','','','','','','','',r.get('error','')])
    print(f"\n[OK] Results exported to {csv_path}")

if __name__ == '__main__':
    import warnings
    warnings.filterwarnings('ignore')
    asyncio.run(main())
