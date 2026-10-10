import http.server
import socketserver
import json
import urllib.parse
import urllib.request
from http import cookies
import os
import uuid
import threading
import re
import sys
import platform
import string
import time
import datetime
import csv
import io
from cryptography.fernet import Fernet

PORT = 8000
UPLOAD_DIR = "uploads"
ENCRYPTED_CSV_FILE = "accounts_encrypted.csv"
LOGIN_LOGS_CSV = "login_logs.csv"
SESSIONS = {}
BOARD_CACHE = "[]"
CACHE_LOCK = threading.Lock()
CHAT_HISTORIES = {}

# Retrieve the secret decryption key from environment variables (GitHub Secrets / Render / Local)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AQ.Ab8RN6J-yO8rxDJAcCcM7EHM2_c_POYdGhFoNmetjTi6vue-2A")
CSV_ENCRYPTION_KEY = os.environ.get("CSV_ENCRYPTION_KEY", "HwHL7WMhRl65vW16Ax958ilVyBGvjwKNrWL7_uN5tZU=")

GRADES = ["PRKG", "LKG", "UKG"] + [f"{i}th" for i in range(1, 11)]
SECTIONS = ["A", "B", "C", "D", "E", "F", "G"]

def ensure_file_manager_structure():
    if not os.path.exists(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR)
    for g in GRADES:
        for s in SECTIONS:
            folder_path = os.path.join(UPLOAD_DIR, g, s)
            if not os.path.exists(folder_path):
                os.makedirs(folder_path)

ensure_file_manager_structure()

# --- ENCRYPTED CSV DATABASE & LOGGING MANAGEMENT ---
def get_fernet():
    """Initializes and returns the Fernet encryption instance."""
    if not CSV_ENCRYPTION_KEY:
        # Fallback default key for local development if environment variable isn't set yet
        return Fernet(b'VlD8h2tEiJkQpKKnDNKnu8ya2fpIBMOo5oc7JKNasvk=')
    return Fernet(CSV_ENCRYPTION_KEY.encode())

def init_encrypted_csv():
    """Initializes accounts_encrypted.csv with an empty structure (headers only) if it does not exist."""
    if not os.path.exists(ENCRYPTED_CSV_FILE):
        # Save an empty dictionary so the encrypted file is created securely with headers only
        save_users_to_encrypted_csv({})

def load_users_from_encrypted_csv():
    """Decrypts accounts_encrypted.csv in memory and loads all user credentials."""
    users = {}
    if os.path.exists(ENCRYPTED_CSV_FILE):
        try:
            fernet = get_fernet()
            with open(ENCRYPTED_CSV_FILE, "rb") as enc_file:
                encrypted_bytes = enc_file.read()
            
            decrypted_bytes = fernet.decrypt(encrypted_bytes)
            decoded_text = decrypted_bytes.decode('utf-8')
            reader = csv.reader(io.StringIO(decoded_text))
            
            # Skip header row: Username, Password, Role, Grade, Section
            header = next(reader, None)
            
            for row in reader:
                if row and len(row) >= 5:
                    username = row[0].strip()
                    users[username] = {
                        "password": row[1].strip(),
                        "role": row[2].strip(),
                        "grade": row[3].strip(),
                        "section": row[4].strip()
                    }
        except Exception as e:
            print(f"❌ Decryption/Loading failed: {str(e)}")
    return users

def save_users_to_encrypted_csv(users_dict):
    """Takes the complete users dictionary, formats to CSV, encrypts, and saves to disk."""
    try:
        fernet = get_fernet()
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write Header
        writer.writerow(["Username", "Password", "Role", "Grade", "Section"])
        
        # Write User Rows
        for username, data in users_dict.items():
            writer.writerow([
                username,
                data["password"],
                data["role"],
                data.get("grade", "10th"),
                data.get("section", "A")
            ])
            
        csv_text = output.getvalue()
        encrypted_bytes = fernet.encrypt(csv_text.encode('utf-8'))
        
        with open(ENCRYPTED_CSV_FILE, "wb") as enc_file:
            enc_file.write(encrypted_bytes)
        return True
    except Exception as e:
        print(f"❌ Encryption/Saving failed: {str(e)}")
        return False

init_encrypted_csv()

def log_login_event(username, role, grade, section, auth_method):
    """Logs login activity to login_logs.csv audit trail."""
    file_exists = os.path.exists(LOGIN_LOGS_CSV)
    with open(LOGIN_LOGS_CSV, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Timestamp", "Username", "Role", "Grade", "Section", "Auth Method"])
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        writer.writerow([timestamp, username, role, grade, section, auth_method])

ADMIN_KEYS = {
    "9080-3456-7890-3456-7280-4562-8729-RJU-2013-2810-4568-6573": {
        "email": "juraghav@gmail.com",
        "name": "System Administrator",
        "photo_url": ""
    },
    "admin-secret-key-12345": {
        "email": "leadadmin@Digiboardleaning.com",
        "name": "Lead Admin",
        "photo_url": ""
    }
}

LOGIN_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>DigiBoard - Login</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #070d19; color: #f8fafc; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .login-card { background: #0f172a; border: 1px solid #1e293b; padding: 2.5rem; border-radius: 12px; width: 380px; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.6); }
        h2 { text-align: center; margin-top: 0; color: #38bdf8; font-size: 1.5rem; }
        label { font-size: 0.85rem; color: #94a3b8; display: block; margin-top: 1rem; }
        input { width: 100%; padding: 0.65rem; margin-top: 0.3rem; border: 1px solid #334155; background: #070d19; color: #fff; border-radius: 6px; box-sizing: border-box; }
        input:focus { outline: none; border-color: #38bdf8; }
        button { width: 100%; padding: 0.75rem; margin-top: 1.2rem; background: #0284c7; border: none; color: white; border-radius: 6px; font-weight: bold; cursor: pointer; transition: background 0.2s; }
        button:hover { background: #0369a1; }
        .admin-btn { background: #4f46e5; margin-top: 0.75rem; }
        .admin-btn:hover { background: #4338ca; }
        .error { color: #ef4444; font-size: 0.875rem; text-align: center; margin-bottom: 1rem; background: rgba(239, 68, 68, 0.1); padding: 0.5rem; border-radius: 4px; }
        .divider { border-top: 1px solid #1e293b; margin: 1.5rem 0 0.5rem 0; text-align: center; position: relative; }
    </style>
</head>
<body>
    <div class="login-card">
        <h2>DigiBoard Master Console</h2>
        <!--ERROR-->
        <form action="/login" method="POST">
            <label>Username</label>
            <input type="text" name="username" placeholder="user@domain.com" required>
            <label>Password</label>
            <input type="password" name="password" required>
            <button type="submit">Sign In</button>
        </form>

        <div class="divider"></div>
        <form action="/login-admin" method="POST">
            <label>Admin SSH Key ID</label>
            <input type="password" name="admin_key" placeholder="Enter Authorized SSH Key ID..." required>
            <button type="submit" class="admin-btn">🔑 Authenticate Admin Mode</button>
        </form>
    </div>
</body>
</html>"""

CONSOLE_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>DigiBoard Master Console</title>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        * { box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #050a14; color: #f8fafc; margin: 0; padding: 0; height: 100vh; display: flex; flex-direction: column; }
        header { display: flex; justify-content: space-between; align-items: center; padding: 1.2rem 2.5rem; border-bottom: 1px solid #111c30; background: #070d19; }
        .header-title { font-size: 1.25rem; font-weight: bold; letter-spacing: 0.5px; color: #ffffff; }
        .user-section { display: flex; align-items: center; gap: 1rem; font-size: 0.875rem; color: #94a3b8; }
        .user-id { color: #ffffff; font-weight: 600; }
        .user-role-badge { background: #1e293b; color: #38bdf8; padding: 0.2rem 0.6rem; border-radius: 4px; font-weight: 600; text-transform: uppercase; font-size: 0.75rem; }
        .admin-badge { background: #4f46e5 !important; color: #fff !important; }
        .logout-btn { background: transparent; border: 1px solid #1e293b; color: #38bdf8; padding: 0.4rem 1rem; border-radius: 4px; cursor: pointer; font-size: 0.85rem; }
        .logout-btn:hover { background: #1e293b; color: #fff; }
        .console-container { flex: 1; display: flex; justify-content: center; align-items: center; padding: 2rem; }
        .grid-wrapper { background: rgba(15, 23, 42, 0.6); border: 1px solid #172554; border-radius: 16px; padding: 2.5rem; display: flex; gap: 2rem; box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5); }
        .app-card { width: 150px; height: 150px; background: #091326; border: 1px solid #1e293b; border-radius: 14px; display: flex; flex-direction: column; justify-content: center; align-items: center; cursor: pointer; transition: all 0.2s ease; gap: 0.85rem; }
        .app-card:hover { transform: translateY(-4px); border-color: #38bdf8; background: #0e1d38; box-shadow: 0 10px 20px -5px rgba(56, 189, 248, 0.2); }
        .app-icon { width: 56px; height: 56px; border-radius: 14px; display: flex; justify-content: center; align-items: center; }
        .icon-wb { background: #2563eb; }
        .icon-ai { background: #8b5cf6; }
        .icon-fm { background: #eab308; }
        .icon-admin { background: #4f46e5; }
        .app-icon svg { width: 30px; height: 30px; fill: white; }
        .app-title { font-size: 0.85rem; font-weight: 600; color: #cbd5e1; text-align: center; }
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(3, 7, 18, 0.9); justify-content: center; align-items: center; z-index: 100; }
        .modal-content { background: #0f172a; border: 1px solid #1e293b; border-radius: 12px; width: 95%; max-width: 1150px; height: 88vh; display: flex; flex-direction: column; overflow: hidden; position: relative; }
        .modal-header { display: flex; justify-content: space-between; align-items: center; padding: 1rem 1.5rem; border-bottom: 1px solid #1e293b; background: #070d19; }
        .modal-header h3 { margin: 0; color: #38bdf8; font-size: 1.1rem; }
        .close-btn { color: #94a3b8; font-size: 1.5rem; font-weight: bold; cursor: pointer; line-height: 1; }
        .close-btn:hover { color: #fff; }
        .modal-body { padding: 1rem; overflow: hidden; flex: 1; position: relative; display: flex; flex-direction: column; }
        .admin-form-group { margin-bottom: 1rem; }
        .admin-form-group label { display: block; margin-bottom: 0.3rem; color: #94a3b8; font-size: 0.85rem; }
        .admin-form-group input, .admin-form-group select { width: 100%; padding: 0.5rem; background: #070d19; border: 1px solid #334155; color: white; border-radius: 6px; }
    </style>
</head>
<body>
    <header>
        <div class="header-title">DigiBoard Master Console</div>
        <div class="user-section">
            User ID: <span class="user-id"><!--USERNAME--></span>
            <span class="user-role-badge <!--ADMIN_CLASS-->"><!--USER_ROLE--></span>
            <button class="logout-btn" onclick="window.location.href='/logout'">Logout</button>
        </div>
    </header>

    <div class="console-container">
        <div class="grid-wrapper">
            <div class="app-card" onclick="alert('Interactive Whiteboard Module')">
                <div class="app-icon icon-wb"><svg viewBox="0 0 24 24"><path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg></div>
                <div class="app-title">Interactive WhiteBoard</div>
            </div>

            <div class="app-card" onclick="alert('Gemini AI Assistant Module')">
                <div class="app-icon icon-ai"><svg viewBox="0 0 24 24"><path d="M12 2a2 2 0 0 1 2 2v1a2 2 0 0 1-2 2 2 2 0 0 1-2-2V4a2 2 0 0 1 2-2m8 7a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h16m-12 3a1.5 1.5 0 0 0-1.5 1.5 1.5 1.5 0 0 0 1.5 1.5 1.5 1.5 0 0 0 1.5-1.5A1.5 1.5 0 0 0 8 12m8 0a1.5 1.5 0 0 0-1.5 1.5 1.5 1.5 0 0 0 1.5 1.5 1.5 1.5 0 0 0 1.5-1.5A1.5 1.5 0 0 0 16 12z"/></svg></div>
                <div class="app-title">Gemini AI Assistant</div>
            </div>

            <div class="app-card" onclick="alert('File Manager Module')">
                <div class="app-icon icon-fm"><svg viewBox="0 0 24 24"><path d="M10 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z"/></svg></div>
                <div class="app-title">File Manager</div>
            </div>

            <!--ROLE_ADMIN_ONLY-->
            <div class="app-card" onclick="openApp('admin-modal')">
                <div class="app-icon icon-admin"><svg viewBox="0 0 24 24"><path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-5.45 9-12V5l-9-4zm0 10.99h7c-.53 4.12-3.28 7.79-7 8.94V12H5V6.3l7-3.11v8.8s0 0 0 0z"/></svg></div>
                <div class="app-title">Admin Console</div>
            </div>
            <!--END_ADMIN_ROLE-->
        </div>
    </div>

    <!-- ADMIN MODAL -->
    <!--ROLE_ADMIN_ONLY-->
    <div class="modal" id="admin-modal">
        <div class="modal-content" style="max-width: 800px; height:auto;">
            <div class="modal-header">
                <h3>Admin Management & Provisioning Console</h3>
                <span class="close-btn" onclick="closeApp('admin-modal')">&times;</span>
            </div>
            <div class="modal-body" style="height: 520px; overflow-y: auto;">
                <div style="background:#070d19; padding:1.2rem; border-radius:8px; border:1px solid #1e293b;">
                    <h4 style="margin-top:0; color:#cbd5e1;">Mass Provision Accounts & Class Linking (Encrypted CSV)</h4>
                    <form onsubmit="handleMassCreate(event)">
                        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:1rem;">
                            <div class="admin-form-group">
                                <label>Account Role Type</label>
                                <select id="mass-role">
                                    <option value="teacher">Teacher Accounts</option>
                                    <option value="student">Digital Boards / Class Accounts</option>
                                </select>
                            </div>
                            <div class="admin-form-group">
                                <label>Prefix Name (e.g. board / teacher)</label>
                                <input type="text" id="mass-prefix" value="digitalboard" required>
                            </div>
                            <div class="admin-form-group">
                                <label>Link to Grade / Class</label>
                                <select id="mass-grade"><!--GRADES_OPTIONS--></select>
                            </div>
                            <div class="admin-form-group">
                                <label>Link to Section</label>
                                <select id="mass-section"><!--SECTIONS_OPTIONS--></select>
                            </div>
                            <div class="admin-form-group">
                                <label>Number of Accounts</label>
                                <input type="number" id="mass-count" min="1" max="500" value="10" required>
                            </div>
                            <div class="admin-form-group">
                                <label>Default Password</label>
                                <input type="password" id="mass-password" required value="2234269580">
                            </div>
                        </div>
                        <button type="submit" style="width:100%; padding:0.6rem; background:#4f46e5; border:none; color:white; font-weight:bold; border-radius:4px; cursor:pointer;">Generate & Encrypt Batch</button>
                    </form>
                </div>

                <h4 style="margin-top:1.5rem; color:#cbd5e1;">Active System Users (<span id="user-count">0</span>)</h4>
                <div id="users-table-container" style="background:#070d19; border:1px solid #1e293b; border-radius:6px; max-height:180px; overflow-y:auto; padding:0.5rem;"></div>
            </div>
        </div>
    </div>
    <!--END_ADMIN_ROLE-->

    <script>
        const USER_ROLE = "<!--USER_ROLE-->";
        if (USER_ROLE === 'admin') {
            function loadUsers() {
                fetch('/api/admin/users')
                    .then(r => r.json())
                    .then(users => {
                        document.getElementById('user-count').innerText = Object.keys(users).length;
                        let html = '<table style="width:100%; border-collapse:collapse; text-align:left; font-size:0.85rem;">';
                        html += '<tr style="border-bottom:1px solid #334155; color:#94a3b8;"><th>Username</th><th>Role</th><th>Class & Section</th></tr>';
                        for (let u in users) {
                            html += `<tr style="border-bottom:1px solid #1e293b; color:#cbd5e1;"><td style="padding:0.4rem 0;">${u}</td><td><span class="user-role-badge">${users[u].role}</span></td><td>${users[u].grade || 'N/A'} - ${users[u].section || 'N/A'}</td></tr>`;
                        }
                        html += '</table>';
                        document.getElementById('users-table-container').innerHTML = html;
                    });
            }

            function handleMassCreate(e) {
                e.preventDefault();
                const payload = {
                    role: document.getElementById('mass-role').value,
                    prefix: document.getElementById('mass-prefix').value,
                    grade: document.getElementById('mass-grade').value,
                    section: document.getElementById('mass-section').value,
                    count: parseInt(document.getElementById('mass-count').value),
                    password: document.getElementById('mass-password').value
                };
                fetch('/api/admin/mass-create', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                })
                .then(r => r.json())
                .then(res => {
                    alert(`Successfully created ${res.created} accounts saved into encrypted CSV!`);
                    loadUsers();
                });
            }
            setTimeout(loadUsers, 500);
        }
        function openApp(id) { document.getElementById(id).style.display = 'flex'; }
        function closeApp(id) { document.getElementById(id).style.display = 'none'; }
    </script>
</body>
</html>"""

def call_gemini_api_with_history(history_list):
    if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_GEMINI_API_KEY_HERE":
        return "⚠️ Gemini API key is missing."

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    
    system_instruction = {
        "parts": [{
            "text": "You are Gemini, a helpful AI assistant inside DigiBoard."
        }]
    }

    contents = []
    for m in history_list:
        role = "user" if m["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": m["text"]}]})

    payload = {"system_instruction": system_instruction, "contents": contents}

    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers)
        with urllib.request.urlopen(req, timeout=20) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            return res_data['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        return f"Error contacting Gemini API: {str(e)}"

class DigiBoardHandler(http.server.BaseHTTPRequestHandler):

    def set_no_cache_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")

    def get_session(self):
        cookie_header = self.headers.get('Cookie')
        if cookie_header:
            cookie = cookies.SimpleCookie()
            cookie.load(cookie_header)
            if 'session_id' in cookie:
                sid = cookie['session_id'].value
                return SESSIONS.get(sid)
        return None

    def send_html(self, content, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.set_no_cache_headers()
        self.end_headers()
        self.wfile.write(content.encode('utf-8'))

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.set_no_cache_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def redirect(self, location):
        self.send_response(302)
        self.send_header("Location", location)
        self.set_no_cache_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        session = self.get_session()

        if path == "/login":
            self.send_html(LOGIN_HTML.replace("<!--ERROR-->", ""))
            return

        if path == "/logout":
            cookie_header = self.headers.get('Cookie')
            if cookie_header:
                cookie = cookies.SimpleCookie()
                cookie.load(cookie_header)
                if 'session_id' in cookie:
                    sid = cookie['session_id'].value
                    SESSIONS.pop(sid, None)
            self.redirect("/login")
            return

        if path in ("/", "/dashboard"):
            if not session:
                self.redirect("/login")
                return
            
            html = CONSOLE_HTML.replace("<!--USERNAME-->", session['username'])
            html = html.replace("<!--USER_ROLE-->", session['role'])

            grade_opts = "".join([f'<option value="{g}" {"selected" if g == session.get("grade","10th") else ""}>{g}</option>' for g in GRADES])
            sec_opts = "".join([f'<option value="{s}" {"selected" if s == session.get("section","A") else ""}>Section {s}</option>' for s in SECTIONS])
            html = html.replace("<!--GRADES_OPTIONS-->", grade_opts).replace("<!--SECTIONS_OPTIONS-->", sec_opts)
            
            if session['role'] == 'admin':
                html = html.replace("<!--ADMIN_CLASS-->", "admin-badge")
                html = html.replace("<!--ROLE_ADMIN_ONLY-->", "").replace("<!--END_ADMIN_ROLE-->", "")
            else:
                html = html.replace("<!--ADMIN_CLASS-->", "")
                html = re.sub(r'<!--ROLE_ADMIN_ONLY-->.*?<!--END_ADMIN_ROLE-->', '', html, flags=re.DOTALL)
                
            self.send_html(html)
            return

        if path == "/api/admin/users":
            if not session or session.get('role') != 'admin':
                self.send_json({"error": "Forbidden"}, 403)
                return
            users = load_users_from_encrypted_csv()
            self.send_json(users)
            return

        self.send_error(404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/login-admin":
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            params = urllib.parse.parse_qs(body)
            admin_key_entered = params.get('admin_key', [''])[0].strip()

            if admin_key_entered in ADMIN_KEYS:
                admin_info = ADMIN_KEYS[admin_key_entered]
                sid = str(uuid.uuid4())

                SESSIONS[sid] = {
                    "username": admin_info["email"],
                    "role": "admin",
                    "grade": "10th",
                    "section": "A",
                    "key_info": {
                        "name": admin_info["name"],
                        "super_key": admin_key_entered,
                        "photo_url": admin_info["photo_url"]
                    }
                }

                log_login_event(admin_info["email"], "admin", "10th", "A", "Admin SSH Key")

                self.send_response(302)
                self.send_header("Set-Cookie", f"session_id={sid}; Path=/; HttpOnly")
                self.send_header("Location", "/")
                self.set_no_cache_headers()
                self.end_headers()
            else:
                err_html = LOGIN_HTML.replace("<!--ERROR-->", '<div class="error">❌ Unauthorized Key ID!</div>')
                self.send_html(err_html, 401)
            return

        if path == "/login":
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            params = urllib.parse.parse_qs(body)
            username = params.get('username', [''])[0].strip()
            password = params.get('password', [''])[0].strip()

            # LOAD USERS FROM ENCRYPTED CSV
            users = load_users_from_encrypted_csv()

            if username in users and users[username]['password'] == password:
                sid = str(uuid.uuid4())
                user_data = users[username]
                SESSIONS[sid] = {
                    "username": username, 
                    "role": user_data['role'],
                    "grade": user_data.get('grade', '10th'),
                    "section": user_data.get('section', 'A')
                }

                log_login_event(
                    username=username,
                    role=user_data['role'],
                    grade=user_data.get('grade', '10th'),
                    section=user_data.get('section', 'A'),
                    auth_method="Password"
                )

                self.send_response(302)
                self.send_header("Set-Cookie", f"session_id={sid}; Path=/; HttpOnly")
                self.send_header("Location", "/")
                self.set_no_cache_headers()
                self.end_headers()
            else:
                err_html = LOGIN_HTML.replace("<!--ERROR-->", '<div class="error">Invalid username or password</div>')
                self.send_html(err_html, 401)
            return

        session = self.get_session()
        if not session:
            self.send_json({"error": "Unauthorized"}, 401)
            return

        if path == "/api/admin/mass-create":
            if session.get('role') != 'admin':
                self.send_json({"error": "Forbidden"}, 403)
                return
            content_length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(content_length).decode('utf-8'))
            
            role = body.get('role', 'student')
            prefix = body.get('prefix', 'digitalboard')
            grade = body.get('grade', '10th')
            sec = body.get('section', 'A')
            count = int(body.get('count', 1))
            password = body.get('password', '2234269580')

            # Load existing users from encrypted CSV
            users = load_users_from_encrypted_csv()

            created_count = 0
            for i in range(1, count + 1):
                acc_email = f"{prefix}{i:03d}@Digiboardleaning.com"
                users[acc_email] = {
                    "password": password,
                    "role": role,
                    "grade": grade,
                    "section": sec
                }
                created_count += 1

            # Save updated dictionary back to encrypted CSV
            save_users_to_encrypted_csv(users)

            self.send_json({"status": "ok", "created": created_count})
            return

        self.send_error(404)

if __name__ == "__main__":
    if not os.path.exists(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR)
    
    with socketserver.TCPServer(("", PORT), DigiBoardHandler) as httpd:
        print(f"DigiBoard Master Console running at http://localhost:{PORT}")
        httpd.serve_forever()
