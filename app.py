import os
import time
import requests
import json
import urllib.parse
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup

import db_helper
import scrapers

app = Flask(__name__)

# Initialize database on startup
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
PROXY_URL = os.environ.get("GOOGLE_PROXY_URL")
db_helper.init_db(default_token=BOT_TOKEN, default_chat_id=CHAT_ID)
if PROXY_URL:
    db_helper.set_setting("google_proxy_url", PROXY_URL)

# Helper function to get config
def get_bot_credentials():
    token = db_helper.get_setting("telegram_bot_token")
    chat_id = db_helper.get_setting("telegram_chat_id")
    return token, chat_id

def send_telegram_message(token, chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        print(f"Error sending message: {e}")
        return None

def edit_telegram_message(token, chat_id, message_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{token}/editMessageText"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        print(f"Error editing message: {e}")
        return None

def answer_callback_query(token, callback_query_id, text=None):
    url = f"https://api.telegram.org/bot{token}/answerCallbackQuery"
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Error answering callback query: {e}")

# Menu Markups
def get_main_menu_markup():
    return {
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

def get_settings_markup(current_interval):
    intervals = ["1", "3", "6", "12", "24"]
    keyboard = []
    row = []
    for val in intervals:
        text = f"✅ {val} Jam" if str(current_interval) == val else f"{val} Jam"
        row.append({"text": text, "callback_data": f"set_interval:{val}"})
    keyboard.append(row)
    keyboard.append([{"text": "🔙 Kembali ke Menu Utama", "callback_data": "menu_main"}])
    return {"inline_keyboard": keyboard}

def get_sources_markup(sources):
    keyboard = []
    for src in sources:
        if src["type"] != "built-in":
            keyboard.append([
                {"text": f"❌ Hapus {src['name'][:20]}...", "callback_data": f"delete_source:{src['id']}"}
            ])
    keyboard.append([
        {"text": "➕ Tambah Sumber Baru", "callback_data": "menu_add_source"},
        {"text": "🔙 Kembali ke Menu Utama", "callback_data": "menu_main"}
    ])
    return {"inline_keyboard": keyboard}

# Business Logic for Scraper (Used by Cron)
def run_scrape_and_post(manual_trigger=False, user_chat_id=None):
    token, chat_id = get_bot_credentials()
    if not token or not chat_id:
        print("Scraper skipped: Telegram bot token or chat ID is missing.")
        return False, "Kredensial Telegram Bot belum diatur."
        
    interval_hours = int(db_helper.get_setting("interval_hours", 1))
    last_run = int(db_helper.get_setting("last_run", 0))
    current_time = int(time.time())
    
    if not manual_trigger:
        elapsed_hours = (current_time - last_run) / 3600
        if elapsed_hours < interval_hours:
            msg = f"Scraper dilompati. Selisih waktu ({elapsed_hours:.2f} jam) kurang dari interval ({interval_hours} jam)."
            print(msg)
            return False, msg
            
    print("Starting parallel scrape of all sources...")
    sources = db_helper.get_sources()
    
    # Run parallel scrape via Google Apps Script Proxy
    jobs = scrapers.scrape_all_sources_parallel(sources)
    print(f"Parallel scrape returned {len(jobs)} total jobs.")
    
    new_jobs_count = 0
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
            
            success = send_telegram_message(token, chat_id, message)
            if success and success.get("ok"):
                db_helper.mark_job_as_sent(job_id)
                new_jobs_count += 1
                time.sleep(1) # avoid hitting Telegram rate limits
                
    db_helper.set_setting("last_run", current_time)
    db_helper.prune_sent_jobs()
    
    if manual_trigger and user_chat_id:
        send_telegram_message(
            token, 
            user_chat_id, 
            f"✅ <b>Pemeriksaan Loker Selesai!</b>\n\n"
            f"Telah memindai {len(sources)} sumber loker.\n"
            f"Hasil: Menemukan <b>{new_jobs_count} loker baru</b>."
        )
        
    return True, f"Scraping selesai. Menemukan {new_jobs_count} loker baru."

@app.route("/")
def home():
    token, chat_id = get_bot_credentials()
    return jsonify({
        "status": "online",
        "bot_configured": token is not None,
        "chat_id_configured": chat_id is not None,
        "interval_hours": db_helper.get_setting("interval_hours")
    })

@app.route("/run-cron", methods=["GET", "POST"])
def run_cron():
    success, message = run_scrape_and_post(manual_trigger=False)
    return jsonify({"success": success, "message": message})

@app.route("/scrape-step")
def scrape_step():
    index = int(request.args.get("index", 0))
    user_chat_id = request.args.get("user_chat_id")
    message_id = request.args.get("message_id")
    
    token, chat_id = get_bot_credentials()
    if not token or not chat_id:
        return jsonify({"status": "error", "message": "Credentials missing"})
        
    sources = db_helper.get_sources()
    total_sources = len(sources)
    
    # Load state from DB
    try:
        results_summary = json.loads(db_helper.get_setting("scrape_state_results", "[]"))
        new_jobs_total = int(db_helper.get_setting("scrape_state_new_jobs", "0"))
    except Exception:
        results_summary = []
        new_jobs_total = 0
        
    if index >= total_sources:
        # Finished! Send summary
        summary_text = "\n".join(results_summary)
        final_text = (
            f"✅ <b>Pemeriksaan Loker Selesai!</b>\n\n"
            f"📋 <b>Hasil Ringkasan Pemindaian:</b>\n"
            f"{summary_text if summary_text else '• Semua sumber bersih/tidak ada loker baru.'}\n\n"
            f"🎉 <b>Total Loker Baru Terkirim: {new_jobs_total}</b>"
        )
        
        edit_telegram_message(token, user_chat_id, message_id, final_text, get_main_menu_markup())
        db_helper.set_setting("last_run", int(time.time()))
        db_helper.prune_sent_jobs()
        return jsonify({"status": "finished"})
        
    # Update progress in Telegram
    src = sources[index]
    progress = int((index / total_sources) * 100)
    filled = int(progress / 10)
    bar = "▓" * filled + "░" * (10 - filled)
    
    progress_text = (
        f"🔄 <b>Sedang Memindai Lowongan Pelaut...</b>\n\n"
        f"<code>[{bar}] {progress}% ({index}/{total_sources})</code>\n"
        f"Memindai: <b>{src['name']}</b>...\n\n"
        f"<i>Proses pemindaian dilakukan 1 per 1 agar tidak bentrok. Mohon tunggu...</i>"
    )
    edit_telegram_message(token, user_chat_id, message_id, progress_text)
    
    # Scrape the current source
    jobs = []
    try:
        if src["type"] == "built-in":
            if src["name"] == "Crewell":
                jobs = scrapers.scrape_crewell()
            elif src["name"] == "JobMarineMan":
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
            success = send_telegram_message(token, chat_id, message)
            if success and success.get("ok"):
                db_helper.mark_job_as_sent(job_id)
                new_jobs_from_source += 1
                time.sleep(1)
                
    # Update state
    if len(jobs) > 0:
        results_summary.append(f"• <b>{src['name']}</b>: {len(jobs)} loker ({new_jobs_from_source} baru)")
        new_jobs_total += new_jobs_from_source
        db_helper.set_setting("scrape_state_results", json.dumps(results_summary))
        db_helper.set_setting("scrape_state_new_jobs", str(new_jobs_total))
        
    # Trigger next step via HTTP request to ourselves (non-blocking) via Google Apps Script Proxy to bypass PythonAnywhere sandbox blocking
    host = request.host
    if not host:
        host = "amanputradewa.pythonanywhere.com"
        
    target_url = f"https://{host}/scrape-step?index={index+1}&user_chat_id={user_chat_id}&message_id={message_id}"
    proxy_url = db_helper.get_setting("google_proxy_url")
    
    if proxy_url:
        next_url = f"{proxy_url}?url={urllib.parse.quote(target_url)}"
    else:
        next_url = target_url
        
    try:
        requests.get(next_url, timeout=0.5)
    except requests.exceptions.RequestException:
        pass
        
    return jsonify({"status": "in_progress", "index": index})

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    if not data:
        return "Empty request", 400
        
    token, chat_id = get_bot_credentials()
    if not token:
        return "Bot not configured", 200
        
    if "message" in data:
        message_data = data["message"]
        chat = message_data["chat"]
        user_chat_id = chat["id"]
        text = message_data.get("text", "").strip()
        
        if chat["type"] in ["group", "supergroup", "channel"]:
            db_helper.set_setting("telegram_chat_id", user_chat_id)
            token, chat_id = get_bot_credentials()
            
        if text.startswith("/start") or text.startswith("/menu"):
            send_telegram_message(
                token, 
                user_chat_id, 
                "🚢 <b>Menu Pengaturan JobPelayaran Bot</b>\n\nSilakan pilih menu pengaturan bot di bawah ini:", 
                get_main_menu_markup()
            )
            db_helper.set_user_state(user_chat_id, "normal")
            
        elif text == "/id":
            send_telegram_message(token, user_chat_id, f"ID Chat ini adalah: <code>{user_chat_id}</code>")
            
        else:
            state = db_helper.get_user_state(user_chat_id)
            if state == "awaiting_source_url":
                if text.startswith("http://") or text.startswith("https://"):
                    success = db_helper.add_source(name=text, url=text, s_type="rss")
                    if success:
                        send_telegram_message(token, user_chat_id, "✅ Sumber baru berhasil ditambahkan ke database!")
                    else:
                        send_telegram_message(token, user_chat_id, "❌ URL sudah terdaftar di database.")
                else:
                    send_telegram_message(token, user_chat_id, "❌ Format URL tidak valid. Harus diawali dengan http:// atau https://")
                
                db_helper.set_user_state(user_chat_id, "normal")
                send_telegram_message(token, user_chat_id, "Kembali ke Menu Utama:", get_main_menu_markup())
                
    elif "callback_query" in data:
        callback_query = data["callback_query"]
        callback_query_id = callback_query["id"]
        user_chat_id = callback_query["message"]["chat"]["id"]
        message_id = callback_query["message"]["message_id"]
        callback_data = callback_query["data"]
        
        if callback_data == "menu_main":
            answer_callback_query(token, callback_query_id)
            edit_telegram_message(
                token, 
                user_chat_id, 
                message_id, 
                "🚢 <b>Menu Pengaturan JobPelayaran Bot</b>\n\nSilakan pilih menu pengaturan bot di bawah ini:", 
                get_main_menu_markup()
            )
            db_helper.set_user_state(user_chat_id, "normal")
            
        elif callback_data == "menu_settings":
            answer_callback_query(token, callback_query_id)
            current_interval = db_helper.get_setting("interval_hours", 1)
            edit_telegram_message(
                token, 
                user_chat_id, 
                message_id, 
                f"⏱️ <b>Pengaturan Interval Waktu Update</b>\n\n"
                f"Pilih seberapa sering bot akan memposting loker baru jika terdeteksi.\n"
                f"Interval aktif saat ini: <b>{current_interval} Jam</b>", 
                get_settings_markup(current_interval)
            )
            
        elif callback_data.startswith("set_interval:"):
            hours = callback_data.split(":")[-1]
            db_helper.set_setting("interval_hours", hours)
            answer_callback_query(token, callback_query_id, f"Interval diatur ke {hours} jam.")
            edit_telegram_message(
                token, 
                user_chat_id, 
                message_id, 
                f"⏱️ <b>Pengaturan Interval Waktu Update</b>\n\n"
                f"Pilih seberapa sering bot akan memposting loker baru jika terdeteksi.\n"
                f"Interval aktif saat ini: <b>{hours} Jam</b>", 
                get_settings_markup(hours)
            )
            
        elif callback_data == "menu_sources":
            answer_callback_query(token, callback_query_id)
            sources = db_helper.get_sources()
            text_sources = "📋 <b>Daftar Sumber Loker Aktif:</b>\n\n"
            for idx, src in enumerate(sources):
                text_sources += f"{idx+1}. <b>{src['name']}</b> ({src['type']})\nURL: <code>{src['url']}</code>\n\n"
            
            edit_telegram_message(token, user_chat_id, message_id, text_sources, get_sources_markup(sources))
            
        elif callback_data == "menu_add_source":
            answer_callback_query(token, callback_query_id)
            db_helper.set_user_state(user_chat_id, "awaiting_source_url")
            edit_telegram_message(
                token, 
                user_chat_id, 
                message_id, 
                "➕ <b>Tambah Sumber Loker Manual</b>\n\n"
                "Silakan ketik dan kirimkan link URL (RSS Feed XML atau alamat halaman web) yang ingin Anda tambahkan sebagai sumber manual.\n\n"
                "Contoh: <code>https://wintermar.com/careers/rss</code>\n\n"
                "<i>Bot akan menunggu input teks dari Anda...</i>"
            )
            
        elif callback_data.startswith("delete_source:"):
            source_id = callback_data.split(":")[-1]
            deleted = db_helper.delete_source(source_id)
            
            if deleted:
                answer_callback_query(token, callback_query_id, "Sumber manual berhasil dihapus.")
            else:
                answer_callback_query(token, callback_query_id, "Gagal menghapus (Sumber Bawaan tidak bisa dihapus).")
                
            sources = db_helper.get_sources()
            text_sources = "📋 <b>Daftar Sumber Loker Aktif:</b>\n\n"
            for idx, src in enumerate(sources):
                text_sources += f"{idx+1}. <b>{src['name']}</b> ({src['type']})\nURL: <code>{src['url']}</code>\n\n"
            edit_telegram_message(token, user_chat_id, message_id, text_sources, get_sources_markup(sources))
            
        elif callback_data == "menu_scrape":
            answer_callback_query(token, callback_query_id, "Scraping dimulai...")
            edit_telegram_message(
                token, 
                user_chat_id, 
                message_id, 
                "🔄 <b>Sedang memulai pemeriksaan lowongan...</b>\n\nMenghubungkan ke server..."
            )
            
            # Reset state in DB
            db_helper.set_setting("scrape_state_results", "[]")
            db_helper.set_setting("scrape_state_new_jobs", "0")
            
            # Trigger first step (index 0) via Google Apps Script Proxy to bypass PythonAnywhere sandbox blocking
            host = request.host
            if not host:
                host = "amanputradewa.pythonanywhere.com"
                
            target_url = f"https://{host}/scrape-step?index=0&user_chat_id={user_chat_id}&message_id={message_id}"
            proxy_url = db_helper.get_setting("google_proxy_url")
            
            if proxy_url:
                next_url = f"{proxy_url}?url={urllib.parse.quote(target_url)}"
            else:
                next_url = target_url
                
            try:
                requests.get(next_url, timeout=0.5)
            except requests.exceptions.RequestException:
                pass
            
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
