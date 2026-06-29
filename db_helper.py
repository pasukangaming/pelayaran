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
        
    # Populate default built-in sources
    default_sources = [
        ("Crewell", "https://crewell.net/en/vacancies/", "built-in"),
        ("JobMarineMan", "https://jobmarineman.com/vacancies/", "built-in"),
        ("Profesea", "https://profesea.id/", "built-in"),
        ("Maersk Careers", "https://www.maersk.com/careers/vacancies", "built-in"),
        ("MSC Careers", "https://www.msc.com/en/careers", "built-in"),
        ("CMA CGM Careers", "https://www.cmacgm-group.com/en/careers", "built-in"),
        ("Hapag-Lloyd Careers", "https://www.hapag-lloyd.com/en/company/careers/jobs.html", "built-in"),
        ("V.Group Careers", "https://vgrouplimited.com/careers/", "built-in"),
        ("Wilhelmsen Careers", "https://www.wilhelmsen.com/careers/", "built-in"),
        ("Bernhard Schulte Shipmanagement", "https://www.bs-shipmanagement.com/en/careers", "built-in"),
        ("Anglo-Eastern Careers", "https://www.angloeastern.com/careers", "built-in"),
        ("Synergy Marine Group", "https://www.synergymarinegroup.com/careers/", "built-in"),
        ("Columbia Shipmanagement", "https://www.columbia-shipmanagement.com/careers/", "built-in"),
        ("Fleet Management Limited", "https://www.fleetship.com/careers/", "built-in"),
        ("Wallem Careers", "https://www.wallem.com/careers", "built-in"),
        ("OSM Thome Careers", "https://www.osmthome.com/careers/", "built-in"),
        ("Marlow Navigation", "https://marlow-navigation.com/en/careers.asp", "built-in"),
        ("Crowley Careers", "https://www.crowley.com/careers/", "built-in"),
        ("Teekay Careers", "https://www.teekay.com/careers/", "built-in"),
        ("NYK Line Careers", "https://www.nyk.com/english/recruit/", "built-in"),
        ("MOL Careers", "https://www.mol.co.jp/en/recruit/", "built-in"),
        ("Evergreen Marine", "https://www.evergreen-marine.com/career/", "built-in"),
        ("Wallenius Wilhelmsen", "https://www.walleniuswilhelmsen.com/careers", "built-in"),
        ("Euronav Careers", "https://www.euronav.com/en/careers/", "built-in"),
        ("Bourbon Offshore", "https://www.bourbonoffshore.com/en/careers", "built-in"),
        ("Tidewater Careers", "https://www.tdw.com/careers/", "built-in"),
        ("Solstad Offshore", "https://www.solstad.no/careers/", "built-in"),
        ("Boskalis Careers", "https://www.boskalis.com/careers.html", "built-in"),
        ("Van Oord Careers", "https://www.vanoord.com/en/careers/", "built-in"),
        ("DEME Group Careers", "https://www.deme-group.com/careers", "built-in"),
        ("Jan De Nul Careers", "https://www.jandenul.com/careers", "built-in"),
        ("Seatrade Careers", "https://www.seatrade.com/careers/", "built-in"),
        ("Wintermar Careers", "https://www.wintermar.com/careers/", "built-in"),
        ("Soechi Lines", "https://www.soechi.com/career.html", "built-in"),
        ("Samudera Indonesia", "https://samudera.id/career/", "built-in"),
        ("Temas Line", "https://www.temasline.com/career", "built-in"),
        ("Meratus Line", "https://www.meratusline.com/careers", "built-in"),
        ("SPIL Careers", "https://www.spil.co.id/career", "built-in"),
        ("Pelni Careers", "https://rekrutmen.pelni.co.id/", "built-in"),
        ("ASDP Indonesia Ferry", "https://rekrutmen.indonesiaferry.co.id/", "built-in"),
        ("Pertamina International Shipping", "https://pertamina-pis.com/career", "built-in"),
        ("Transcoal Pacific", "http://www.transcoalpacific.com/career", "built-in"),
        ("Logindo Samudramakmur", "http://www.logindo.co.id/career", "built-in"),
        ("Buana Lintas Lautan", "https://www.bll.co.id/careers/", "built-in"),
        ("Humpuss Intermoda", "https://www.humpussintermoda.co.id/career", "built-in"),
        ("Gurita Lintas Samudera", "https://www.gls.co.id/career", "built-in"),
        ("Kartika Samudra Adijaya", "https://www.ksa.co.id/careers", "built-in"),
        ("Indo Tambangraya Megah", "https://www.itmg.co.id/careers", "built-in"),
        ("Arpeni Pratama Ocean Line", "https://www.arpeni.com/career", "built-in"),
        ("Habco Trans Maritima", "https://www.habco.co.id/careers", "built-in"),
        ("Pelayaran Nelly Dwi Putri", "http://www.nelly.co.id/career.html", "built-in"),
        ("Pelayaran Nasional Bina Buana Raya", "https://www.binabuanaraya.co.id/career", "built-in"),
        ("Temas Shipping", "https://www.temasshipping.co.id/careers", "built-in"),
        ("Pelayaran Tempuran Emas", "https://www.temasline.com/career", "built-in")
    ]
    
    for name, url, s_type in default_sources:
        cursor.execute("INSERT OR IGNORE INTO sources (name, url, type) VALUES (?, ?, ?)", (name, url, s_type))
        
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

# Cleanup function to keep database size bounded
def prune_sent_jobs(keep_count=500):
    conn = get_db_connection()
    cursor = conn.cursor()
    # Delete oldest jobs keeping only the most recent keep_count
    cursor.execute("""
        DELETE FROM sent_jobs 
        WHERE job_id NOT IN (
            SELECT job_id FROM sent_jobs 
            ORDER BY sent_at DESC 
            LIMIT ?
        )
    """, (keep_count,))
    conn.commit()
    conn.close()
