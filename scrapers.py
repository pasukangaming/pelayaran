import requests
from bs4 import BeautifulSoup
import urllib.parse
import hashlib
import db_helper

def escape_html(text):
    if not text:
        return ""
    return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def get_html_content(url):
    proxy_url = db_helper.get_setting("google_proxy_url")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    try:
        if proxy_url:
            print(f"Fetching via Google Apps Script Proxy: {url}")
            target_url = f"{proxy_url}?url={urllib.parse.quote(url)}"
            response = requests.get(target_url, timeout=7)
        else:
            print(f"Fetching directly: {url}")
            response = requests.get(url, headers=headers, timeout=5)
            
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def parse_crewell_html(html_text):
    soup = BeautifulSoup(html_text, 'html.parser')
    vacancy_items = soup.find_all(class_='vacancy-item')
    jobs = []
    
    for item in vacancy_items:
        try:
            title_tag = item.find('a', class_='vacancyTitle')
            if not title_tag:
                continue
            
            href = title_tag.get('href', '')
            job_id_match = [s for s in href.split('/') if s]
            if not job_id_match:
                continue
            job_id = f"crewell_{job_id_match[-1]}"
            
            full_text = title_tag.get_text(separator='|', strip=True)
            parts = [p.strip() for p in full_text.split('|') if p.strip()]
            
            position = parts[0] if parts else "Unknown Position"
            vessel_type = "Unknown"
            if len(parts) >= 3 and parts[1].lower() == 'on':
                vessel_type = parts[2]
            elif len(parts) >= 2:
                vessel_type = parts[1]
                
            salary = "Contact Company"
            join_date = "Urgent / TBD"
            duration = "TBD"
            
            info_rows = item.find_all(class_='info-row')
            for row in info_rows:
                coin_icon = row.find(class_='icon-coin')
                calendar_icon = row.find(class_='icon-calendar3')
                busy_icon = row.find(class_='icon-busy')
                
                text_content = " ".join(row.get_text().split())
                
                if coin_icon or 'Salary:' in text_content:
                    salary = text_content.replace('Salary:', '').strip()
                elif calendar_icon or 'Join date:' in text_content:
                    join_date = text_content.replace('Join date:', '').strip()
                elif busy_icon or 'Duration:' in text_content:
                    duration = text_content.replace('Duration:', '').strip()
            
            company_wrapper = item.find(class_='company-wrapper')
            company = "Anonymous / Crewing Agency"
            if company_wrapper:
                a_company = company_wrapper.find('a')
                if a_company:
                    company = a_company.get_text(strip=True)
                    
            link = f"https://crewell.net{href}"
            
            jobs.append({
                "id": job_id,
                "position": position,
                "vessel_type": vessel_type,
                "salary": salary,
                "join_date": join_date,
                "duration": duration,
                "company": company,
                "link": link
            })
        except Exception as ex:
            print(f"Error parsing Crewell vacancy: {ex}")
            
    return jobs

def parse_rss_html(html_text):
    soup = BeautifulSoup(html_text, 'xml')
    items = soup.find_all('item')
    if not items:
        items = soup.find_all('entry')
        
    jobs = []
    for item in items:
        title_tag = item.find('title')
        link_tag = item.find('link')
        
        title = title_tag.get_text(strip=True) if title_tag else "New Vacancy"
        link = ""
        if link_tag:
            link = link_tag.get('href') or link_tag.get_text(strip=True)
        
        if not link:
            continue
            
        job_id = f"rss_{hashlib.md5(link.encode('utf-8')).hexdigest()[:10]}"
        desc_tag = item.find('description') or item.find('summary')
        desc = ""
        if desc_tag:
            desc_soup = BeautifulSoup(desc_tag.get_text(), 'html.parser')
            desc = desc_soup.get_text(separator=' ', strip=True)
            desc = desc[:150] + "..." if len(desc) > 150 else desc
            
        jobs.append({
            "id": job_id,
            "position": title,
            "vessel_type": "Lihat Detail",
            "salary": "Hubungi Perusahaan",
            "join_date": "Lihat Detail",
            "duration": "Sesuai Kontrak",
            "company": desc if desc else "Sumber RSS Eksternal",
            "link": link
        })
    return jobs

def parse_generic_html(html_text, base_url):
    soup = BeautifulSoup(html_text, 'html.parser')
    links = soup.find_all('a')
    jobs = []
    seen_hrefs = set()
    keywords = ['job', 'vacancy', 'loker', 'career', 'detail', 'apply', 'pelaut', 'crew', 'rekrut']
    
    for a in links:
        href = a.get('href', '')
        text = a.get_text(separator=' ', strip=True)
        if not href or len(text) < 5 or len(text) > 100:
            continue
            
        href_lower = href.lower()
        text_lower = text.lower()
        
        is_job = any(kw in href_lower or kw in text_lower for kw in keywords)
        if is_job:
            full_href = urllib.parse.urljoin(base_url, href)
            if not full_href.startswith('http'):
                continue
            if full_href in seen_hrefs:
                continue
            seen_hrefs.add(full_href)
            
            job_id = f"gen_{hashlib.md5(full_href.encode('utf-8')).hexdigest()[:10]}"
            jobs.append({
                "id": job_id,
                "position": text,
                "vessel_type": "Lihat Detail",
                "salary": "Hubungi Perusahaan",
                "join_date": "Lihat Detail",
                "duration": "Sesuai Kontrak",
                "company": urllib.parse.urlparse(base_url).netloc,
                "link": full_href
            })
    return jobs

def scrape_crewell():
    html = get_html_content("https://crewell.net/en/vacancies/")
    return parse_crewell_html(html) if html else []

def scrape_rss(url):
    html = get_html_content(url)
    return parse_rss_html(html) if html else []

def scrape_generic(url):
    html = get_html_content(url)
    return parse_generic_html(html, url) if html else []

def scrape_all_sources_parallel(sources):
    proxy_url = db_helper.get_setting("google_proxy_url")
    urls = [src["url"] for src in sources]
    
    html_mapping = {}
    if proxy_url and len(urls) > 0:
        print(f"Fetching {len(urls)} URLs in parallel via Google Apps Script Proxy...")
        try:
            response = requests.post(proxy_url, json={"urls": urls}, timeout=45)
            response.raise_for_status()
            html_mapping = response.json()
        except Exception as e:
            print(f"Error fetching parallel URLs: {e}")
            html_mapping = {}
            
    all_jobs = []
    for src in sources:
        url = src["url"]
        html_text = html_mapping.get(url)
        
        # Fallback to direct fetch if not returned by parallel call
        if not html_text:
            print(f"Fallback to direct fetch for: {url}")
            html_text = get_html_content(url)
            
        if not html_text or "Error: " in html_text[:15]:
            continue
            
        jobs = []
        try:
            name_lower = src["name"].lower()
            url_lower = url.lower()
            if "crewell" in name_lower or "crewell.net" in url_lower:
                jobs = parse_crewell_html(html_text)
            elif src.get("type") == "rss" or url_lower.endswith("/feed") or url_lower.endswith(".xml") or "/rss" in url_lower:
                jobs = parse_rss_html(html_text)
            else:
                jobs = parse_generic_html(html_text, url)
        except Exception as e:
            print(f"Error parsing source {src['name']}: {e}")
            
        all_jobs.extend(jobs)
        
    return all_jobs

def scrape_single_source(src):
    url = src["url"]
    html_text = get_html_content(url)
    if not html_text or "Error: " in html_text[:15]:
        return []
    try:
        name_lower = src["name"].lower()
        url_lower = url.lower()
        if "crewell" in name_lower or "crewell.net" in url_lower:
            return parse_crewell_html(html_text)
        elif src.get("type") == "rss" or url_lower.endswith("/feed") or url_lower.endswith(".xml") or "/rss" in url_lower:
            return parse_rss_html(html_text)
        else:
            return parse_generic_html(html_text, url)
    except Exception as e:
        print(f"Error parsing source {src['name']}: {e}")
        return []
