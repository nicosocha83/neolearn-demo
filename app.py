import streamlit as st
import google.generativeai as genai
import sqlite3
import hashlib
import time
import os

# --- 1. KONFIGURATION & MODEL ---
MODEL_NAME = 'gemini-2.0-flash-001'

# Wir versuchen, den Key aus dem Tresor (Secrets) zu holen
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except:
    # Falls wir lokal testen und keine secrets.toml haben, meckern wir, 
    # aber wir schreiben den Key NICHT hier rein für GitHub!
    st.error("Kein API Key gefunden! Bitte in st.secrets eintragen.")
    # Nur wenn du lokal testest, kannst du ihn hier kurz reinmachen, 
    # aber VOR DEM UPLOAD wieder rauslöschen!
    API_KEY = ""

st.set_page_config(
    page_title="NEO-LEARN", 
    layout="wide", 
    page_icon="🎓", 
    initial_sidebar_state="expanded"
)

# --- 2. CSS (Nur Kosmetik, kein Layout-Hacking) ---
st.markdown("""
<style>
    /* Generelles Aussehen */
    .stApp {
        background-color: #f8fafc;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    
    /* Header & Footer verstecken für App-Look */
    header[data-testid="stHeader"] {background-color: transparent;}
    footer {visibility: hidden;}
    #MainMenu {visibility: hidden;}
    div[data-testid="stDecoration"] {visibility: hidden;}

    /* Chat Bubbles schön machen */
    .stChatMessage {
        background-color: white;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 15px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.02);
    }
    
    /* User Nachricht blau einfärben */
    div[data-testid="chatAvatarIcon-user"] + div {
        background-color: #eff6ff;
        border-color: #bfdbfe;
    }

    /* Buttons modernisieren */
    .stButton button {
        border-radius: 6px;
        border: 1px solid #cbd5e1;
        background-color: white;
        color: #334155;
    }
    button[kind="primary"] {
        background-color: #2563eb !important;
        color: white !important;
        border: none !important;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. DATENBANK (Unverändert) ---
def init_db():
    conn = sqlite3.connect('lernen.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password_hash TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS progress (user_id TEXT, topic TEXT, passed BOOLEAN, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS topics (title TEXT PRIMARY KEY, prompt TEXT)''')
    
    c.execute('SELECT count(*) FROM topics')
    if c.fetchone()[0] == 0:
        default_prompts = [
            ("Python Grundlagen", "Du bist ein Python-Lehrer. Erkläre einfach. Nach 2 Fragen starte Quiz. Wenn richtig, antworte NUR mit JSON: {'status': 'passed'}"),
            ("Online Marketing", "Du bist Marketing-Profi. Prüfe Wissen nach 2 Fragen. Wenn richtig, antworte NUR mit JSON: {'status': 'passed'}")
        ]
        c.executemany('INSERT INTO topics VALUES (?,?)', default_prompts)
        conn.commit()
    conn.commit()
    conn.close()

def make_hash(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def register_user(username, password):
    conn = sqlite3.connect('lernen.db')
    c = conn.cursor()
    try:
        c.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', (username, make_hash(password)))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def login_user(username, password):
    conn = sqlite3.connect('lernen.db')
    c = conn.cursor()
    c.execute('SELECT password_hash FROM users WHERE username = ?', (username,))
    data = c.fetchone()
    conn.close()
    if data and data[0] == make_hash(password): return True
    return False

def get_all_topics():
    conn = sqlite3.connect('lernen.db')
    c = conn.cursor()
    c.execute('SELECT title, prompt FROM topics')
    data = c.fetchall()
    conn.close()
    return {title: prompt for title, prompt in data}

def add_new_topic(title, prompt):
    conn = sqlite3.connect('lernen.db')
    c = conn.cursor()
    try:
        c.execute('INSERT INTO topics VALUES (?,?)', (title, prompt))
        conn.commit()
        return True
    except:
        return False
    finally:
        conn.close()

def delete_topic(title):
    conn = sqlite3.connect('lernen.db')
    c = conn.cursor()
    c.execute('DELETE FROM topics WHERE title = ?', (title,))
    conn.commit()
    conn.close()

def save_progress(user_id, topic):
    conn = sqlite3.connect('lernen.db')
    c = conn.cursor()
    c.execute('INSERT INTO progress (user_id, topic, passed) VALUES (?, ?, ?)', (user_id, topic, True))
    conn.commit()
    conn.close()

def is_topic_passed(user_id, topic):
    conn = sqlite3.connect('lernen.db')
    c = conn.cursor()
    c.execute('SELECT passed FROM progress WHERE user_id = ? AND topic = ?', (user_id, topic))
    result = c.fetchone()
    conn.close()
    return result is not None

init_db()

# --- 4. LOGIN SCREEN ---
if "user_id" not in st.session_state: st.session_state.user_id = None

if st.session_state.user_id is None:
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    
    col_main_1, col_main_2, col_main_3 = st.columns([1, 1.5, 1])
    
    with col_main_2:
        st.markdown("<h1 style='text-align: center; color:#2563eb;'>🚀 NEO-LEARN</h1>", unsafe_allow_html=True)
        
        with st.container(border=True):
            tab1, tab2 = st.tabs(["Einloggen", "Registrieren"])
            
            with tab1:
                l_user = st.text_input("Username", key="l_user")
                l_pass = st.text_input("Passwort", type="password", key="l_pass")
                if st.button("Anmelden", type="primary", use_container_width=True):
                    if login_user(l_user, l_pass):
                        st.session_state.user_id = l_user
                        st.rerun()
                    else:
                        st.error("Login fehlgeschlagen.")
            
            with tab2:
                r_user = st.text_input("Wunsch-Username", key="r_user")
                r_pass = st.text_input("Passwort", type="password", key="r_pass")
                if st.button("Kostenlos Registrieren", use_container_width=True):
                    if register_user(r_user, r_pass):
                        st.success("Account erstellt! Bitte einloggen.")
                    else:
                        st.error("Username vergeben.")
    st.stop()

# --- 5. HAUPT APP ---
CURRENT_USER = st.session_state.user_id
TOPICS = get_all_topics()

try:
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel(MODEL_NAME)
except:
    st.error("API Error")

# SIDEBAR (Standard Streamlit - Stabil)
with st.sidebar:
    st.markdown(f"### 👋 Hallo, {CURRENT_USER}")
    st.markdown("---")
    
    # ADMIN
    if CURRENT_USER == "admin":
        with st.expander("🛠 Admin Werkzeuge"):
            st.markdown("##### Neues Thema")
            new_title = st.text_input("Titel", key="adm_title")
            def_instr = '... antworte NUR mit JSON: {"status": "passed"}'
            new_prompt = st.text_area("Prompt", value=def_instr, height=100)
            if st.button("Speichern"):
                if add_new_topic(new_title, new_prompt):
                    st.success("Gespeichert")
                    time.sleep(1)
                    st.rerun()
            
            st.markdown("##### Löschen")
            if TOPICS:
                d_t = st.selectbox("Wähle Thema", list(TOPICS.keys()))
                if st.button("Löschen"):
                    delete_topic(d_t)
                    st.rerun()
        st.markdown("---")

    # NAVIGATION
    topic_options = []
    sorted_topics = sorted(list(TOPICS.keys()))
    
    for t in sorted_topics:
        icon = "✅" if is_topic_passed(CURRENT_USER, t) else "⭕"
        topic_options.append(f"{icon} {t}")
        
    if not topic_options:
        st.warning("Keine Themen verfügbar.")
        st.stop()
    else:
        # Hier triggern wir einen vollen Reload wenn das Thema gewechselt wird
        selected_label = st.radio("Kurs wählen:", topic_options)
        selected_topic = selected_label.split(" ", 1)[1]

    st.markdown("---")
    if st.button("🔒 Ausloggen", use_container_width=True):
        st.session_state.user_id = None
        st.session_state.messages = []
        if "show_balloons" in st.session_state: del st.session_state.show_balloons
        st.rerun()
        
    if st.button("🗑 Chat Reset", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# MAIN CONTENT
st.title(f"{selected_topic}")

if "messages" not in st.session_state: st.session_state.messages = []
if "curr_topic" not in st.session_state: st.session_state.curr_topic = selected_topic
if st.session_state.curr_topic != selected_topic:
    st.session_state.messages = []
    st.session_state.curr_topic = selected_topic

already_passed = is_topic_passed(CURRENT_USER, selected_topic)

if "show_balloons" in st.session_state and st.session_state.show_balloons:
    st.balloons()
    st.success("🎉 Herzlichen Glückwunsch! Modul erfolgreich bestanden.")
    st.session_state.show_balloons = False
elif already_passed:
    st.info("🏆 Du hast diesen Kurs bereits erfolgreich abgeschlossen.")

# --- HIER IST DIE MAGIE: ST.FRAGMENT ---
# Das sorgt dafür, dass sich nur dieser Teil aktualisiert beim Chatten.
# Der Rest der Seite bleibt ruhig stehen.
@st.fragment
def chat_interface():
    # Chat History
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # Input
    user_input = st.chat_input("Was möchtest du lernen?")

    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.write(user_input)

        with st.chat_message("assistant"):
            try:
                sys_prompt = TOPICS[selected_topic]
                history = [{"role": "user" if m["role"]=="user" else "model", "parts": m["content"]} for m in st.session_state.messages]
                
                chat = model.start_chat(history=history[:-1])
                response = chat.send_message(f"SYSTEM: {sys_prompt}\nUSER: {user_input}")
                
                clean_res = response.text.replace(" ", "").replace("\n", "")
                
                if '"status":"passed"' in clean_res:
                    if not already_passed: save_progress(CURRENT_USER, selected_topic)
                    # Hier brauchen wir einen vollen Rerun für die Ballons (außerhalb des Fragments)
                    st.session_state.show_balloons = True
                    st.rerun()
                else:
                    st.write(response.text)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
            except Exception as e:
                st.error(f"Verbindungsfehler: {e}")

# Funktionsaufruf
chat_interface()