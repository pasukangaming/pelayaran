import os
import sqlite3

# Path to the database file in the same directory as this helper
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pelayaran.db")

# Curated, official verified P3MI/SIUPPAK agencies in Indonesia
DEFAULT_AGENCIES = [
    ("PT Alpha Magsaysay Careers", "SIUPPAK & P3MI", "Kapal Pesiar & Hospitality", 
     "Jalan Batu Ceper Raya Nomor 52, Kebon Kelapa, Gambir, Jakarta Pusat", "+62 21 7591 2517 / recruitment@alphamagsaysay.co.id / IG: https://www.instagram.com/alphamagsaysay/", "https://www.alphamagsaysaycareers.com/"),
    ("PT Alpha Magsaysay International", "SIUPPAK & P3MI", "Kapal Pesiar & Hospitality", 
     "Jalan Batu Ceper Raya Nomor 52, Kebon Kelapa, Gambir, Jakarta Pusat", "+62 21 7591 2517 / recruitment@alphamagsaysay.co.id / IG: https://www.instagram.com/alphamagsaysay/", "https://www.alphamagsaysay.com/"),
    ("PT Ratu Oceania Raya Career", "SIUPPAK & P3MI", "Kapal Pesiar", 
     "Plaza DM 12th Floor, Jl. Jend. Sudirman Kav 25, Jakarta Selatan", "+62 21 5267073 / info@ratuoceania.com / IG: https://www.instagram.com/officialratuoceaniaraya/", "https://www.ratuoceaniaraya.com/career"),
    ("PT Ratu Oceania Raya Web", "SIUPPAK & P3MI", "Kapal Pesiar", 
     "Plaza DM 12th Floor, Jl. Jend. Sudirman Kav 25, Jakarta Selatan", "+62 21 5267073 / info@ratuoceania.com / IG: https://www.instagram.com/officialratuoceaniaraya/", "https://www.ratuoceaniaraya.com/"),
    ("PT Cipta Wira Tirta Jobs", "SIUPPAK & P3MI", "Kapal Pesiar & Hospitality", 
     "Jalan Kebon Sirih No. 17-19, Jakarta Pusat", "+62 21 391 1515 / recruitment@ciptawiratirta.com / IG: https://www.instagram.com/wiramanningservice/", "https://www.ciptawiratirta.com/jobs"),
    ("PT Cipta Wira Tirta Web", "SIUPPAK & P3MI", "Kapal Pesiar & Hospitality", 
     "Jalan Kebon Sirih No. 17-19, Jakarta Pusat", "+62 21 391 1515 / recruitment@ciptawiratirta.com / IG: https://www.instagram.com/wiramanningservice/", "https://www.ciptawiratirta.com/"),
    ("PT Equinox Cruise Careers", "SIUPPAK & P3MI", "Kapal Pesiar & Merchant", 
     "Menara Anugrah Lt. 24, Kantor Taman E.3.3, Jl. Mega Kuningan Lot 8.6-8.7, Jakarta Selatan", "+62 21 5794 8888 / info@equinox.co.id / IG: https://www.instagram.com/ebu.cruise/", "https://cruise.equinoxshipping.co.id/"),
    ("PT Equinox Cruise Jobs Portal", "SIUPPAK & P3MI", "Kapal Pesiar & Merchant", 
     "Menara Anugrah Lt. 24, Kantor Taman E.3.3, Jl. Mega Kuningan Lot 8.6-8.7, Jakarta Selatan", "+62 21 5794 8888 / info@equinox.co.id / IG: https://www.instagram.com/ebu.cruise/", "https://cruise.jobs.equinoxshipping.co.id/"),
    ("Cast-A-Way Cruise Recruiting (Hospitality)", "Official International Agency", "Kapal Pesiar & Hospitality", 
     "International Recruiting Office", "info@cast-a-way.com / IG: https://www.instagram.com/castawayindonesia/", "https://cast-a-way.com/hospitality/"),
    ("Cast-A-Way Cruise Recruiting (F&B)", "Official International Agency", "Kapal Pesiar & Hospitality", 
     "International Recruiting Office", "info@cast-a-way.com / IG: https://www.instagram.com/castawayindonesia/", "https://cast-a-way.com/fb-operations/"),
    ("Cast-A-Way Cruise Recruiting (Spa)", "Official International Agency", "Kapal Pesiar & Hospitality", 
     "International Recruiting Office", "info@cast-a-way.com / IG: https://www.instagram.com/castawayindonesia/", "https://cast-a-way.com/spa/"),
    ("PT Marine Pride Service (MPS)", "SIUPPAK & P3MI", "Kapal Pesiar & Merchant", 
     "Ruko Gading Kirana, Jl. Kirana Avenue No. 23, Kelapa Gading, Jakarta Utara", "info@mpsjakarta.com / IG: https://www.instagram.com/mpsjakarta/", "https://www.mpsjakarta.com/"),
    ("PT Marine Pride Service (MPS) Career", "SIUPPAK & P3MI", "Kapal Pesiar & Merchant", 
     "Ruko Gading Kirana, Jl. Kirana Avenue No. 23, Kelapa Gading, Jakarta Utara", "info@mpsjakarta.com / IG: https://www.instagram.com/mpsjakarta/", "https://www.mpsjakarta.com/apply-now/candidate"),
    ("PT Kuantum Marina Global Web", "SIUPPAK & P3MI", "Kapal Pesiar & Merchant", 
     "Gedung K-Marina Global, Jakarta", "recruitment@k-marinaglobal.com / IG: https://www.instagram.com/kuantummarinaglobal_official/", "https://k-marinaglobal.com/"),
    ("PT Kuantum Marina Global Career", "SIUPPAK & P3MI", "Kapal Pesiar & Merchant", 
     "Gedung K-Marina Global, Jakarta", "recruitment@k-marinaglobal.com / IG: https://www.instagram.com/kuantummarinaglobal_official/", "https://k-marinaglobal.com/career/")
]

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
    except Exception:
        pass
    return conn

def init_db(default_token=None, default_chat_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create settings table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    
    # Create sources table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            url TEXT UNIQUE,
            type TEXT
        )
    """)
    
    # Create user_states table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_states (
            chat_id INTEGER PRIMARY KEY,
            state TEXT
        )
    """)
    
    # Create sent_jobs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sent_jobs (
            job_id TEXT PRIMARY KEY,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create agencies table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            license_no TEXT,
            type TEXT,
            address TEXT,
            contact TEXT,
            website TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Check if created_at column exists in agencies table, if not alter the table
    try:
        cursor.execute("SELECT created_at FROM agencies LIMIT 1")
    except sqlite3.OperationalError:
        try:
            cursor.execute("ALTER TABLE agencies ADD COLUMN created_at TIMESTAMP")
            cursor.execute("UPDATE agencies SET created_at = datetime('now', 'localtime') WHERE created_at IS NULL")
            conn.commit()
            print("Successfully added created_at column to agencies table via migration.")
        except Exception as e:
            print(f"Error altering agencies table: {e}")
            
    # Create jobs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            position TEXT,
            vessel_type TEXT,
            salary TEXT,
            join_date TEXT,
            duration TEXT,
            company TEXT,
            link TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create subscribers table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subscribers (
            chat_id INTEGER PRIMARY KEY,
            category TEXT
        )
    """)
    
    conn.commit()
    
    # Populate default settings
    defaults = {
        "interval_hours": "1",
        "last_run": "0"
    }
    
    if default_token:
        defaults["telegram_bot_token"] = default_token
    if default_chat_id:
        defaults["telegram_chat_id"] = default_chat_id
        
    for key, value in defaults.items():
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))
        
    # Clear and populate filtered official built-in sources
    cursor.execute("DELETE FROM sources WHERE type = 'built-in'")
    default_sources = [
        ("Crewell", "https://crewell.net/en/vacancies/", "built-in"),
        ("JobMarineMan", "https://jobmarineman.com/vacancies/", "built-in"),
        ("Alpha Magsaysay Careers", "https://www.alphamagsaysay.co.id/", "built-in"),
        ("Ratu Oceania Raya Jobs", "https://ratuoceania.com/job-opening/", "built-in"),
        ("SBI Holland America Jobs", "https://www.sbi.co.id/career/", "built-in"),
        ("CTI Group Vacancies", "http://www.ctigroup.co.id/", "built-in"),
        ("Equinox Careers", "https://www.equinox.co.id/careers", "built-in"),
        ("Bali Paradise Vacancies", "https://baliparadisecitramandiri.co.id/vacancy/", "built-in"),
        ("Sentina Karya Career", "https://www.sentinakarya.co.id/career", "built-in"),
        ("Horizon Karir Jobs", "https://www.horizonkarir.com/vacancy", "built-in")
    ]
    
    for name, url, s_type in default_sources:
        cursor.execute("INSERT OR IGNORE INTO sources (name, url, type) VALUES (?, ?, ?)", (name, url, s_type))
        
    # Populate official agencies list
    for name, lic, a_type, addr, cont, web in DEFAULT_AGENCIES:
        cursor.execute("""
            INSERT OR REPLACE INTO agencies (name, license_no, type, address, contact, website) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, lic, a_type, addr, cont, web))
        
    conn.commit()
    conn.close()
    print("Database initialized successfully.")

def get_setting(key, default=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row["value"]
    return default

def set_setting(key, value):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

def get_sources():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, url, type FROM sources")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def add_source(name, url, s_type="rss"):
    conn = get_db_connection()
    cursor = conn.cursor()
    success = False
    try:
        cursor.execute("INSERT INTO sources (name, url, type) VALUES (?, ?, ?)", (name, url, s_type))
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        print(f"Source URL already exists: {url}")
    conn.close()
    return success

def delete_source(source_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sources WHERE id = ? AND type != 'built-in'", (source_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def is_job_sent(job_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM sent_jobs WHERE job_id = ?", (job_id,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def mark_job_as_sent(job_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT OR IGNORE INTO sent_jobs (job_id) VALUES (?)", (job_id,))
        conn.commit()
    except Exception as e:
        print(f"Error marking job as sent: {e}")
    conn.close()

def get_user_state(chat_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT state FROM user_states WHERE chat_id = ?", (chat_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row["state"]
    return "normal"

def set_user_state(chat_id, state):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO user_states (chat_id, state) VALUES (?, ?)", (chat_id, state))
    conn.commit()
    conn.close()

def prune_sent_jobs(keep_count=500):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        DELETE FROM sent_jobs 
        WHERE job_id NOT IN (
            SELECT job_id FROM sent_jobs 
            ORDER BY sent_at DESC 
            LIMIT ?
        )
    """, (keep_count,))
    
    # Prune jobs table
    cursor.execute("""
        DELETE FROM jobs 
        WHERE id NOT IN (
            SELECT id FROM jobs 
            ORDER BY created_at DESC 
            LIMIT ?
        )
    """, (keep_count,))
    
    conn.commit()
    conn.close()

def get_agencies_by_type(agency_type):
    conn = get_db_connection()
    cursor = conn.cursor()
    if agency_type == "cruise":
        cursor.execute("SELECT name, license_no, type, address, contact, website, created_at FROM agencies WHERE type LIKE '%Kapal Pesiar%'")
    elif agency_type == "landbase":
        cursor.execute("SELECT name, license_no, type, address, contact, website, created_at FROM agencies WHERE type LIKE '%Landbase%'")
    else:
        cursor.execute("SELECT name, license_no, type, address, contact, website, created_at FROM agencies")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_agencies_by_location(loc_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name, license_no, type, address, contact, website, created_at 
        FROM agencies 
        WHERE address LIKE ? 
        ORDER BY name ASC
    """, (f"%{loc_name}%",))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_agencies():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, license_no, type, address, contact, website, created_at FROM agencies ORDER BY name ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def add_agency(name, license_no, agency_type, address="", contact="", website=""):
    conn = get_db_connection()
    cursor = conn.cursor()
    success = False
    try:
        cursor.execute("""
            INSERT INTO agencies (name, license_no, type, address, contact, website, created_at) 
            VALUES (?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
        """, (name, license_no, agency_type, address, contact, website))
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        print(f"Agency already exists: {name}")
    conn.close()
    return success

def delete_agency(agency_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM agencies WHERE id = ?", (agency_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def save_job(job):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT OR REPLACE INTO jobs (id, position, vessel_type, salary, join_date, duration, company, link)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (job["id"], job["position"], job["vessel_type"], job["salary"], job["join_date"], job["duration"], job["company"], job["link"]))
        conn.commit()
    except Exception as e:
        print(f"Error saving job: {e}")
    conn.close()

def search_jobs(query_str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT position, vessel_type, salary, join_date, duration, company, link 
        FROM jobs 
        WHERE position LIKE ? OR company LIKE ? OR vessel_type LIKE ?
        ORDER BY created_at DESC 
        LIMIT 10
    """, (f"%{query_str}%", f"%{query_str}%", f"%{query_str}%"))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_jobs_by_keywords(keywords):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query_parts = []
    params = []
    for kw in keywords:
        query_parts.append("position LIKE ? OR vessel_type LIKE ?")
        params.extend([f"%{kw}%", f"%{kw}%"])
        
    where_clause = " OR ".join(query_parts)
    sql = f"""
        SELECT position, vessel_type, salary, join_date, duration, company, link 
        FROM jobs 
        WHERE {where_clause} 
        ORDER BY created_at DESC 
        LIMIT 10
    """
    
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def subscribe_user(chat_id, category):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO subscribers (chat_id, category) VALUES (?, ?)", (chat_id, category))
    conn.commit()
    conn.close()

def unsubscribe_user(chat_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM subscribers WHERE chat_id = ?", (chat_id,))
    conn.commit()
    conn.close()

def get_subscribers_by_category(category):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT chat_id, category FROM subscribers")
    rows = cursor.fetchall()
    conn.close()
    
    matching_chat_ids = []
    for row in rows:
        user_cat = row["category"]
        if not user_cat:
            continue
        user_cats = [c.strip() for c in user_cat.split(",") if c.strip()]
        if "all" in user_cats or category in user_cats:
            matching_chat_ids.append(row["chat_id"])
    return matching_chat_ids

def get_user_subscription(chat_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT category FROM subscribers WHERE chat_id = ?", (chat_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row["category"]
    return None

def get_stats():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM jobs")
    total_jobs = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM agencies")
    total_agencies = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM subscribers")
    total_subscribers = cursor.fetchone()[0]
    
    conn.close()
    return {
        "total_jobs": total_jobs,
        "total_agencies": total_agencies,
        "total_subscribers": total_subscribers
    }

def sync_default_agencies():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM agencies")
    
    for name, lic, a_type, addr, cont, web in DEFAULT_AGENCIES:
        cursor.execute("""
            INSERT INTO agencies (name, license_no, type, address, contact, website, created_at) 
            VALUES (?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
        """, (name, lic, a_type, addr, cont, web))
        
    conn.commit()
    
    cursor.execute("SELECT COUNT(*) FROM agencies")
    after = cursor.fetchone()[0]
    
    conn.close()
    return after

def clear_all_jobs():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM jobs")
    cursor.execute("DELETE FROM sent_jobs")
    conn.commit()
    conn.close()
    return True
