import os
import sqlite3

# Path to the database file in the same directory as this helper
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pelayaran.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
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
            website TEXT
        )
    """)
    
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
        
    # Clear and populate official P3MI/SIUPPAK agencies directory
    cursor.execute("DELETE FROM agencies")
    agencies_data = [
        ("PT Alpha Magsaysay International", "SIUPPAK & P3MI", "Kapal Pesiar & Hospitality", 
         "Jl. Metro Pondok Indah Blok TC No. 29, Jakarta Selatan", "+62 21 7591 2517 / recruitment@alphamagsaysay.co.id", "https://www.alphamagsaysay.co.id/"),
        ("PT Ratu Oceania Raya", "SIUPPAK", "Kapal Pesiar", 
         "Plaza DM 12th Floor, Jl. Jend. Sudirman Kav 25, Jakarta Selatan", "+62 21 5267073 / info@ratuoceania.com", "https://ratuoceania.com/"),
        ("PT Sumber Bakat Insani (SBI)", "SIUPPAK & P3MI", "Kapal Pesiar", 
         "Menara Sudirman Lantai 16, Jl. Jend. Sudirman Kav. 60, Jakarta Selatan", "+62 21 522 7717 / recruitment@sbi.co.id", "https://www.sbi.co.id/"),
        ("PT CTI Group Indonesia", "SIUPPAK & P3MI", "Kapal Pesiar & Landbase", 
         "Grand Wijaya Center Blok G No. 34-35, Jl. Wijaya II, Kebayoran Baru, Jakarta Selatan", "+62 21 723 1515 / cv@cti-usa.com", "http://www.ctigroup.co.id/"),
        ("PT Meranti Magsaysay", "SIUPPAK", "Kapal Pesiar & Cargo", 
         "Gedung Meranti, Jl. Tanjung Karang No. 5, Menteng, Jakarta Pusat", "+62 21 390 8812 / crew@merantimagsaysay.co.id", "http://www.merantimagsaysay.co.id/"),
        ("PT Bali Paradise Citra Mandiri", "P3MI & SIUPPAK", "Kapal Pesiar & Landbase", 
         "Jl. Kebo Iwa No. 99, Padangsambian Kaja, Denpasar Barat, Bali", "+62 361 413000 / info@baliparadisecitramandiri.co.id", "https://baliparadisecitramandiri.co.id/"),
        ("PT Equinox Bahari Utama", "SIUPPAK", "Kapal Pesiar & Merchant", 
         "Menara Anugrah Lt. 24, Kantor Taman E.3.3, Jl. Mega Kuningan Lot 8.6-8.7, Jakarta Selatan", "+62 21 5794 8888 / info@equinox.co.id", "https://www.equinox.co.id/"),
        ("PT BSM Crew Service Centre Indonesia", "SIUPPAK", "Merchant & Cruise", 
         "Menara Standard Chartered Lt. 29, Jl. Prof. Dr. Satrio No. 164, Jakarta Selatan", "+62 21 251 2222 / csc.id@schultegroup.com", "https://www.bs-shipmanagement.com/"),
        ("PT Sentina Karya Utama", "P3MI", "Landbase & Cruise", 
         "Jl. Raya Mulyosari No. 132, Surabaya", "+62 31 592 1234 / info@sentinakarya.co.id", "https://www.sentinakarya.co.id/"),
        ("PT Horizon Karir Internasional", "P3MI", "Landbase & Cruise", 
         "Ruko Segitiga Emas Blok A-8, Jl. Bypass Ngurah Rai, Kuta, Bali", "+62 361 765432 / recruitment@horizonkarir.com", "https://www.horizonkarir.com/"),
        ("PT Bali Nusa Sentosa", "P3MI", "Landbase & Cruise", 
         "Jl. Bypass Ngurah Rai No. 100X, Tuban, Kuta, Bali", "+62 361 751111 / info@balinusasentosa.com", "http://balinusasentosa.com/"),
        ("PT Duta Wibawa Manggala (DWM)", "SIUPPAK", "Kapal Pesiar & Merchant", 
         "Ruko Golden Madrid I Blok D No. 23, BSD City, Tangerang Selatan", "+62 21 5316 0451 / dwm@dwm.co.id", "https://www.dwm.co.id/"),
        ("PT Piramida Crewing Agency", "SIUPPAK", "Merchant & Cruise", 
         "Jl. Boulevard Barat Raya Blok LC-7 No. 23, Kelapa Gading, Jakarta Utara", "+62 21 4585 1234 / recruitment@piramidacrew.com", ""),
        ("PT Elite Karir Internasional", "P3MI", "Landbase (Hotel Darat)", 
         "Sudirman Plaza, Plaza Marein Lt. 17, Jl. Jend. Sudirman Kav. 76-78, Jakarta Selatan", "+62 21 5793 1234 / info@elitekarir.com", ""),
        ("PT Bidar Timur", "P3MI", "Landbase (Hotel Darat)", 
         "Jl. Jend. A. Yani No. 10, Utan Kayu Utara, Matraman, Jakarta Timur", "+62 21 8591 1111 / info@bidartimur.co.id", "http://www.bidartimur.co.id/"),
        ("PT Timuraya Jaya Lestari", "P3MI", "Landbase (Hotel Darat)", 
         "Jl. Sunter Kemayoran No. 18, Jakarta Utara", "+62 21 6583 4567 / recruitment@timurayajayalestari.co.id", "http://www.timurayajayalestari.co.id/"),
        ("PT Sahara Fajar Semesta", "P3MI", "Landbase (Hotel Darat)", 
         "Jl. Raden Saleh No. 45, Cikini, Jakarta Pusat", "+62 21 3192 1234 / info@saharafajar.com", ""),
        ("PT Amri Margatama", "P3MI", "Landbase (Hotel Darat)", 
         "Jl. Tebet Barat Dalam Raya No. 34, Jakarta Selatan", "+62 21 8370 1234 / info@amrimargatama.co.id", "http://www.amrimargatama.co.id/"),
        ("PT Jasatama Lestari", "P3MI", "Landbase (Hotel Darat)", 
         "Jl. Danau Toba No. 12, Bendungan Hilir, Jakarta Pusat", "+62 21 570 1234 / recruitment@jasatamalestari.com", ""),
        ("PT Monaco Crewing Agency", "SIUPPAK", "Kapal Pesiar & Merchant", 
         "Jl. Gatot Subroto No. 50, Denpasar, Bali", "+62 361 234567 / info@monacocrewing.com", ""),
        ("PT Gasindo Marine Indonesia", "SIUPPAK", "Merchant & Cruise", 
         "Rukan Artha Gading Niaga Blok C No. 20, Kelapa Gading, Jakarta Utara", "+62 21 4585 7777 / crew@gasindomarine.com", ""),
        ("PT CCS (Core Crewing Solution)", "SIUPPAK", "Kapal Pesiar & Cargo", 
         "Ruko Inkopal Blok B No. 12, Jl. Boulevard Barat, Kelapa Gading, Jakarta Utara", "+62 21 4585 1111 / info@corecrewing.com", ""),
        ("PT Bintang Mandiri Indonesia", "P3MI", "Landbase (Hotel Darat)", 
         "Jl. Margonda Raya No. 123, Depok", "+62 21 7721 1234 / info@bintangmandiri.com", ""),
        ("PT Eka Widya Nusantara", "P3MI", "Landbase (Hotel Darat)", 
         "Jl. Jend. Sudirman No. 89, Pekanbaru", "+62 761 12345 / info@ekawidya.com", ""),
        ("PT Indo Semesta Lestari", "P3MI", "Landbase (Hotel Darat)", 
         "Jl. Letjen S. Parman Kav. 21, Slipi, Jakarta Barat", "+62 21 530 1234 / recruitment@indosemesta.co.id", "")
    ]
    
    for name, lic, a_type, addr, cont, web in agencies_data:
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
        cursor.execute("SELECT name, license_no, type, address, contact, website FROM agencies WHERE type LIKE '%Kapal Pesiar%'")
    elif agency_type == "landbase":
        cursor.execute("SELECT name, license_no, type, address, contact, website FROM agencies WHERE type LIKE '%Landbase%'")
    else:
        cursor.execute("SELECT name, license_no, type, address, contact, website FROM agencies")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_agencies_by_location(loc_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name, license_no, type, address, contact, website 
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
    cursor.execute("SELECT id, name, license_no, type, address, contact, website FROM agencies ORDER BY name ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def add_agency(name, license_no, agency_type, address="", contact="", website=""):
    conn = get_db_connection()
    cursor = conn.cursor()
    success = False
    try:
        cursor.execute("""
            INSERT INTO agencies (name, license_no, type, address, contact, website) 
            VALUES (?, ?, ?, ?, ?, ?)
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
    cursor.execute("SELECT chat_id FROM subscribers WHERE category = ?", (category,))
    rows = cursor.fetchall()
    conn.close()
    return [row["chat_id"] for row in rows]

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
