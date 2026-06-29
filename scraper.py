import os
import json
import requests
from bs4 import BeautifulSoup

def escape_html(text):
    if not text:
        return ""
    return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def scrape_crewell():
    url = "https://crewell.net/en/vacancies/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    
    print("Fetching vacancies from Crewell...")
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except Exception as e:
        print(f"Error fetching vacancies: {e}")
        return []
        
    soup = BeautifulSoup(response.text, 'html.parser')
    vacancy_items = soup.find_all(class_='vacancy-item')
    
    print(f"Found {len(vacancy_items)} vacancy items in HTML.")
    jobs = []
    
    for item in vacancy_items:
        try:
            # Title & Vessel Type
            title_tag = item.find('a', class_='vacancyTitle')
            if not title_tag:
                continue
            
            href = title_tag.get('href', '')
            job_id_match = [s for s in href.split('/') if s]
            if not job_id_match:
                continue
            job_id = job_id_match[-1]
            
            # Extract position and vessel type
            full_text = title_tag.get_text(separator='|', strip=True)
            parts = [p.strip() for p in full_text.split('|') if p.strip()]
            
            position = parts[0] if parts else "Unknown Position"
            vessel_type = "Unknown"
            if len(parts) >= 3 and parts[1].lower() == 'on':
                vessel_type = parts[2]
            elif len(parts) >= 2:
                vessel_type = parts[1]
                
            # Default values
            salary = "Contact Company"
            join_date = "Urgent / TBD"
            duration = "TBD"
            
            # Find all info-rows in the card
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
            
            # Company name
            company_wrapper = item.find(class_='company-wrapper')
            company = "Anonymous / Crewing Agency"
            if company_wrapper:
                a_company = company_wrapper.find('a')
                if a_company:
                    company = a_company.get_text(strip=True)
                    
            # Link
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
            print(f"Error parsing vacancy card: {ex}")
            
    return jobs

def send_telegram(token, chat_id, message):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        response_json = response.json()
        if not response_json.get("ok"):
            print(f"Telegram API error: {response_json.get('description')}")
            return False
        return True
    except Exception as e:
        print(f"Error sending Telegram message: {e}")
        return False

def main():
    # Load environment variables
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not bot_token or not chat_id:
        print("Error: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables must be set.")
        return
    
    # Path for state file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    state_file = os.path.join(script_dir, "last_jobs.json")
    
    # Load already sent jobs
    if os.path.exists(state_file):
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                sent_jobs = json.load(f)
        except Exception as e:
            print(f"Error loading state file: {e}")
            sent_jobs = []
    else:
        sent_jobs = []
        
    print(f"Loaded {len(sent_jobs)} historical job IDs.")
    
    # Scrape new jobs
    all_jobs = scrape_crewell()
    print(f"Scraped {len(all_jobs)} jobs from web.")
    
    new_jobs_found = False
    
    # Process from oldest to newest (reverse list) to send in order
    for job in reversed(all_jobs):
        job_id = job["id"]
        if job_id not in sent_jobs:
            print(f"New job found: ID {job_id} - {job['position']} on {job['vessel_type']}")
            
            # Format message
            message = (
                f"🚢 <b>LOWONGAN PELAUT BARU</b>\n\n"
                f"💼 <b>Posisi:</b> {escape_html(job['position'])}\n"
                f"🛥 <b>Jenis Kapal:</b> {escape_html(job['vessel_type'])}\n"
                f"💵 <b>Gaji:</b> {escape_html(job['salary'])}\n"
                f"📅 <b>Join Date:</b> {escape_html(job['join_date'])}\n"
                f"⏱ <b>Kontrak:</b> {escape_html(job['duration'])}\n"
                f"🏢 <b>Perusahaan:</b> {escape_html(job['company'])}\n\n"
                f"🔗 <a href='{job['link']}'>Detail &amp; Apply Loker</a>"
            )
            
            # Send message
            success = send_telegram(bot_token, chat_id, message)
            if success:
                sent_jobs.append(job_id)
                new_jobs_found = True
                
    # Save state if new jobs were successfully processed
    if new_jobs_found:
        # Keep only the last 500 job IDs to avoid the state file growing infinitely
        if len(sent_jobs) > 500:
            sent_jobs = sent_jobs[-500:]
            
        try:
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(sent_jobs, f, indent=4, ensure_ascii=False)
            print("Successfully updated last_jobs.json with new job IDs.")
        except Exception as e:
            print(f"Error saving state file: {e}")
    else:
        print("No new jobs to post.")

if __name__ == "__main__":
    main()
