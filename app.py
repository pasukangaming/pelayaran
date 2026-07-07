import os
import time
import threading
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

# In-memory credential cache to avoid repeated DB hits per request
_cred_cache = {}

def get_bot_credentials():
    if _cred_cache.get("token") and _cred_cache.get("chat_id"):
        return _cred_cache["token"], _cred_cache["chat_id"]
    token = db_helper.get_setting("telegram_bot_token")
    chat_id = db_helper.get_setting("telegram_chat_id")
    if token:
        _cred_cache["token"] = token
    if chat_id:
        _cred_cache["chat_id"] = chat_id
    return token, chat_id

def invalidate_cred_cache():
    _cred_cache.clear()

def is_user_admin(token, user_chat_id, chat_type="private"):
    admins = db_helper.get_bot_admins()
    admins = [str(a) for a in admins if a and str(a).lower() != "none"]
    
    admin_id = db_helper.get_setting("owner_admin_id")
    if not admin_id or str(admin_id).strip() == "" or str(admin_id).lower() == "none":
        admin_id = None
    
    print(f"[DEBUG] Checking admin status for user_chat_id: {user_chat_id}, chat_type: {chat_type}")
    print(f"[DEBUG] Current admins list: {admins}, owner_admin_id: {admin_id}")
    
    if admin_id:
        if str(admin_id) not in admins:
            db_helper.add_bot_admin(admin_id)
            admins.append(str(admin_id))
        if str(user_chat_id) == str(admin_id):
            print(f"[DEBUG] Matches owner_admin_id ({admin_id}) - ACCESS GRANTED")
            return True
            
    if str(user_chat_id) in admins:
        print(f"[DEBUG] Matches admins list - ACCESS GRANTED")
        return True
        
    env_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if env_chat_id and str(env_chat_id).lower() != "none" and str(user_chat_id) == str(env_chat_id):
        db_helper.set_setting("owner_admin_id", str(user_chat_id))
        db_helper.add_bot_admin(str(user_chat_id))
        db_helper.invalidate_settings_cache()
        print(f"[DEBUG] Matches env TELEGRAM_CHAT_ID ({env_chat_id}) - ACCESS GRANTED")
        return True
        
    if not admin_id and str(user_chat_id).strip() and not str(user_chat_id).startswith("-"):
        db_helper.set_setting("owner_admin_id", str(user_chat_id))
        db_helper.add_bot_admin(str(user_chat_id))
        db_helper.invalidate_settings_cache()
        print(f"[DEBUG] No owner registered yet. Registering user as Owner - ACCESS GRANTED")
        return True
        
    if chat_type in ["group", "supergroup"]:
        target_group_id = db_helper.get_setting("telegram_chat_id")
        if target_group_id and str(target_group_id).startswith("-"):
            try:
                payload = {
                    "chat_id": target_group_id,
                    "user_id": user_chat_id
                }
                res = call_telegram_api("getChatMember", payload)
                if res and res.get("ok"):
                    status = res["result"].get("status")
                    print(f"[DEBUG] Group {target_group_id} member status check for user {user_chat_id}: {status}")
                    if status in ["creator", "administrator"]:
                        print(f"[DEBUG] Group admin/creator - ACCESS GRANTED")
                        return True
            except Exception as e:
                print(f"[DEBUG] Error checking group admin status: {e}")
            
    print(f"[DEBUG] No credentials matched - ACCESS DENIED")
    return False
def categorize_job(position):
    pos_lower = position.lower()
    deck_kws = ['master', 'captain', 'mate', 'officer', 'deck', 'bosun', 'ab ', 'os ', 'cadet', 'helmsman', 'jurumudi', 'kelasi']
    engine_kws = ['engineer', 'engine', 'oiler', 'wiper', 'fitter', 'electrician', 'motorman']
    hk_kws = ['housekeeping', 'stateroom steward', 'stateroom attendant', 'room steward', 'cabin steward', 'stateroom host', 'public area host', 'laundry host', 'utility cleaner', 'rooms division', 'cleaner', 'hk ', 'room boy', 'cabin attendant', 'housekeeper']
    fnb_kws = ['waiter', 'waitress', 'restaurant steward', 'buffet steward', 'wine steward', 'messboy', 'f&b', 'food & beverage', 'galley steward', 'restaurant', 'snack', 'server']
    culinary_kws = ['cook', 'chef', 'galley', 'culinary', 'commis', 'baker', 'pastry', 'butcher', 'cook helper', 'demi chef', 'kitchen']
    bar_kws = ['bar ', 'bartender', 'bar utility', 'bar steward', 'bar boy', 'bar keep', 'bar supervisor', 'bar manager', 'bar server', 'bar cleaner']
    laundry_kws = ['laundry', 'laundryman', 'laundry utility', 'laundry operator', 'laundry attendant', 'tailor', 'linen keeper']
    landbase_kws = ['hotel darat', 'receptionist', 'front office', 'spa ', 'butler', 'cleaner', 'landbase']
    
    if any(kw in pos_lower for kw in bar_kws):
        return "bar"
    elif any(kw in pos_lower for kw in laundry_kws):
        return "laundry"
    elif any(kw in pos_lower for kw in hk_kws):
        return "housekeeping"
    elif any(kw in pos_lower for kw in culinary_kws):
        return "culinary"
    elif any(kw in pos_lower for kw in fnb_kws):
        return "fnb"
    elif any(kw in pos_lower for kw in deck_kws):
        return "deck"
    elif any(kw in pos_lower for kw in engine_kws):
        return "engine"
    elif any(kw in pos_lower for kw in landbase_kws):
        return "landbase"
    return "other"
def call_telegram_api(method, payload):
    token = get_bot_credentials()[0]
    if not token:
        return None
        
    proxy_url = db_helper.get_setting("google_proxy_url")
    base_url = f"https://api.telegram.org/bot{token}/{method}"
    
    query_params = {}
    for k, v in payload.items():
        if isinstance(v, (dict, list)):
            query_params[k] = json.dumps(v)
        else:
            query_params[k] = str(v)
            
    url_parts = list(urllib.parse.urlparse(base_url))
    url_parts[4] = urllib.parse.urlencode(query_params)
    telegram_url = urllib.parse.urlunparse(url_parts)
    
    if proxy_url:
        target_url = f"{proxy_url}?url={urllib.parse.quote(telegram_url)}"
    else:
        target_url = telegram_url
        
    try:
        response = requests.get(target_url, timeout=3.0)
        return response.json()
    except Exception as e:
        print(f"Error calling Telegram API ({method}) via proxy: {e}")
        try:
            fallback_response = requests.post(base_url, json=payload, timeout=2.0)
            return fallback_response.json()
        except Exception as fe:
            print(f"Fallback direct call failed: {fe}")
            return None

def send_telegram_message(token, chat_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return call_telegram_api("sendMessage", payload)

def edit_telegram_message(token, chat_id, message_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return call_telegram_api("editMessageText", payload)

def answer_callback_query(token, callback_query_id, text=None, show_alert=False):
    """Fire-and-forget: runs in background thread to not block main response."""
    def _do():
        payload = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        if show_alert:
            payload["show_alert"] = True
        call_telegram_api("answerCallbackQuery", payload)
    threading.Thread(target=_do, daemon=True).start()

# Menu Markups
def get_main_menu_markup(is_admin=False):
    keyboard = [
        [
            {"text": "💼 Lowongan Per Jabatan", "callback_data": "menu_jobs"}
        ],
        [
            {"text": "🏢 Daftar Agency Resmi", "callback_data": "menu_agencies"},
            {"text": "🔔 Langganan Loker", "callback_data": "menu_subscribe"}
        ]
    ]
    if is_admin:
        keyboard.append([
            {"text": "📊 Statistik Bot", "callback_data": "menu_stats"},
            {"text": "🔄 Cek Loker Sekarang 🔐", "callback_data": "menu_scrape"}
        ])
        keyboard.append([
            {"text": "⚙️ Atur Interval 🔐", "callback_data": "menu_settings"},
            {"text": "📢 Bagikan Bot", "callback_data": "menu_share"}
        ])
    else:
        keyboard.append([
            {"text": "📊 Statistik Bot", "callback_data": "menu_stats"},
            {"text": "📢 Bagikan Bot", "callback_data": "menu_share"}
        ])
    return {"inline_keyboard": keyboard}

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
    active_cats = []
    if current_sub:
        if current_sub == "all":
            active_cats = ["deck", "engine", "housekeeping", "bar", "fnb", "culinary", "laundry", "landbase"]
        else:
            active_cats = [p.strip() for p in current_sub.split(",") if p.strip()]
            
    keyboard = [
        [
            {"text": "🚢 Deck" + (" ✅" if "deck" in active_cats else ""), "callback_data": "sub_toggle:deck"},
            {"text": "🔧 Engine" + (" ✅" if "engine" in active_cats else ""), "callback_data": "sub_toggle:engine"}
        ],
        [
            {"text": "🧹 Housekeeping" + (" ✅" if "housekeeping" in active_cats else ""), "callback_data": "sub_toggle:housekeeping"},
            {"text": "🍹 Bar" + (" ✅" if "bar" in active_cats else ""), "callback_data": "sub_toggle:bar"}
        ],
        [
            {"text": "🍽 Food & Beverage" + (" ✅" if "fnb" in active_cats else ""), "callback_data": "sub_toggle:fnb"},
            {"text": "🍳 Culinary" + (" ✅" if "culinary" in active_cats else ""), "callback_data": "sub_toggle:culinary"}
        ],
        [
            {"text": "🧺 Laundry" + (" ✅" if "laundry" in active_cats else ""), "callback_data": "sub_toggle:laundry"},
            {"text": "🏨 Hotel Darat" + (" ✅" if "landbase" in active_cats else ""), "callback_data": "sub_toggle:landbase"}
        ],
        [
            {"text": "✨ Semua Departemen" + (" ✅" if current_sub == "all" else ""), "callback_data": "sub_action:all"}
        ]
    ]
    if current_sub:
        keyboard.append([{"text": "🔕 Berhenti Berlangganan", "callback_data": "sub_action:unsubscribe"}])
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
                {"text": "🧹 Housekeeping Department", "callback_data": "list_jobs:housekeeping"},
                {"text": "🍹 Bar Department", "callback_data": "list_jobs:bar"}
            ],
            [
                {"text": "🍽 Food & Beverage Department", "callback_data": "list_jobs:fnb"},
                {"text": "🍳 Culinary Department", "callback_data": "list_jobs:culinary"}
            ],
            [
                {"text": "🧺 Laundry Department", "callback_data": "list_jobs:laundry"},
                {"text": "🏨 Landbase Hotel (Darat)", "callback_data": "list_jobs:landbase"}
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
                {"text": "➕ Tambah Agency 🔐", "callback_data": "menu_add_agency"},
                {"text": "❌ Hapus Agency 🔐", "callback_data": "menu_delete_agency_list"}
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
                {"text": "✍️ Input Manual 🔐", "callback_data": "menu_add_agency_manual"},
                {"text": "🔄 Update Otomatis 🔐", "callback_data": "menu_add_agency_auto"}
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

def get_settings_markup(current_minutes):
    presets = [
        ("1 Menit", "1"),
        ("5 Menit", "5"),
        ("15 Menit", "15"),
        ("30 Menit", "30"),
        ("1 Jam", "60"),
        ("3 Jam", "180"),
        ("6 Jam", "360")
    ]
    keyboard = []
    row1 = []
    row2 = []
    for i, (text, val) in enumerate(presets):
        is_active = str(current_minutes) == val
        btn_text = f"✅ {text}" if is_active else text
        if i < 4:
            row1.append({"text": btn_text, "callback_data": f"set_interval_min:{val}"})
        else:
            row2.append({"text": btn_text, "callback_data": f"set_interval_min:{val}"})
    keyboard.append(row1)
    keyboard.append(row2)
    keyboard.append([{"text": "⌨️ Atur Waktu Kustom (Menit) 🔐", "callback_data": "menu_custom_interval"}])
    keyboard.append([
        {"text": "👥 Kelola Admin 🔐", "callback_data": "menu_manage_admins"},
        {"text": "🚨 Hapus Semua Loker 🔐", "callback_data": "menu_clear_jobs"}
    ])
    keyboard.append([{"text": "🔙 Kembali ke Menu Utama", "callback_data": "menu_main"}])
    return {"inline_keyboard": keyboard}

def get_admins_markup(admins, owner_id):
    keyboard = []
    for adm in admins:
        if str(adm) != str(owner_id):
            keyboard.append([
                {"text": f"❌ Hapus ID: {adm}", "callback_data": f"delete_admin:{adm}"}
            ])
    keyboard.append([
        {"text": "➕ Tambah Admin Baru 🔐", "callback_data": "menu_add_admin_prompt"}
    ])
    keyboard.append([{"text": "🔙 Kembali ke Pengaturan", "callback_data": "menu_settings"}])
    return {"inline_keyboard": keyboard}

def extract_instagram_link(contact_str):
    if not contact_str:
        return None
    import re
    match = re.search(r'https?://[^\s]*instagram\.com[^\s]*', contact_str)
    if match:
        return match.group(0).rstrip('/')
    return None

def clean_contact_info(contact_str):
    if not contact_str:
        return ""
    import re
    cleaned = re.sub(r'\s*/?\s*IG:\s*https?://[^\s]*instagram\.com[^\s]*', '', contact_str, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s*/?\s*https?://[^\s]*instagram\.com[^\s]*', '', cleaned, flags=re.IGNORECASE)
    return cleaned.strip(' /')

def get_agency_by_job(job):
    try:
        conn = db_helper.get_db_connection()
        cursor = conn.cursor()
        
        # 1. Exact match
        cursor.execute("SELECT contact, website FROM agencies WHERE name = ?", (job['company'],))
        row = cursor.fetchone()
        if row:
            conn.close()
            return dict(row)
            
        # 2. Partial match
        cursor.execute("SELECT contact, website FROM agencies WHERE ? LIKE '%' || name || '%' OR name LIKE '%' || ? || '%'", (job['company'], job['company']))
        row = cursor.fetchone()
        if row:
            conn.close()
            return dict(row)
            
        # 3. Domain match
        from urllib.parse import urlparse
        job_domain = urlparse(job['link']).netloc.replace('www.', '')
        cursor.execute("SELECT contact, website FROM agencies")
        all_ags = cursor.fetchall()
        for ag in all_ags:
            if ag['website']:
                ag_domain = urlparse(ag['website']).netloc.replace('www.', '')
                if job_domain == ag_domain:
                    conn.close()
                    return dict(ag)
        conn.close()
    except Exception as e:
        print(f"Error in get_agency_by_job: {e}")
    return None

def format_job_message(job):
    pos = scrapers.escape_html(job['position'])
    comp = scrapers.escape_html(job['company'])
    link = job['link']
    
    vessel = job['vessel_type'].strip()
    if not vessel or vessel.lower() in ["lihat detail", "detail", "n/a", "unknown", "lihat detail loker"]:
        vessel_str = f"<a href='{link}'>Cek Detail Kapal di Website</a>"
    else:
        vessel_str = scrapers.escape_html(vessel)
        
    sal = job['salary'].strip()
    if not sal or sal.lower() in ["hubungi perusahaan", "negotiable", "hubungi agency", "discuss", "unknown", "hubungi perusahaan / agency"]:
        salary_str = f"Sesuai Standar Perusahaan (Hubungi Agency / Tanyakan Saat Interview)"
    else:
        salary_str = scrapers.escape_html(sal)
        
    jd = job['join_date'].strip()
    if not jd or jd.lower() in ["lihat detail", "immediately", "secepatnya", "asap", "unknown", "lihat detail loker"]:
        join_str = f"Segera / <a href='{link}'>Lihat Jadwal Keberangkatan</a>"
    else:
        join_str = scrapers.escape_html(jd)
        
    dur = job['duration'].strip()
    if not dur or dur.lower() in ["sesuai kontrak", "tbd", "unknown", "lihat detail loker"]:
        duration_str = f"Sesuai Perjanjian Kerja Laut (PKL) / Cek Detail Loker"
    else:
        duration_str = scrapers.escape_html(dur)
        
    # Look up agency to find Instagram/social media
    agency_info = get_agency_by_job(job)
    ig_str = ""
    if agency_info:
        ig_link = extract_instagram_link(agency_info['contact'])
        if ig_link:
            ig_str = f"📸 <b>Medsos Agency:</b> <a href='{ig_link}'>Instagram Resmi</a>\n"
        
    message = (
        f"💼 <b>LOWONGAN JOB BARU</b>\n\n"
        f"💼 <b>Posisi:</b> {pos}\n"
        f"🛥 <b>Jenis Kapal:</b> {vessel_str}\n"
        f"💵 <b>Gaji:</b> {salary_str}\n"
        f"📅 <b>Join Date:</b> {join_str}\n"
        f"⏱ <b>Kontrak:</b> {duration_str}\n"
        f"🏢 <b>Perusahaan:</b> {comp}\n"
        f"{ig_str}\n"
        f"🔗 <a href='{link}'>Detail &amp; Apply Loker</a>"
    )
    return message

# Business Logic for Scraper (Used by Cron)
def run_scrape_and_post(manual_trigger=False, user_chat_id=None):
    token, chat_id = get_bot_credentials()
    if not token or not chat_id:
        print("Scraper skipped: Telegram bot token or chat ID is missing.")
        return False, "Kredensial Telegram Bot belum diatur."
        
    interval_minutes = int(db_helper.get_setting("interval_minutes", 60))
    last_run = int(db_helper.get_setting("last_run", 0))
    current_time = int(time.time())
    
    if not manual_trigger:
        elapsed_minutes = (current_time - last_run) / 60
        if elapsed_minutes < interval_minutes:
            msg = f"Scraper dilompati. Selisih waktu ({elapsed_minutes:.2f} menit) kurang dari interval ({interval_minutes} menit)."
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
            message = format_job_message(job)
            
            success = send_telegram_message(token, chat_id, message)
            if success and success.get("ok"):
                db_helper.mark_job_as_sent(job_id)
                new_jobs_count += 1
                
                # Send private alerts to category subscribers
                job_cat = categorize_job(job["position"])
                if job_cat != "other":
                    subs = db_helper.get_subscribers_by_category(job_cat)
                    
                    sal = job['salary'].strip()
                    if not sal or sal.lower() in ["hubungi perusahaan", "negotiable", "hubungi agency", "discuss", "unknown", "hubungi perusahaan / agency"]:
                        salary_str = "Sesuai Standar Perusahaan"
                    else:
                        salary_str = scrapers.escape_html(sal)
                        
                    alert_msg = (
                        f"🔔 <b>[ALERT LANGGANAN] Loker Baru Sesuai Departemen Anda!</b>\n\n"
                        f"💼 <b>Posisi:</b> {scrapers.escape_html(job['position'])}\n"
                        f"🏢 <b>Perusahaan:</b> {scrapers.escape_html(job['company'])}\n"
                        f"💵 <b>Gaji:</b> {salary_str}\n"
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
        
        edit_telegram_message(token, user_chat_id, message_id, final_text, get_main_menu_markup(is_user_admin(token, user_chat_id)))
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
                    message = format_job_message(job)
                    success = send_telegram_message(token, chat_id, message)
                    if success and success.get("ok"):
                        db_helper.mark_job_as_sent(job_id)
                        new_jobs_from_source += 1
                        
                        # Send private alerts to category subscribers
                        job_cat = categorize_job(job["position"])
                        if job_cat != "other":
                            subs = db_helper.get_subscribers_by_category(job_cat)
                            
                            sal = job['salary'].strip()
                            if not sal or sal.lower() in ["hubungi perusahaan", "negotiable", "hubungi agency", "discuss", "unknown", "hubungi perusahaan / agency"]:
                                salary_str = "Sesuai Standar Perusahaan"
                            else:
                                salary_str = scrapers.escape_html(sal)
                                
                            alert_msg = (
                                f"🔔 <b>[ALERT LANGGANAN] Loker Baru Sesuai Departemen Anda!</b>\n\n"
                                f"💼 <b>Posisi:</b> {scrapers.escape_html(job['position'])}\n"
                                f"🏢 <b>Perusahaan:</b> {scrapers.escape_html(job['company'])}\n"
                                f"💵 <b>Gaji:</b> {salary_str}\n"
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

@app.route("/reset-owner")
def reset_owner_route():
    try:
        db_helper.set_setting("owner_admin_id", None)
        db_helper.set_setting("bot_admins", "")
        db_helper.invalidate_settings_cache()
        return "Owner Admin has been successfully reset! Message /start to the bot on your main account to become the new owner.", 200
    except Exception as e:
        return f"Error resetting owner: {e}", 500

@app.route("/set-owner/<owner_id>")
def set_owner_route(owner_id):
    try:
        db_helper.set_setting("owner_admin_id", str(owner_id))
        db_helper.add_bot_admin(str(owner_id))
        db_helper.invalidate_settings_cache()
        return f"Success! Owner Admin has been set to {owner_id}. Message /start to the bot on that account to see the admin menus.", 200
    except Exception as e:
        return f"Error setting owner: {e}", 500

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
        from_data = message_data.get("from")
        sender_user_id = from_data.get("id") if from_data and isinstance(from_data, dict) else user_chat_id
        text = message_data.get("text", "").strip()
        
        if chat["type"] in ["group", "supergroup", "channel"]:
            db_helper.set_setting("telegram_chat_id", user_chat_id)
            token, chat_id = get_bot_credentials()
            
        if text.startswith("/start") or text.startswith("/menu"):
            send_telegram_message(
                token, 
                user_chat_id, 
                "🚢 <b>Selamat datang para siswa</b>\n\nSilakan pilih menu bot di bawah ini:", 
                get_main_menu_markup(is_user_admin(token, sender_user_id, chat["type"]))
            )
            db_helper.set_user_state(user_chat_id, "normal")
            
        elif text == "/id":
            send_telegram_message(token, user_chat_id, f"ID Chat ini adalah: <code>{user_chat_id}</code>")
            
        else:
            state = db_helper.get_user_state(user_chat_id)
            if state in ["awaiting_agency_data", "awaiting_custom_interval", "awaiting_new_admin_id"] and not is_user_admin(token, sender_user_id, chat["type"]):
                db_helper.set_user_state(user_chat_id, "normal")
                send_telegram_message(token, user_chat_id, "❌ Akses Ditolak: Anda bukan Administrator Bot.", get_main_menu_markup(is_user_admin(token, sender_user_id, chat["type"])))
            elif state == "awaiting_agency_data":
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
                        vessel = j['vessel_type'].strip()
                        if not vessel or vessel.lower() in ["lihat detail", "detail", "n/a", "unknown", "lihat detail loker"]:
                            vessel = "Cek Detail Kapal"
                            
                        sal = j['salary'].strip()
                        if not sal or sal.lower() in ["hubungi perusahaan", "negotiable", "hubungi agency", "discuss", "unknown", "hubungi perusahaan / agency"]:
                            sal = "Standar Perusahaan"
                            
                        jd = j['join_date'].strip()
                        if not jd or jd.lower() in ["lihat detail", "immediately", "secepatnya", "asap", "unknown", "lihat detail loker"]:
                            jd = "Segera"
                            
                        text_res += f"{idx+1}. <b>{j['position']}</b>\n"
                        text_res += f"   🏢 {j['company']} | 🛥 {vessel}\n"
                        text_res += f"   💵 Gaji: {sal} | 📅 Join: {jd}\n"
                        text_res += f"   🔗 <a href='{j['link']}'>Detail Loker</a>\n\n"
                else:
                    text_res = f"❌ Tidak ditemukan lowongan dengan kata kunci: <b>{query}</b>.\n\nCoba cari kata kunci lainnya (misal: AB, Fitter, Waiter)."
                    
            elif state == "awaiting_custom_interval":
                try:
                    minutes = int(text.strip())
                    if minutes <= 0:
                        raise ValueError()
                    db_helper.set_setting("interval_minutes", minutes)
                    db_helper.set_setting("interval_hours", None)
                    db_helper.invalidate_settings_cache()
                    
                    text_res = (
                        f"✅ <b>Interval Berhasil Diatur!</b>\n\n"
                        f"Bot sekarang diatur untuk memeriksa loker setiap: <b>{minutes} Menit</b>.\n"
                        f"<i>Pastikan cron job / pemanggil /run-cron Anda diatur lebih cepat dari interval ini agar dapat mendeteksi perubahan.</i>"
                    )
                except ValueError:
                    text_res = "❌ <b>Input Tidak Valid</b>\n\nHarap kirimkan angka bulat positif saja (dalam satuan menit). Contoh: <code>5</code> atau <code>30</code>."
                
                db_helper.set_user_state(user_chat_id, "normal")
                send_telegram_message(token, user_chat_id, text_res, get_main_menu_markup(is_user_admin(token, sender_user_id, chat["type"])))
                
            elif state == "awaiting_new_admin_id":
                try:
                    new_id = int(text.strip())
                    success = db_helper.add_bot_admin(new_id)
                    if success:
                        text_res = f"✅ <b>Admin Berhasil Ditambahkan!</b>\n\nTelegram User ID <code>{new_id}</code> sekarang terdaftar sebagai Administrator Bot dan memiliki akses ke menu gembok 🔐."
                    else:
                        text_res = f"❌ <b>Gagal Menambahkan</b>\n\nUser ID <code>{new_id}</code> mungkin sudah terdaftar sebagai Administrator."
                except ValueError:
                    text_res = "❌ <b>Input Tidak Valid</b>\n\nHarap kirimkan angka bulat positif Telegram User ID. Contoh: <code>123456789</code>."
                
                db_helper.set_user_state(user_chat_id, "normal")
                send_telegram_message(token, user_chat_id, text_res, get_main_menu_markup(is_user_admin(token, sender_user_id, chat["type"])))
                
            else:
                db_helper.set_user_state(user_chat_id, "normal")
                send_telegram_message(token, user_chat_id, "Kembali ke Menu Utama:", get_main_menu_markup(is_user_admin(token, sender_user_id, chat["type"])))
                
    elif "callback_query" in data:
        callback_query = data["callback_query"]
        callback_query_id = callback_query["id"]
        user_chat_id = callback_query["message"]["chat"]["id"]
        message_id = callback_query["message"]["message_id"]
        callback_data = callback_query["data"]
        clicker_user_id = callback_query["from"]["id"]
        chat_type = callback_query["message"]["chat"]["type"]
        
        # Check admin credentials
        admin_callbacks = [
            "menu_scrape", "menu_settings", "menu_custom_interval", 
            "menu_add_agency", "menu_add_agency_manual", "menu_add_agency_auto",
            "menu_delete_agency_list", "menu_clear_jobs", "clear_jobs_confirm",
            "menu_manage_admins", "menu_add_admin_prompt"
        ]
        is_admin_req = (
            callback_data in admin_callbacks or 
            callback_data.startswith("set_interval_min:") or 
            callback_data.startswith("delete_agency:") or 
            callback_data.startswith("delete_admin:")
        )
        
        if is_admin_req and not is_user_admin(token, clicker_user_id, chat_type):
            answer_callback_query(
                token, 
                callback_query_id, 
                text="❌ Akses Ditolak: Fitur ini hanya dapat diakses oleh Administrator Bot.", 
                show_alert=True
            )
            return jsonify({"status": "forbidden"})
            
        if callback_data == "menu_main":
            answer_callback_query(token, callback_query_id)
            edit_telegram_message(
                token, 
                user_chat_id, 
                message_id, 
                "🚢 <b>Selamat datang para siswa</b>\n\nSilakan pilih menu bot di bawah ini:", 
                get_main_menu_markup(is_user_admin(token, clicker_user_id, chat_type))
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
                "housekeeping": ['housekeeping', 'stateroom steward', 'stateroom attendant', 'room steward', 'cabin steward', 'stateroom host', 'public area host', 'laundry host', 'utility cleaner', 'rooms division', 'cleaner', 'hk ', 'room boy', 'cabin attendant', 'housekeeper'],
                "fnb": ['waiter', 'waitress', 'restaurant steward', 'buffet steward', 'wine steward', 'messboy', 'f&b', 'food & beverage', 'galley steward', 'restaurant', 'snack', 'server'],
                "culinary": ['cook', 'chef', 'galley', 'culinary', 'commis', 'baker', 'pastry', 'butcher', 'cook helper', 'demi chef', 'kitchen'],
                "bar": ['bar ', 'bartender', 'bar utility', 'bar steward', 'bar boy', 'bar keep', 'bar supervisor', 'bar manager', 'bar server', 'bar cleaner'],
                "laundry": ['laundry', 'laundryman', 'laundry utility', 'laundry operator', 'laundry attendant', 'tailor', 'linen keeper'],
                "landbase": ['hotel darat', 'receptionist', 'front office', 'spa ', 'butler', 'cleaner', 'landbase']
            }
            
            keywords = keywords_map.get(category, [])
            jobs = db_helper.get_jobs_by_keywords(keywords)
            
            category_titles = {
                "deck": "🚢 Deck (Perwira & Rating)",
                "engine": "🔧 Engine (Engineer & Rating)",
                "housekeeping": "🧹 Housekeeping Department",
                "fnb": "🍽 Food & Beverage Department",
                "culinary": "🍳 Culinary Department",
                "bar": "🍹 Bar Department",
                "laundry": "🧺 Laundry Department",
                "landbase": "🏨 Landbase Hotel"
            }
            
            title = category_titles.get(category, "Lowongan Kerja")
            text = f"💼 <b>Daftar Lowongan - {title}</b>\n\n"
            
            if jobs:
                for idx, j in enumerate(jobs):
                    vessel = j['vessel_type'].strip()
                    if not vessel or vessel.lower() in ["lihat detail", "detail", "n/a", "unknown", "lihat detail loker"]:
                        vessel = "Cek Detail Kapal"
                        
                    sal = j['salary'].strip()
                    if not sal or sal.lower() in ["hubungi perusahaan", "negotiable", "hubungi agency", "discuss", "unknown", "hubungi perusahaan / agency"]:
                        sal = "Standar Perusahaan"
                        
                    jd = j['join_date'].strip()
                    if not jd or jd.lower() in ["lihat detail", "immediately", "secepatnya", "asap", "unknown", "lihat detail loker"]:
                        jd = "Segera"
                        
                    text += f"{idx+1}. <b>{j['position']}</b>\n"
                    text += f"   🏢 {j['company']} | 🛥 {vessel}\n"
                    text += f"   💵 Gaji: {sal} | 📅 Join: {jd}\n"
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
            parts = callback_data.split(":")
            category = parts[1]
            page = int(parts[2]) if len(parts) > 2 else 0
            answer_callback_query(token, callback_query_id)
            
            agencies = db_helper.get_agencies_by_type(category)
            per_page = 8
            total_pages = max(1, (len(agencies) + per_page - 1) // per_page)
            page = max(0, min(page, total_pages - 1))
            start = page * per_page
            page_agencies = agencies[start:start + per_page]
            
            category_title = "🚢 Cruise Line (SIUPPAK/P3MI)" if category == "cruise" else "🏨 Landbase Hotel (P3MI)"
            text = f"🏢 <b>Daftar Agency Resmi - {category_title}</b>\n"
            text += f"<i>Halaman {page + 1} dari {total_pages} ({len(agencies)} agensi total)</i>\n\n"
            
            for idx, ag in enumerate(page_agencies):
                global_idx = start + idx + 1
                text += f"{global_idx}. <b>{ag['name']}</b>\n"
                
                ig_link = extract_instagram_link(ag['contact'])
                cleaned_contact = clean_contact_info(ag['contact'])
                
                if cleaned_contact:
                    contact_short = cleaned_contact.split(' / ')[0] if ' / ' in cleaned_contact else cleaned_contact
                    if len(contact_short) > 80:
                        contact_short = contact_short[:77] + "..."
                    text += f"   📞 <code>{contact_short}</code>\n"
                if ag['website']:
                    text += f"   🌐 <a href='{ag['website']}'>Portal / Website</a>\n"
                if ig_link:
                    text += f"   📸 <a href='{ig_link}'>Instagram Resmi</a>\n"
                text += "\n"
            
            # Build navigation buttons
            nav_buttons = []
            if page > 0:
                nav_buttons.append({"text": "◀️ Sebelumnya", "callback_data": f"list_agencies:{category}:{page - 1}"})
            if page < total_pages - 1:
                nav_buttons.append({"text": "Selanjutnya ▶️", "callback_data": f"list_agencies:{category}:{page + 1}"})
            
            keyboard = []
            if nav_buttons:
                keyboard.append(nav_buttons)
            keyboard.append([{"text": "🔙 Kembali", "callback_data": "menu_agencies"}])
            
            markup = {"inline_keyboard": keyboard}
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
                f"Database bot telah diselaraskan dengan daftar agensi resmi (kapal pesiar & hotel darat) terverifikasi.\n\n"
                f"• Total agensi aktif di database: <b>{added_count} agensi</b>\n\n"
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
            parts = callback_data.split(":")
            loc = parts[1]
            page = int(parts[2]) if len(parts) > 2 else 0
            answer_callback_query(token, callback_query_id)
            
            if loc == "Lainnya":
                all_agencies = db_helper.get_agencies()
                agencies = [a for a in all_agencies if "jakarta" not in a["address"].lower() and "bali" not in a["address"].lower() and "surabaya" not in a["address"].lower()]
            else:
                agencies = db_helper.get_agencies_by_location(loc)
            
            per_page = 8
            total_pages = max(1, (len(agencies) + per_page - 1) // per_page) if agencies else 1
            page = max(0, min(page, total_pages - 1))
            start = page * per_page
            page_agencies = agencies[start:start + per_page]
                
            text = f"📍 <b>Daftar Agency di Wilayah: {loc}</b>\n"
            text += f"<i>Halaman {page + 1} dari {total_pages} ({len(agencies)} agensi)</i>\n\n"
            
            if page_agencies:
                for idx, ag in enumerate(page_agencies):
                    global_idx = start + idx + 1
                    text += f"{global_idx}. <b>{ag['name']}</b>\n"
                    
                    ig_link = extract_instagram_link(ag['contact'])
                    cleaned_contact = clean_contact_info(ag['contact'])
                    
                    if cleaned_contact:
                        contact_short = cleaned_contact.split(' / ')[0] if ' / ' in cleaned_contact else cleaned_contact
                        if len(contact_short) > 80:
                            contact_short = contact_short[:77] + "..."
                        text += f"   📞 <code>{contact_short}</code>\n"
                    if ag['website']:
                        text += f"   🌐 <a href='{ag['website']}'>Portal / Website</a>\n"
                    if ig_link:
                        text += f"   📸 <a href='{ig_link}'>Instagram Resmi</a>\n"
                    text += "\n"
            else:
                text += "❌ Belum ada agency terdaftar di wilayah ini."
            
            nav_buttons = []
            if page > 0:
                nav_buttons.append({"text": "◀️ Sebelumnya", "callback_data": f"list_agencies_loc:{loc}:{page - 1}"})
            if page < total_pages - 1:
                nav_buttons.append({"text": "Selanjutnya ▶️", "callback_data": f"list_agencies_loc:{loc}:{page + 1}"})
            
            keyboard = []
            if nav_buttons:
                keyboard.append(nav_buttons)
            keyboard.append([{"text": "🔙 Kembali", "callback_data": "menu_agencies_location"}])
            
            markup = {"inline_keyboard": keyboard}
            edit_telegram_message(token, user_chat_id, message_id, text, markup)
            
        elif callback_data == "menu_subscribe":
            answer_callback_query(token, callback_query_id)
            current_sub = db_helper.get_user_subscription(user_chat_id)
            
            if not current_sub:
                sub_title = "Belum Berlangganan"
            elif current_sub == "all":
                sub_title = "✨ Semua Departemen"
            else:
                cat_titles = {
                    "deck": "🚢 Deck",
                    "engine": "🔧 Engine",
                    "housekeeping": "🧹 Housekeeping",
                    "fnb": "🍽 Food & Beverage",
                    "culinary": "🍳 Culinary",
                    "bar": "🍹 Bar",
                    "laundry": "🧺 Laundry",
                    "landbase": "🏨 Hotel Darat"
                }
                parts = [p.strip() for p in current_sub.split(",") if p.strip()]
                sub_title = ", ".join([cat_titles.get(p, p) for p in parts])
                
            text = (
                f"🔔 <b>Personal Job Alerts (Langganan Loker)</b>\n\n"
                f"Dapatkan notifikasi pesan pribadi (japri) secara otomatis dari bot ketika ada lowongan baru sesuai minat jabatan Anda!\n\n"
                f"Status Langganan Aktif: <b>{sub_title}</b>\n\n"
                f"Silakan ketuk departemen di bawah ini untuk memilih satu/lebih (multi-pilihan) atau pilih Semua Departemen:"
            )
            edit_telegram_message(token, user_chat_id, message_id, text, get_subscribe_markup(current_sub))
            
        elif callback_data.startswith("sub_toggle:"):
            category = callback_data.split(":")[-1]
            answer_callback_query(token, callback_query_id)
            
            current_sub = db_helper.get_user_subscription(user_chat_id)
            
            if not current_sub:
                user_cats = [category]
            elif current_sub == "all":
                user_cats = [category]
            else:
                user_cats = [p.strip() for p in current_sub.split(",") if p.strip()]
                if category in user_cats:
                    user_cats.remove(category)
                else:
                    user_cats.append(category)
                    
            if not user_cats:
                db_helper.unsubscribe_user(user_chat_id)
            else:
                db_helper.subscribe_user(user_chat_id, ",".join(user_cats))
                
            # Re-render subscribe menu
            current_sub = db_helper.get_user_subscription(user_chat_id)
            if not current_sub:
                sub_title = "Belum Berlangganan"
            elif current_sub == "all":
                sub_title = "✨ Semua Departemen"
            else:
                cat_titles = {
                    "deck": "🚢 Deck",
                    "engine": "🔧 Engine",
                    "housekeeping": "🧹 Housekeeping",
                    "fnb": "🍽 Food & Beverage",
                    "culinary": "🍳 Culinary",
                    "bar": "🍹 Bar",
                    "laundry": "🧺 Laundry",
                    "landbase": "🏨 Hotel Darat"
                }
                parts = [p.strip() for p in current_sub.split(",") if p.strip()]
                sub_title = ", ".join([cat_titles.get(p, p) for p in parts])
                
            text = (
                f"🔔 <b>Personal Job Alerts (Langganan Loker)</b>\n\n"
                f"Dapatkan notifikasi pesan pribadi (japri) secara otomatis dari bot ketika ada lowongan baru sesuai minat jabatan Anda!\n\n"
                f"Status Langganan Aktif: <b>{sub_title}</b>\n\n"
                f"Silakan ketuk departemen di bawah ini untuk memilih satu/lebih (multi-pilihan) atau pilih Semua Departemen:"
            )
            edit_telegram_message(token, user_chat_id, message_id, text, get_subscribe_markup(current_sub))
            
        elif callback_data.startswith("sub_action:"):
            action = callback_data.split(":")[-1]
            answer_callback_query(token, callback_query_id)
            
            if action == "all":
                db_helper.subscribe_user(user_chat_id, "all")
            elif action == "unsubscribe":
                db_helper.unsubscribe_user(user_chat_id)
                
            # Re-render subscribe menu
            current_sub = db_helper.get_user_subscription(user_chat_id)
            if not current_sub:
                sub_title = "Belum Berlangganan"
            elif current_sub == "all":
                sub_title = "✨ Semua Departemen"
            else:
                cat_titles = {
                    "deck": "🚢 Deck",
                    "engine": "🔧 Engine",
                    "housekeeping": "🧹 Housekeeping",
                    "fnb": "🍽 Food & Beverage",
                    "culinary": "🍳 Culinary",
                    "bar": "🍹 Bar",
                    "laundry": "🧺 Laundry",
                    "landbase": "🏨 Hotel Darat"
                }
                parts = [p.strip() for p in current_sub.split(",") if p.strip()]
                sub_title = ", ".join([cat_titles.get(p, p) for p in parts])
                
            text = (
                f"🔔 <b>Personal Job Alerts (Langganan Loker)</b>\n\n"
                f"Dapatkan notifikasi pesan pribadi (japri) secara otomatis dari bot ketika ada lowongan baru sesuai minat jabatan Anda!\n\n"
                f"Status Langganan Aktif: <b>{sub_title}</b>\n\n"
                f"Silakan ketuk departemen di bawah ini untuk memilih satu/lebih (multi-pilihan) atau pilih Semua Departemen:"
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
                
            current_minutes = int(db_helper.get_setting("interval_minutes", 60))
            if current_minutes >= 60 and current_minutes % 60 == 0:
                interval_str = f"{current_minutes // 60} Jam"
            else:
                interval_str = f"{current_minutes} Menit"
            
            text_stats = (
                f"📊 <b>Statistik & Informasi Sistem Bot</b>\n\n"
                f"• <b>Total Lowongan Kerja:</b> {stats['total_jobs']} loker\n"
                f"• <b>Total Agensi Terdaftar:</b> {stats['total_agencies']} agensi\n"
                f"• <b>Total Pelanggan Alert:</b> {stats['total_subscribers']} user\n\n"
                f"⏱ <b>Interval Scraping:</b> {interval_str} sekali\n"
                f"🔄 <b>Terakhir Dipindai:</b> <code>{local_time}</code>\n"
                f"📢 <b>Target Group ID:</b> <code>{target_chat_id}</code>\n\n"
                f"<i>Sistem berjalan otomatis di server secara realtime.</i>"
            )
            
            markup = {
                "inline_keyboard": [
                    [{"text": "🔙 Kembali", "callback_data": "menu_main"}]
                ]
            }
            edit_telegram_message(token, user_chat_id, message_id, text_stats, markup)
            
        elif callback_data == "menu_settings":
            answer_callback_query(token, callback_query_id)
            current_minutes = int(db_helper.get_setting("interval_minutes", 60))
            if current_minutes >= 60 and current_minutes % 60 == 0:
                display_time = f"{current_minutes // 60} Jam"
            else:
                display_time = f"{current_minutes} Menit"
            edit_telegram_message(
                token, 
                user_chat_id, 
                message_id, 
                f"⏱️ <b>Pengaturan Interval Waktu Update 🔐</b>\n\n"
                f"Pilih seberapa sering bot akan memposting loker baru jika terdeteksi.\n"
                f"Interval aktif saat ini: <b>{display_time}</b>", 
                get_settings_markup(current_minutes)
            )
            
        elif callback_data.startswith("set_interval_min:"):
            minutes = int(callback_data.split(":")[-1])
            db_helper.set_setting("interval_minutes", minutes)
            db_helper.set_setting("interval_hours", None)
            db_helper.invalidate_settings_cache()
            
            if minutes >= 60 and minutes % 60 == 0:
                display_time = f"{minutes // 60} Jam"
            else:
                display_time = f"{minutes} Menit"
                
            answer_callback_query(token, callback_query_id, f"Interval diatur ke {display_time}.")
            edit_telegram_message(
                token, 
                user_chat_id, 
                message_id, 
                f"⏱️ <b>Pengaturan Interval Waktu Update 🔐</b>\n\n"
                f"Pilih seberapa sering bot akan memposting loker baru jika terdeteksi.\n"
                f"Interval aktif saat ini: <b>{display_time}</b>", 
                get_settings_markup(minutes)
            )
        elif callback_data == "menu_custom_interval":
            answer_callback_query(token, callback_query_id)
            db_helper.set_user_state(user_chat_id, "awaiting_custom_interval")
            edit_telegram_message(
                token,
                user_chat_id,
                message_id,
                "⌨️ <b>Input Kustom Interval (Menit) 🔐</b>\n\n"
                "Silakan ketik angka interval pemeriksaan loker dalam satuan menit (contoh: ketik <code>5</code> untuk memeriksa setiap 5 menit, atau <code>1</code> untuk 1 menit):\n\n"
                "<i>Bot akan menunggu input angka dari Anda...</i>",
                {"inline_keyboard": [[{"text": "🔙 Batal", "callback_data": "menu_settings"}]]}
            )
        elif callback_data == "menu_manage_admins":
            answer_callback_query(token, callback_query_id)
            admins = db_helper.get_bot_admins()
            owner_id = db_helper.get_setting("owner_admin_id")
            
            text_adm = (
                "👥 <b>Manajemen Administrator Bot 🔐</b>\n\n"
                "Daftar administrator yang memiliki akses ke menu gembok 🔐:\n"
                f"👑 <b>Owner/Pemilik:</b> <code>{owner_id}</code>\n\n"
            )
            if len(admins) > 1:
                text_adm += "<b>Admin Tambahan:</b>\n"
                for adm in admins:
                    if str(adm) != str(owner_id):
                        text_adm += f"• <code>{adm}</code>\n"
            else:
                text_adm += "<i>Belum ada admin tambahan yang didaftarkan.</i>"
                
            edit_telegram_message(
                token, 
                user_chat_id, 
                message_id, 
                text_adm, 
                get_admins_markup(admins, owner_id)
            )
            
        elif callback_data == "menu_add_admin_prompt":
            answer_callback_query(token, callback_query_id)
            db_helper.set_user_state(user_chat_id, "awaiting_new_admin_id")
            edit_telegram_message(
                token,
                user_chat_id,
                message_id,
                "➕ <b>Tambah Administrator Baru 🔐</b>\n\n"
                "Silakan kirimkan <b>Telegram User ID</b> orang yang ingin Anda jadikan admin baru (berupa deretan angka):\n\n"
                "<i>Cara mencari ID: Orang tersebut bisa mengirim pesan `/id` ke bot ini terlebih dahulu dan memberikan ID-nya kepada Anda.</i>",
                {"inline_keyboard": [[{"text": "🔙 Batal", "callback_data": "menu_manage_admins"}]]}
            )
            
        elif callback_data.startswith("delete_admin:"):
            target_adm = callback_data.split(":")[-1]
            owner_id = db_helper.get_setting("owner_admin_id")
            
            if str(target_adm) == str(owner_id):
                answer_callback_query(token, callback_query_id, "Gagal: Tidak bisa menghapus pemilik utama!", show_alert=True)
            else:
                removed = db_helper.remove_bot_admin(target_adm)
                if removed:
                    answer_callback_query(token, callback_query_id, f"Admin {target_adm} berhasil dihapus.")
                else:
                    answer_callback_query(token, callback_query_id, "Gagal menghapus admin.")
                    
            admins = db_helper.get_bot_admins()
            text_adm = (
                "👥 <b>Manajemen Administrator Bot 🔐</b>\n\n"
                "Daftar administrator yang memiliki akses ke menu gembok 🔐:\n"
                f"👑 <b>Owner/Pemilik:</b> <code>{owner_id}</code>\n\n"
            )
            if len(admins) > 1:
                text_adm += "<b>Admin Tambahan:</b>\n"
                for adm in admins:
                    if str(adm) != str(owner_id):
                        text_adm += f"• <code>{adm}</code>\n"
            else:
                text_adm += "<i>Belum ada admin tambahan yang didaftarkan.</i>"
                
            edit_telegram_message(
                token, 
                user_chat_id, 
                message_id, 
                text_adm, 
                get_admins_markup(admins, owner_id)
            )
        elif callback_data == "menu_clear_jobs":
            answer_callback_query(token, callback_query_id)
            text_confirm = (
                "⚠️ <b>Konfirmasi Hapus Semua Loker</b>\n\n"
                "Apakah Anda yakin ingin menghapus seluruh data lowongan kerja beserta riwayat pengiriman dari database?\n\n"
                "• Tindakan ini akan mengosongkan riwayat agar bot dapat mengirim ulang loker lama sebagai loker baru pada pemindaian berikutnya.\n"
                "• Data langganan user dan daftar agensi resmi tidak akan dihapus."
            )
            markup = {
                "inline_keyboard": [
                    [
                        {"text": "✅ Ya, Hapus Semua", "callback_data": "clear_jobs_confirm"},
                        {"text": "❌ Batal", "callback_data": "menu_settings"}
                    ]
                ]
            }
            edit_telegram_message(token, user_chat_id, message_id, text_confirm, markup)
            
        elif callback_data == "clear_jobs_confirm":
            db_helper.clear_all_jobs()
            answer_callback_query(token, callback_query_id, "Data loker dibersihkan!")
            text_success = (
                "🚨 <b>Database Loker Berhasil Dibersihkan!</b>\n\n"
                "Seluruh data loker dan riwayat pengiriman (logs) telah dihapus dari sistem.\n\n"
                "Silakan klik tombol <b>Cek Loker Sekarang</b> pada menu utama jika ingin memulai pemindaian ulang dari awal."
            )
            markup = {
                "inline_keyboard": [
                    [{"text": "🔙 Kembali ke Pengaturan", "callback_data": "menu_settings"}]
                ]
            }
            edit_telegram_message(token, user_chat_id, message_id, text_success, markup)
            
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

@app.route("/clear-all-agencies")
def clear_all_agencies_route():
    try:
        conn = db_helper.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM agencies")
        conn.commit()
        conn.close()
        return "Tabel agensi berhasil dikosongkan!"
    except Exception as e:
        return f"Gagal mengosongkan tabel agensi: {str(e)}"

@app.route("/debug-log")
def debug_log():
    info = {}
    try:
        conn = db_helper.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(agencies)")
        info["agencies_columns"] = [dict(row) for row in cursor.fetchall()]
        conn.close()
    except Exception as e:
        info["db_error"] = str(e)
        
    try:
        err_path = "/var/log/amanputradewa.pythonanywhere.com.error.log"
        srv_path = "/var/log/amanputradewa.pythonanywhere.com.server.log"
        
        err_lines = []
        if os.path.exists(err_path):
            with open(err_path, "r", encoding="utf-8", errors="ignore") as f:
                err_lines = f.readlines()[-60:]
                
        srv_lines = []
        if os.path.exists(srv_path):
            with open(srv_path, "r", encoding="utf-8", errors="ignore") as f:
                srv_lines = f.readlines()[-60:]
                
        info["error_log"] = err_lines
        info["server_log"] = srv_lines
    except Exception as e:
        info["log_error"] = str(e)
        
    return jsonify(info)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
