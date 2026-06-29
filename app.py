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
def categorize_job(position):
    pos_lower = position.lower()
    deck_kws = ['master', 'captain', 'mate', 'officer', 'deck', 'bosun', 'ab ', 'os ', 'cadet', 'helmsman', 'jurumudi', 'kelasi']
    engine_kws = ['engineer', 'engine', 'oiler', 'wiper', 'fitter', 'electrician', 'motorman']
    galley_kws = ['cook', 'steward', 'messboy', 'waiter', 'chef', 'galley', 'laundry', 'utility']
    landbase_kws = ['housekeeping', 'receptionist', 'front office', 'spa ', 'hotel darat', 'butler', 'cleaner', 'landbase']
    
    if any(kw in pos_lower for kw in deck_kws):
        return "deck"
    elif any(kw in pos_lower for kw in engine_kws):
        return "engine"
    elif any(kw in pos_lower for kw in galley_kws):
        return "galley"
    elif any(kw in pos_lower for kw in landbase_kws):
        return "landbase"
    return "other"
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
                {"text": "💼 Lowongan Per Jabatan", "callback_data": "menu_jobs"}
            ],
            [
                {"text": "🏢 Daftar Agency Resmi", "callback_data": "menu_agencies"},
                {"text": "🔔 Langganan Loker", "callback_data": "menu_subscribe"}
            ],
            [
                {"text": "📄 Tips & Template CV", "callback_data": "menu_cv"},
                {"text": "📊 Statistik Bot", "callback_data": "menu_stats"}
            ],
            [
                {"text": "⚙️ Atur Interval", "callback_data": "menu_settings"},
                {"text": "🔄 Cek Loker Sekarang", "callback_data": "menu_scrape"}
            ],
            [
                {"text": "📢 Bagikan Bot", "callback_data": "menu_share"}
            ]
        ]
    }

def get_cv_menu_markup():
    return {
        "inline_keyboard": [
            [
                {"text": "🚢 Format Sea Service (Pelaut)", "callback_data": "cv_format:pelaut"},
                {"text": "🏨 Format Resume (Hotel)", "callback_data": "cv_format:hotel"}
            ],
            [
                {"text": "🔙 Kembali ke Menu Utama", "callback_data": "menu_main"}
            ]
        ]
    }

def get_subscribe_markup(current_sub):
    keyboard = [
        [
            {"text": "🚢 Deck" + (" (Aktif)" if current_sub == "deck" else ""), "callback_data": "sub:deck"},
            {"text": "🔧 Engine" + (" (Aktif)" if current_sub == "engine" else ""), "callback_data": "sub:engine"}
        ],
        [
            {"text": "🍽 Galley" + (" (Aktif)" if current_sub == "galley" else ""), "callback_data": "sub:galley"},
            {"text": "🏨 Hotel" + (" (Aktif)" if current_sub == "landbase" else ""), "callback_data": "sub:landbase"}
        ]
    ]
    if current_sub:
        keyboard.append([{"text": "🔕 Berhenti Berlangganan", "callback_data": "sub:unsubscribe"}])
    keyboard.append([{"text": "🔙 Kembali ke Menu Utama", "callback_data": "menu_main"}])
    return {"inline_keyboard": keyboard}

def get_jobs_menu_markup():
    return {
        "inline_keyboard": [
            [
                {"text": "🚢 Deck (Perwira & Rating)", "callback_data": "list_jobs:deck"},
                {"text": "🔧 Engine (Engineer & Rating)", "callback_data": "list_jobs:engine"}
            ],
            [
                {"text": "🍽 Steward & Galley", "callback_data": "list_jobs:galley"},
                {"text": "🏨 Landbase Hotel", "callback_data": "list_jobs:landbase"}
            ],
            [
                {"text": "🔍 Cari Posisi / Ketik Bebas", "callback_data": "menu_search_jobs"}
            ],
            [
                {"text": "🔙 Kembali ke Menu Utama", "callback_data": "menu_main"}
            ]
        ]
    }

def get_agencies_menu_markup():
    return {
        "inline_keyboard": [
            [
                {"text": "🚢 Cruise Line (SIUPPAK/P3MI)", "callback_data": "list_agencies:cruise"},
                {"text": "🏨 Landbase Hotel (P3MI)", "callback_data": "list_agencies:landbase"}
            ],
            [
                {"text": "📍 Cari Berdasarkan Lokasi", "callback_data": "menu_agencies_location"}
            ],
            [
                {"text": "➕ Tambah Agency", "callback_data": "menu_add_agency"},
                {"text": "❌ Hapus Agency", "callback_data": "menu_delete_agency_list"}
            ],
            [
                {"text": "🔙 Kembali ke Menu Utama", "callback_data": "menu_main"}
            ]
        ]
    }

def get_add_agency_options_markup():
    return {
        "inline_keyboard": [
            [
                {"text": "✍️ Input Manual", "callback_data": "menu_add_agency_manual"},
                {"text": "🔄 Update Otomatis", "callback_data": "menu_add_agency_auto"}
            ],
            [
                {"text": "🔙 Batal", "callback_data": "menu_agencies"}
            ]
        ]
    }

def get_agencies_location_markup():
    return {
        "inline_keyboard": [
            [
                {"text": "📍 Jakarta", "callback_data": "list_agencies_loc:Jakarta"},
                {"text": "📍 Bali", "callback_data": "list_agencies_loc:Bali"}
            ],
            [
                {"text": "📍 Surabaya", "callback_data": "list_agencies_loc:Surabaya"},
                {"text": "📍 Lainnya", "callback_data": "list_agencies_loc:Lainnya"}
            ],
            [
                {"text": "🔙 Kembali", "callback_data": "menu_agencies"}
            ]
        ]
    }

def get_delete_agencies_markup(agencies):
    keyboard = []
    for ag in agencies:
        keyboard.append([
            {"text": f"❌ Hapus {ag['name'][:25]}...", "callback_data": f"delete_agency:{ag['id']}"}
        ])
    keyboard.append([{"text": "🔙 Kembali", "callback_data": "menu_agencies"}])
    return {"inline_keyboard": keyboard}

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
            
    print("Starting parallel scrape of all official agencies...")
    agencies = db_helper.get_agencies()
    sources = [
        {"name": ag["name"], "url": ag["website"], "type": "web"}
        for ag in agencies
        if ag["website"] and (ag["website"].startswith("http://") or ag["website"].startswith("https://"))
    ]
    
    # Run parallel scrape via Google Apps Script Proxy
    jobs = scrapers.scrape_all_sources_parallel(sources)
    print(f"Parallel scrape returned {len(jobs)} total jobs from {len(sources)} agencies.")
    
    new_jobs_count = 0
    for job in reversed(jobs):
        job_id = job["id"]
        db_helper.save_job(job)
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
                
                # Send private alerts to category subscribers
                job_cat = categorize_job(job["position"])
                if job_cat != "other":
                    subs = db_helper.get_subscribers_by_category(job_cat)
                    alert_msg = (
                        f"🔔 <b>[ALERT LANGGANAN] Loker Baru Sesuai Departemen Anda!</b>\n\n"
                        f"💼 <b>Posisi:</b> {scrapers.escape_html(job['position'])}\n"
                        f"🏢 <b>Perusahaan:</b> {scrapers.escape_html(job['company'])}\n"
                        f"💵 <b>Gaji:</b> {scrapers.escape_html(job['salary'])}\n"
                        f"🔗 <a href='{job['link']}'>Detail &amp; Apply Loker</a>"
                    )
                    for sub_chat_id in subs:
                        send_telegram_message(token, sub_chat_id, alert_msg)
                        
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
        
    agencies = db_helper.get_agencies()
    sources = [
        {"name": ag["name"], "url": ag["website"], "type": "web"}
        for ag in agencies
        if ag["website"] and (ag["website"].startswith("http://") or ag["website"].startswith("https://"))
    ]
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
    
    # Secure try block to ensure failure does not stop the step progression
    try:
        jobs = []
        try:
            jobs = scrapers.scrape_generic(src["url"])
        except Exception as e:
            print(f"Error scraping {src['name']}: {e}")
            
        new_jobs_from_source = 0
        for job in reversed(jobs):
            try:
                job_id = job["id"]
                db_helper.save_job(job)
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
                        
                        # Send private alerts to category subscribers
                        job_cat = categorize_job(job["position"])
                        if job_cat != "other":
                            subs = db_helper.get_subscribers_by_category(job_cat)
                            alert_msg = (
                                f"🔔 <b>[ALERT LANGGANAN] Loker Baru Sesuai Departemen Anda!</b>\n\n"
                                f"💼 <b>Posisi:</b> {scrapers.escape_html(job['position'])}\n"
                                f"🏢 <b>Perusahaan:</b> {scrapers.escape_html(job['company'])}\n"
                                f"💵 <b>Gaji:</b> {scrapers.escape_html(job['salary'])}\n"
                                f"🔗 <a href='{job['link']}'>Detail &amp; Apply Loker</a>"
                            )
                            for sub_chat_id in subs:
                                send_telegram_message(token, sub_chat_id, alert_msg)
                                
                        time.sleep(1)
            except Exception as inner_e:
                print(f"Error processing job: {inner_e}")
                
        # Update state
        if len(jobs) > 0 or new_jobs_from_source > 0:
            results_summary.append(f"• <b>{src['name']}</b>: {len(jobs)} loker ({new_jobs_from_source} baru)")
            new_jobs_total += new_jobs_from_source
            db_helper.set_setting("scrape_state_results", json.dumps(results_summary))
            db_helper.set_setting("scrape_state_new_jobs", str(new_jobs_total))
            
    except Exception as outer_e:
        print(f"Outer loop error on {src['name']}: {outer_e}")
        
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
            if state == "awaiting_agency_data":
                parts = [p.strip() for p in text.split("|")]
                if len(parts) >= 3:
                    name = parts[0]
                    license_no = parts[1]
                    raw_type = parts[2].lower()
                    
                    agency_type = "Kapal Pesiar"
                    if "landbase" in raw_type or "hotel" in raw_type or "darat" in raw_type:
                        agency_type = "Landbase (Hotel Darat)"
                        
                    address = parts[3] if len(parts) > 3 else ""
                    contact = parts[4] if len(parts) > 4 else ""
                    website = parts[5] if len(parts) > 5 else ""
                    
                    success = db_helper.add_agency(name, license_no, agency_type, address, contact, website)
                    if success:
                        send_telegram_message(token, user_chat_id, f"✅ Agency <b>{name}</b> berhasil ditambahkan ke database!")
                    else:
                        send_telegram_message(token, user_chat_id, "❌ Gagal menambahkan. Agency mungkin sudah terdaftar.")
                else:
                    send_telegram_message(token, user_chat_id, "❌ Format tidak valid. Pastikan menyertakan minimal: Nama | Izin | Kategori")
                
            elif state == "awaiting_job_search":
                query = text.strip()
                jobs = db_helper.search_jobs(query)
                
                if jobs:
                    text_res = f"🔍 <b>Hasil Pencarian Lowongan: '{query}'</b>\n\n"
                    for idx, j in enumerate(jobs):
                        text_res += f"{idx+1}. <b>{j['position']}</b>\n"
                        text_res += f"   🏢 {j['company']} | 🛥 {j['vessel_type']}\n"
                        text_res += f"   💵 Gaji: {j['salary']} | 📅 Join: {j['join_date']}\n"
                        text_res += f"   🔗 <a href='{j['link']}'>Detail Loker</a>\n\n"
                else:
                    text_res = f"❌ Tidak ditemukan lowongan dengan kata kunci: <b>{query}</b>.\n\nCoba cari kata kunci lainnya (misal: AB, Fitter, Waiter)."
                    
                db_helper.set_user_state(user_chat_id, "normal")
                send_telegram_message(token, user_chat_id, text_res, get_main_menu_markup())
                
            else:
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
            
        elif callback_data == "menu_jobs":
            answer_callback_query(token, callback_query_id)
            edit_telegram_message(
                token, 
                user_chat_id, 
                message_id, 
                "💼 <b>Lowongan Per Jabatan / Pencarian Loker</b>\n\n"
                "Pilih kategori jabatan di bawah ini atau cari posisi secara manual menggunakan kata kunci bebas:", 
                get_jobs_menu_markup()
            )
            
        elif callback_data.startswith("list_jobs:"):
            category = callback_data.split(":")[-1]
            answer_callback_query(token, callback_query_id)
            
            keywords_map = {
                "deck": ['master', 'captain', 'mate', 'officer', 'deck', 'bosun', 'ab ', 'os ', 'cadet', 'Helmsman', 'jurumudi', 'kelasi'],
                "engine": ['engineer', 'engine', 'oiler', 'wiper', 'fitter', 'electrician', 'motorman'],
                "galley": ['cook', 'steward', 'messboy', 'waiter', 'chef', 'galley', 'laundry', 'utility'],
                "landbase": ['housekeeping', 'receptionist', 'front office', 'spa ', 'hotel darat', 'butler', 'cleaner', 'landbase']
            }
            
            keywords = keywords_map.get(category, [])
            jobs = db_helper.get_jobs_by_keywords(keywords)
            
            category_titles = {
                "deck": "🚢 Deck (Perwira & Rating)",
                "engine": "🔧 Engine (Engineer & Rating)",
                "galley": "🍽 Steward & Galley",
                "landbase": "🏨 Landbase Hotel"
            }
            
            title = category_titles.get(category, "Lowongan Kerja")
            text = f"💼 <b>Daftar Lowongan - {title}</b>\n\n"
            
            if jobs:
                for idx, j in enumerate(jobs):
                    text += f"{idx+1}. <b>{j['position']}</b>\n"
                    text += f"   🏢 {j['company']} | 🛥 {j['vessel_type']}\n"
                    text += f"   💵 Gaji: {j['salary']} | 📅 Join: {j['join_date']}\n"
                    text += f"   🔗 <a href='{j['link']}'>Detail Loker</a>\n\n"
            else:
                text += "❌ Saat ini belum ada lowongan aktif di database untuk kategori ini.\n\n<i>Silakan lakukan scrape data terbaru menggunakan tombol 'Cek Loker Sekarang'.</i>"
                
            markup = {
                "inline_keyboard": [
                    [{"text": "🔙 Kembali", "callback_data": "menu_jobs"}]
                ]
            }
            edit_telegram_message(token, user_chat_id, message_id, text, markup)
            
        elif callback_data == "menu_search_jobs":
            answer_callback_query(token, callback_query_id)
            db_helper.set_user_state(user_chat_id, "awaiting_job_search")
            edit_telegram_message(
                token, 
                user_chat_id, 
                message_id, 
                "🔍 <b>Cari Lowongan Bebas</b>\n\n"
                "Silakan ketik nama jabatan atau posisi yang ingin Anda cari (misal: <code>Fitter</code>, <code>AB</code>, <code>Waiter</code>, <code>Housekeeping</code>).\n\n"
                "<i>Bot akan menunggu input teks dari Anda...</i>",
                {"inline_keyboard": [[{"text": "🔙 Batal", "callback_data": "menu_jobs"}]]}
            )
            
        elif callback_data == "menu_agencies":
            answer_callback_query(token, callback_query_id)
            edit_telegram_message(
                token, 
                user_chat_id, 
                message_id, 
                "🏢 <b>Daftar Agency Resmi Indonesia (P3MI / SIUPPAK)</b>\n\n"
                "Pilih kategori agency yang ingin Anda lihat detail alamat dan kontaknya:", 
                get_agencies_menu_markup()
            )
            
        elif callback_data.startswith("list_agencies:"):
            category = callback_data.split(":")[-1]
            answer_callback_query(token, callback_query_id)
            
            agencies = db_helper.get_agencies_by_type(category)
            
            category_title = "🚢 Cruise Line (SIUPPAK/P3MI)" if category == "cruise" else "🏨 Landbase Hotel (P3MI)"
            text = f"🏢 <b>Daftar Agency Resmi - {category_title}</b>\n\n"
            text += "<i>Berikut daftar agensi berizin resmi di Indonesia (aktif di SISKOP2MI/Kemenhub). Ketuk alamat/kontak untuk menyalin.</i>\n\n"
            
            for idx, ag in enumerate(agencies):
                text += f"{idx+1}. <b>{ag['name']}</b>\n"
                text += f"   📄 <b>Izin:</b> {ag['license_no']}\n"
                if ag['address']:
                    text += f"   📍 <b>Alamat:</b> <code>{ag['address']}</code>\n"
                if ag['contact']:
                    text += f"   📞 <b>Kontak:</b> <code>{ag['contact']}</code>\n"
                if ag['website']:
                    text += f"   🌐 <b>Web:</b> <a href='{ag['website']}'>{ag['name']}</a>\n"
                if ag.get('created_at'):
                    text += f"   📅 <b>Terdaftar:</b> <code>{ag['created_at']}</code>\n"
                text += "\n"
                
            markup = {
                "inline_keyboard": [
                    [{"text": "🔙 Kembali", "callback_data": "menu_agencies"}]
                ]
            }
            edit_telegram_message(token, user_chat_id, message_id, text, markup)
            
        elif callback_data == "menu_add_agency":
            answer_callback_query(token, callback_query_id)
            edit_telegram_message(
                token, 
                user_chat_id, 
                message_id, 
                "➕ <b>Tambah Agency Resmi Baru</b>\n\n"
                "Pilih cara untuk menambahkan agency resmi ke dalam database bot:\n\n"
                "• <b>✍️ Input Manual:</b> Menambahkan secara mandiri dengan mengetik data agensi.\n"
                "• <b>🔄 Update Otomatis:</b> Menyinkronkan otomatis semua daftar agensi resmi (P3MI / SIUPPAK) yang aktif dan terdaftar langsung ke database.",
                get_add_agency_options_markup()
            )
            
        elif callback_data == "menu_add_agency_manual":
            answer_callback_query(token, callback_query_id)
            db_helper.set_user_state(user_chat_id, "awaiting_agency_data")
            edit_telegram_message(
                token, 
                user_chat_id, 
                message_id, 
                "✍️ <b>Input Manual Agency Resmi Baru</b>\n\n"
                "Silakan kirimkan data agency baru dengan format berikut (pisahkan dengan karakter |):\n"
                "<code>Nama Agency | Nomor Izin | Kategori (Kapal Pesiar atau Landbase) | Alamat | Kontak | Website</code>\n\n"
                "Contoh:\n"
                "<code>PT Nusantara Raya | P3MI No. 99/2026 | Landbase | Jl. Sudirman No. 10 | +628123456 | https://nusantararaya.com</code>\n\n"
                "<i>Bot akan menunggu input teks dari Anda...</i>",
                {"inline_keyboard": [[{"text": "🔙 Batal", "callback_data": "menu_add_agency"}]]}
            )
            
        elif callback_data == "menu_add_agency_auto":
            answer_callback_query(token, callback_query_id, "Memulai sinkronisasi...")
            added_count = db_helper.sync_default_agencies()
            
            text_res = (
                f"🔄 <b>Sinkronisasi Otomatis Selesai!</b>\n\n"
                f"Database bot telah diselaraskan dengan daftar agensi resmi berizin aktif di Kemenhub & BP2MI.\n\n"
                f"• Agensi baru berhasil ditambahkan: <b>{added_count} agensi</b>\n\n"
                f"<i>Semua agensi resmi kini aktif dan siap di-scrape!</i>"
            )
            
            markup = {
                "inline_keyboard": [
                    [{"text": "🔙 Kembali ke Menu Agency", "callback_data": "menu_agencies"}]
                ]
            }
            edit_telegram_message(token, user_chat_id, message_id, text_res, markup)
            
        elif callback_data == "menu_delete_agency_list":
            answer_callback_query(token, callback_query_id)
            agencies = db_helper.get_agencies()
            text_del = "❌ <b>Hapus Agency Dari Direktori</b>\n\nPilih agency di bawah ini yang ingin dihapus dari daftar bot:"
            edit_telegram_message(token, user_chat_id, message_id, text_del, get_delete_agencies_markup(agencies))
            
        elif callback_data.startswith("delete_agency:"):
            agency_id = callback_data.split(":")[-1]
            deleted = db_helper.delete_agency(agency_id)
            if deleted:
                answer_callback_query(token, callback_query_id, "Agency berhasil dihapus.")
            else:
                answer_callback_query(token, callback_query_id, "Gagal menghapus agency.")
                
            agencies = db_helper.get_agencies()
            text_del = "❌ <b>Hapus Agency Dari Direktori</b>\n\nPilih agency di bawah ini yang ingin dihapus dari daftar bot:"
            edit_telegram_message(token, user_chat_id, message_id, text_del, get_delete_agencies_markup(agencies))
            
        elif callback_data == "menu_agencies_location":
            answer_callback_query(token, callback_query_id)
            edit_telegram_message(
                token, 
                user_chat_id, 
                message_id, 
                "📍 <b>Cari Agency Berdasarkan Wilayah Kantor</b>\n\nPilih wilayah lokasi kantor agency yang ingin Anda tampilkan:",
                get_agencies_location_markup()
            )
            
        elif callback_data.startswith("list_agencies_loc:"):
            loc = callback_data.split(":")[-1]
            answer_callback_query(token, callback_query_id)
            
            if loc == "Lainnya":
                all_agencies = db_helper.get_agencies()
                agencies = [a for a in all_agencies if "jakarta" not in a["address"].lower() and "bali" not in a["address"].lower() and "surabaya" not in a["address"].lower()]
            else:
                agencies = db_helper.get_agencies_by_location(loc)
                
            text = f"📍 <b>Daftar Agency Resmi di Wilayah: {loc}</b>\n\n"
            text += "<i>Ketuk alamat/kontak untuk menyalin.</i>\n\n"
            
            if agencies:
                for idx, ag in enumerate(agencies):
                    text += f"{idx+1}. <b>{ag['name']}</b>\n"
                    text += f"   📄 <b>Izin:</b> {ag['license_no']}\n"
                    if ag['address']:
                        text += f"   📍 <b>Alamat:</b> <code>{ag['address']}</code>\n"
                    if ag['contact']:
                        text += f"   📞 <b>Kontak:</b> <code>{ag['contact']}</code>\n"
                    if ag['website']:
                        text += f"   🌐 <b>Web:</b> <a href='{ag['website']}'>{ag['name']}</a>\n"
                    if ag.get('created_at'):
                        text += f"   📅 <b>Terdaftar:</b> <code>{ag['created_at']}</code>\n"
                    text += "\n"
            else:
                text += "❌ Belum ada agency terdaftar di wilayah ini."
                
            markup = {
                "inline_keyboard": [
                    [{"text": "🔙 Kembali", "callback_data": "menu_agencies_location"}]
                ]
            }
            edit_telegram_message(token, user_chat_id, message_id, text, markup)
            
        elif callback_data == "menu_subscribe":
            answer_callback_query(token, callback_query_id)
            current_sub = db_helper.get_user_subscription(user_chat_id)
            
            cat_titles = {
                "deck": "🚢 Deck (Perwira & Rating)",
                "engine": "🔧 Engine (Engineer & Rating)",
                "galley": "🍽 Galley/Steward",
                "landbase": "🏨 Hotel Darat Internasional"
            }
            
            sub_title = cat_titles.get(current_sub, "Belum Berlangganan")
            text = (
                f"🔔 <b>Personal Job Alerts (Langganan Loker)</b>\n\n"
                f"Dapatkan notifikasi pesan pribadi (japri) secara otomatis dari bot ketika ada lowongan baru sesuai minat jabatan Anda!\n\n"
                f"Status Langganan Aktif: <b>{sub_title}</b>\n\n"
                f"Silakan klik departemen di bawah ini untuk mengaktifkan atau mengganti langganan Anda:"
            )
            edit_telegram_message(token, user_chat_id, message_id, text, get_subscribe_markup(current_sub))
            
        elif callback_data.startswith("sub:"):
            sub_action = callback_data.split(":")[-1]
            if sub_action == "unsubscribe":
                db_helper.unsubscribe_user(user_chat_id)
                answer_callback_query(token, callback_query_id, "Berhasil berhenti berlangganan.")
            else:
                db_helper.subscribe_user(user_chat_id, sub_action)
                cat_titles = {
                    "deck": "Deck Department",
                    "engine": "Engine Department",
                    "galley": "Galley/Steward",
                    "landbase": "Hotel Darat"
                }
                answer_callback_query(token, callback_query_id, f"Langganan aktif untuk {cat_titles[sub_action]}!")
                
            current_sub = db_helper.get_user_subscription(user_chat_id)
            cat_titles = {
                "deck": "🚢 Deck (Perwira & Rating)",
                "engine": "🔧 Engine (Engineer & Rating)",
                "galley": "🍽 Galley/Steward",
                "landbase": "🏨 Hotel Darat Internasional"
            }
            sub_title = cat_titles.get(current_sub, "Belum Berlangganan")
            text = (
                f"🔔 <b>Personal Job Alerts (Langganan Loker)</b>\n\n"
                f"Dapatkan notifikasi pesan pribadi (japri) secara otomatis dari bot ketika ada lowongan baru sesuai minat jabatan Anda!\n\n"
                f"Status Langganan Aktif: <b>{sub_title}</b>\n\n"
                f"Silakan klik departemen di bawah ini untuk mengaktifkan atau mengganti langganan Anda:"
            )
            edit_telegram_message(token, user_chat_id, message_id, text, get_subscribe_markup(current_sub))
            
        elif callback_data == "menu_share":
            answer_callback_query(token, callback_query_id)
            text_share = (
                f"📢 <b>Bagikan Bot Lowongan Pelayaran</b>\n\n"
                f"Bantu teman-teman pelaut dan pekerja hotel lainnya menemukan pekerjaan resmi dan aman dari agensi berizin Kemenhub & BP2MI!\n\n"
                f"Klik tombol di bawah ini untuk membagikan bot langsung ke chat/grup Telegram teman Anda:"
            )
            
            share_text = "Yuk cari loker pelaut & hotel internasional resmi P3MI/SIUPPAK di bot ini! Lengkap dengan cek direktori agensi resmi dan notifikasi langsung!"
            share_url = f"https://t.me/share/url?url=https://t.me/jobpelayaran_bot&text={urllib.parse.quote(share_text)}"
            
            markup = {
                "inline_keyboard": [
                    [{"text": "📢 Bagikan ke Chat/Grup", "url": share_url}],
                    [{"text": "🔙 Kembali", "callback_data": "menu_main"}]
                ]
            }
            edit_telegram_message(token, user_chat_id, message_id, text_share, markup)
        elif callback_data == "menu_cv":
            answer_callback_query(token, callback_query_id)
            text_cv = (
                "📄 <b>Format CV & Resume Karir Internasional</b>\n\n"
                "Pilih format CV di bawah ini untuk melihat struktur penulisan CV berstandar internasional yang disukai oleh agen kapal pesiar dan hotel luar negeri. "
                "Anda bisa langsung menyalin teksnya untuk diisi:"
            )
            edit_telegram_message(token, user_chat_id, message_id, text_cv, get_cv_menu_markup())
            
        elif callback_data.startswith("cv_format:"):
            cv_type = callback_data.split(":")[-1]
            answer_callback_query(token, callback_query_id)
            
            if cv_type == "pelaut":
                text = (
                    "📄 <b>Format CV Sea Service Record (Masa Layar)</b>\n\n"
                    "Ketuk kolom teks di bawah ini untuk langsung menyalin formatnya, lalu isi/edit sesuai pengalaman Anda:\n\n"
                    "<code>===================================\n"
                    "SEA SERVICE RECORD (Masa Layar)\n"
                    "===================================\n"
                    "1. Vessel Name    : [Nama Kapal]\n"
                    "   Vessel Type    : [Jenis Kapal, misal: Container, Tanker, Cruise]\n"
                    "   G.R.T.         : [Gross Tonnage, misal: 2500 GRT]\n"
                    "   Engine Type    : [Tipe Mesin, misal: Wartsila 8L32]\n"
                    "   B.H.P / K.W    : [Power Mesin, misal: 4000 BHP]\n"
                    "   Rank/Position  : [Jabatan, misal: Third Engineer]\n"
                    "   Sign-On Date   : [Tanggal Naik Kapal]\n"
                    "   Sign-Off Date  : [Tanggal Turun Kapal]\n"
                    "   Company/Owner  : [Nama Agency/Perusahaan]\n"
                    "   Trading Area   : [Wilayah Pelayaran, misal: Worldwide]\n\n"
                    "2. Vessel Name    : ...\n"
                    "===================================</code>"
                )
            else:
                text = (
                    "📄 <b>Format Resume Perhotelan Darat / Internasional</b>\n\n"
                    "Ketuk kolom teks di bawah ini untuk langsung menyalin formatnya, lalu isi/edit sesuai pengalaman Anda:\n\n"
                    "<code>===================================\n"
                    "WORK EXPERIENCE (Pengalaman Kerja)\n"
                    "===================================\n"
                    "1. Job Title      : [Jabatan, misal: Commis De Cuisine / Cook]\n"
                    "   Company Name   : [Nama Hotel / Perusahaan]\n"
                    "   Location       : [Kota, Negara, misal: Dubai, UAE]\n"
                    "   Period         : [Bulan/Tahun Mulai - Selesai]\n"
                    "   Responsibilities:\n"
                    "   - [Deskripsi tugas 1]\n"
                    "   - [Deskripsi tugas 2]\n"
                    "   - [Deskripsi tugas 3]\n\n"
                    "===================================\n"
                    "EDUCATION & CERTIFICATIONS\n"
                    "===================================\n"
                    "1. School/Univ   : [Nama Sekolah/Universitas]\n"
                    "   Degree/Major   : [Jurusan, misal: Hospitality]\n"
                    "   Graduation Year: [Tahun Kelulusan]\n\n"
                    "2. Certificate    : [Sertifikat Keahlian]\n"
                    "===================================</code>"
                )
                
            markup = {
                "inline_keyboard": [
                    [{"text": "🔙 Kembali", "callback_data": "menu_cv"}]
                ]
            }
            edit_telegram_message(token, user_chat_id, message_id, text, markup)
            
        elif callback_data == "menu_stats":
            answer_callback_query(token, callback_query_id)
            stats = db_helper.get_stats()
            _, target_chat_id = get_bot_credentials()
            
            last_run = int(db_helper.get_setting("last_run", 0))
            if last_run > 0:
                local_time = time.strftime('%d-%m-%Y %H:%M:%S', time.localtime(last_run))
            else:
                local_time = "Belum pernah berjalan"
                
            interval = db_helper.get_setting("interval_hours", 1)
            
            text_stats = (
                f"📊 <b>Statistik & Informasi Sistem Bot</b>\n\n"
                f"• <b>Total Lowongan Kerja:</b> {stats['total_jobs']} loker\n"
                f"• <b>Total Agensi Terdaftar:</b> {stats['total_agencies']} agensi\n"
                f"• <b>Total Pelanggan Alert:</b> {stats['total_subscribers']} user\n\n"
                f"⏱ <b>Interval Scraping:</b> {interval} Jam sekali\n"
                f"🔄 <b>Terakhir Dipindai:</b> <code>{local_time}</code>\n"
                f"📢 <b>Target Group ID:</b> <code>{target_chat_id}</code>\n\n"
                f"<i>Sistem berjalan otomatis di server PythonAnywhere secara realtime.</i>"
            )
            
            markup = {
                "inline_keyboard": [
                    [{"text": "🔙 Kembali", "callback_data": "menu_main"}]
                ]
            }
            edit_telegram_message(token, user_chat_id, message_id, text_stats, markup)
            
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

@app.route("/debug-log")
def debug_log():
    log_path = "/var/log/amanputradewa.pythonanywhere.com.error.log"
    if not os.path.exists(log_path):
        return jsonify({"error": f"Log file not found at {log_path}"})
    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            last_lines = lines[-100:]
            return "<pre>" + "".join(last_lines) + "</pre>"
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
