import os
import sys

# Ensure project directory is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import time
import requests
import db_helper
import scrapers

def main():
    if len(sys.argv) < 3:
        print("Usage: scrape_runner.py <user_chat_id> <message_id>")
        return
        
    user_chat_id = sys.argv[1]
    message_id = sys.argv[2]
    
    token = db_helper.get_setting("telegram_bot_token")
    chat_id = db_helper.get_setting("telegram_chat_id")
    
    if not token or not chat_id:
        return
        
    sources = db_helper.get_sources()
    total_sources = len(sources)
    
    results_summary = []
    new_jobs_total = 0
    
    edit_url = f"https://api.telegram.org/bot{token}/editMessageText"
    
    def update_progress(index, current_source_name):
        progress = int((index / total_sources) * 100)
        filled = int(progress / 10)
        bar = "▓" * filled + "░" * (10 - filled)
        
        text = (
            f"🔄 <b>Sedang Memindai Lowongan Pelaut...</b>\n\n"
            f"<code>[{bar}] {progress}% ({index}/{total_sources})</code>\n"
            f"Memindai: <b>{current_source_name}</b>...\n\n"
            f"<i>Proses pemindaian dilakukan 1 per 1 agar tidak bertabrakan. Mohon tunggu sekitar 1 menit...</i>"
        )
        
        payload = {
            "chat_id": user_chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": "HTML"
        }
        try:
            requests.post(edit_url, json=payload, timeout=5)
        except Exception as e:
            print(f"Error updating progress: {e}")

    for idx, src in enumerate(sources):
        update_progress(idx, src["name"])
        
        # Scrape source
        jobs = []
        try:
            if src["type"] == "built-in":
                if src["name"] == "Crewell":
                    jobs = scrapers.scrape_crewell()
                elif src["name"] == "JobMarineMan":
                    # Skip for now
                    pass
                else:
                    jobs = scrapers.scrape_generic(src["url"])
            elif src["type"] == "rss":
                jobs = scrapers.scrape_rss(src["url"])
            else:
                jobs = scrapers.scrape_generic(src["url"])
        except Exception as e:
            print(f"Error scraping {src['name']}: {e}")
            
        new_jobs_from_source = 0
        for job in reversed(jobs):
            job_id = job["id"]
            if not db_helper.is_job_sent(job_id):
                message = (
                    f"🚢 <b>LOWONGAN PELAUT BARU</b>\n\n"
                    f"💼 <b>Posisi:</b> {scrapers.escape_html(job['position'])}\n"
                    f"🛥 <b>Jenis Kapal:</b> {scrapers.escape_html(job['vessel_type'])}\n"
                    f"💵 <b>Gaji:</b> {scrapers.escape_html(job['salary'])}\n"
                    f"📅 <b>Join Date:</b> {scrapers.escape_html(job['join_date'])}\n"
                    f"⏱ <b>Kontrak:</b> {scrapers.escape_html(job['duration'])}\n"
                    f"🏢 <b>Perusahaan:</b> {scrapers.escape_html(job['company'])}\n\n"
                    f"🔗 <a href='{job['link']}'>Detail &amp; Apply Loker</a>"
                )
                try:
                    send_url = f"https://api.telegram.org/bot{token}/sendMessage"
                    res = requests.post(send_url, json={
                        "chat_id": chat_id,
                        "text": message,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True
                    }, timeout=10)
                    if res.json().get("ok"):
                        db_helper.mark_job_as_sent(job_id)
                        new_jobs_from_source += 1
                        time.sleep(1)
                except Exception as e:
                    print(f"Error sending job: {e}")
                    
        # Add to summary if there are jobs
        if len(jobs) > 0:
            results_summary.append(f"• <b>{src['name']}</b>: {len(jobs)} loker ({new_jobs_from_source} baru)")
            new_jobs_total += new_jobs_from_source
            
    # Send final summary
    summary_text = "\n".join(results_summary)
    final_text = (
        f"✅ <b>Pemeriksaan Loker Selesai!</b>\n\n"
        f"📋 <b>Hasil Ringkasan Pemindaian:</b>\n"
        f"{summary_text if summary_text else '• Semua sumber bersih/tidak ada loker baru.'}\n\n"
        f"🎉 <b>Total Loker Baru Terkirim: {new_jobs_total}</b>"
    )
    
    menu_markup = {
        "inline_keyboard": [
            [
                {"text": "⚙️ Atur Interval", "callback_data": "menu_settings"},
                {"text": "📋 Daftar Sumber", "callback_data": "menu_sources"}
            ],
            [
                {"text": "🔄 Cek Loker Sekarang", "callback_data": "menu_scrape"}
            ]
        ]
    }
    
    payload = {
        "chat_id": user_chat_id,
        "message_id": message_id,
        "text": final_text,
        "parse_mode": "HTML",
        "reply_markup": menu_markup
    }
    try:
        requests.post(edit_url, json=payload, timeout=10)
    except Exception as e:
        print(f"Error sending final summary: {e}")
        
    db_helper.set_setting("last_run", int(time.time()))
    db_helper.prune_sent_jobs()

if __name__ == "__main__":
    main()
