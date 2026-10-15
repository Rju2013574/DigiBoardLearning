import http.server
import socketserver
import json
import urllib.parse
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
from google import genai

PORT = int(os.environ.get("PORT", 8000))
UPLOAD_DIR = "uploads"
ENCRYPTED_CSV_FILE = "accounts_encrypted.csv"
LOGIN_LOGS_CSV = "login_logs.csv"
SESSIONS = {}
BOARD_CACHE = "[]"
CACHE_LOCK = threading.Lock()

# Secrets for encrypted account persistence
CSV_ENCRYPTION_KEY = os.environ.get("CSV_ENCRYPTION_KEY", "-_L6Lrh-ujfHHi4wMe9TkooWB1zbqlzlPFQj2xPlSWA=")

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
# --- FAST & BULLETPROOF CLOUD AI HELPER ---
def query_gemini(prompt):
    """Queries Google's Gemini Cloud API directly with concise system instructions to prevent timeouts."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return "❌ Error: GEMINI_API_KEY environment variable is not set in Render."

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent?key={api_key}"
    
    # System instruction enforces concise, fast-generating lesson content
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "systemInstruction": {
            "parts": [{"text": "You are a classroom AI assistant for DigiBoard. Keep answers clear, well-structured, easy to understand for Grade 7 students, and concise so they generate quickly without network delays."}]
        },
        "generationConfig": {
            "maxOutputTokens": 800,
            "temperature": 0.7
        }
    }
    
    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            url,
            data=data,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        # Set socket timeout to 120 seconds
        with urllib.request.urlopen(req, timeout=120) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            candidates = res_data.get('candidates', [])
            if candidates:
                parts = candidates[0].get('content', {}).get('parts', [])
                if parts:
                    return parts[0].get('text', 'No text generated.')
            return "No response text found in candidate output."
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        return f"❌ API HTTP Error {e.code}: {error_body}"
    except Exception as e:
        return f"❌ Cloud AI Connection Error: {str(e)}"

# --- ENCRYPTED CSV DATABASE & LOGGING MANAGEMENT ---
def get_fernet():
    if not CSV_ENCRYPTION_KEY:
        return Fernet(b'VlD8h2tEiJkQpKKnDNKnu8ya2fpIBMOo5oc7JKNasvk=')
    return Fernet(CSV_ENCRYPTION_KEY.encode())

def init_encrypted_csv():
    if not os.path.exists(ENCRYPTED_CSV_FILE):
        save_users_to_encrypted_csv({})

def load_users_from_encrypted_csv():
    users = {}
    if os.path.exists(ENCRYPTED_CSV_FILE):
        try:
            fernet = get_fernet()
            with open(ENCRYPTED_CSV_FILE, "rb") as enc_file:
                encrypted_bytes = enc_file.read()
            
            decrypted_bytes = fernet.decrypt(encrypted_bytes)
            decoded_text = decrypted_bytes.decode('utf-8')
            reader = csv.reader(io.StringIO(decoded_text))
            
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
    try:
        fernet = get_fernet()
        output = io.StringIO()
        writer = csv.writer(output)
        
        writer.writerow(["Username", "Password", "Role", "Grade", "Section"])
        
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
        .icon-gemini { background: linear-gradient(135deg, #3b82f6, #8b5cf6); }
        .icon-fm { background: #eab308; }
        .icon-admin { background: #4f46e5; }
        .app-icon svg { width: 30px; height: 30px; fill: white; }
        .app-title { font-size: 0.85rem; font-weight: 600; color: #cbd5e1; text-align: center; }
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(3, 7, 18, 0.9); justify-content: center; align-items: center; z-index: 100; }
        .modal-content { background: #0f172a; border: 1px solid #1e293b; border-radius: 12px; width: 95%; max-width: 1150px; height: 88vh; display: flex; flex-direction: column; overflow: hidden; position: relative; }
        .modal-header { display: flex; justify-content: space-between; align-items: center; padding: 1rem 1.5rem; border-bottom: 1px solid #1e293b; background: #070d19; }
        .modal-header h3 { margin: 0; color: #38bdf8; font-size: 1.1rem; }
        .header-actions { display: flex; align-items: center; gap: 1rem; }
        .clear-all-btn { background: #ef4444; color: #ffffff; border: none; padding: 0.45rem 0.9rem; border-radius: 6px; font-weight: 600; font-size: 0.85rem; cursor: pointer; display: flex; align-items: center; gap: 0.4rem; transition: background 0.2s, transform 0.1s; }
        .clear-all-btn:hover { background: #dc2626; transform: scale(1.02); }
        .close-btn { color: #94a3b8; font-size: 1.5rem; font-weight: bold; cursor: pointer; line-height: 1; }
        .close-btn:hover { color: #fff; }
        .modal-body { padding: 1rem; overflow: hidden; flex: 1; position: relative; display: flex; flex-direction: column; }
        .wb-viewport { position: relative; width: 100%; height: 100%; flex: 1; background: #ffffff; border-radius: 8px; overflow: hidden; }
        canvas { display: block; width: 100%; height: 100%; background: radial-gradient(#d1d5db 1px, transparent 1px); background-size: 20px 20px; cursor: crosshair; touch-action: none; }
        .markup-palette { position: absolute; left: 20px; top: 50%; transform: translateY(-50%); background: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 30px; padding: 12px 8px; display: flex; flex-direction: column; align-items: center; gap: 10px; box-shadow: 0 12px 30px rgba(0,0,0,0.25); z-index: 20; width: 58px; }
        .markup-btn { width: 38px; height: 38px; border-radius: 50%; border: none; background: transparent; cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 1.1rem; transition: background 0.15s, transform 0.15s; color: #334155; padding: 0; }
        .markup-btn:hover { background: #e2e8f0; transform: scale(1.08); }
        .markup-btn.active { background: #ffffff; box-shadow: 0 2px 6px rgba(0,0,0,0.15); border: 2px solid #0284c7; }
        .palette-divider { width: 30px; height: 1px; background: #cbd5e1; margin: 2px 0; }
        .color-dot { width: 26px; height: 26px; border-radius: 50%; border: 2px solid white; box-shadow: 0 1px 4px rgba(0,0,0,0.3); cursor: pointer; transition: transform 0.15s; }
        .color-dot:hover { transform: scale(1.15); }
        .color-dot.active { transform: scale(1.2); border-color: #0284c7; }
        .tool-config-popover { display: none; position: absolute; left: 85px; top: 50%; transform: translateY(-50%); background: #ffffff; border: 1px solid #cbd5e1; border-radius: 12px; padding: 1rem; box-shadow: 0 10px 25px rgba(0,0,0,0.2); z-index: 30; width: 220px; color: #1e293b; }
        .tool-config-popover h4 { margin: 0 0 0.5rem 0; font-size: 0.85rem; color: #475569; }
        .stroke-options { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.8rem; }
        .stroke-opt { width: 30px; height: 30px; border-radius: 6px; border: 1px solid #cbd5e1; display: flex; justify-content: center; align-items: center; cursor: pointer; }
        .stroke-opt.active { border-color: #0284c7; background: #e0f2fe; }
        .stroke-preview { background: #000; border-radius: 50%; }
        .file-item { display: flex; justify-content: space-between; align-items: center; padding: 0.75rem 1rem; background: #070d19; border: 1px solid #1e293b; border-radius: 6px; margin-bottom: 0.5rem; }
        .file-item a { color: #38bdf8; text-decoration: none; font-weight: 500; font-size: 0.95rem; word-break: break-all; }
        .file-item a:hover { text-decoration: underline; }
        .delete-btn { color: #ef4444; background: rgba(239, 68, 68, 0.1); border: 1px solid #ef4444; padding: 0.3rem 0.6rem; border-radius: 4px; cursor: pointer; font-weight: bold; font-size: 0.8rem; }
        .delete-btn:hover { background: #ef4444; color: #fff; }
        .readonly-banner { background: #1e293b; color: #94a3b8; font-size: 0.8rem; padding: 0.4rem 1rem; text-align: center; border-bottom: 1px solid #334155; }
        .admin-form-group { margin-bottom: 1rem; }
        .admin-form-group label { display: block; margin-bottom: 0.3rem; color: #94a3b8; font-size: 0.85rem; }
        .admin-form-group input, .admin-form-group select { width: 100%; padding: 0.5rem; background: #070d19; border: 1px solid #334155; color: white; border-radius: 6px; }
        .ai-msg p { margin: 0 0 0.5rem 0; }
        .ai-msg ul, .ai-msg ol { margin: 0.5rem 0; padding-left: 1.2rem; }
        .ai-msg strong { color: #38bdf8; }
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
            <div class="app-card" onclick="openApp('whiteboard-modal')">
                <div class="app-icon icon-wb">
                    <svg viewBox="0 0 24 24"><path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg>
                </div>
                <div class="app-title">WhiteBoard</div>
            </div>
            <div class="app-card" onclick="openApp('gemini-modal')">
                <div class="app-icon icon-gemini">
                    <svg viewBox="0 0 24 24"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="white" stroke-width="2" fill="none"/></svg>
                </div>
                <div class="app-title">Gemini AI (24/7 Cloud)</div>
            </div>
            <div class="app-card" onclick="openFileManager()">
                <div class="app-icon icon-fm">
                    <svg viewBox="0 0 24 24"><path d="M10 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z"/></svg>
                </div>
                <div class="app-title">File Manager</div>
            </div>

            <!--ROLE_ADMIN_ONLY-->
            <div class="app-card" onclick="openApp('admin-modal')">
                <div class="app-icon icon-admin">
                    <svg viewBox="0 0 24 24"><path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-5.45 9-12V5l-9-4zm0 10.99h7c-.53 4.12-3.28 7.79-7 8.94V12H5V6.3l7-3.11v8.8s0 0 0 0z"/></svg>
                </div>
                <div class="app-title">Admin Console</div>
            </div>
            <!--END_ADMIN_ROLE-->
        </div>
    </div>

    <!-- GEMINI AI MODAL -->
    <div class="modal" id="gemini-modal">
        <div class="modal-content" style="max-width: 900px; height: 88vh;">
            <div class="modal-header">
                <h3>DigiBoard AI Engine (Cloud Native)</h3>
                <div class="header-actions">
                    <button class="clear-all-btn" onclick="clearChat()" title="Clear Conversation"><span>New Chat</span> ✨</button>
                    <span class="close-btn" onclick="closeApp('gemini-modal')">&times;</span>
                </div>
            </div>
            <div class="modal-body" style="display:flex; flex-direction:column; height: 100%; padding: 1rem;">
                <div id="chat-messages" style="flex:1; overflow-y:auto; background:#070d19; border:1px solid #1e293b; border-radius:8px; padding:1.2rem; margin-bottom:1rem; display:flex; flex-direction:column; gap:1rem;">
                    <div class="ai-msg" style="background:#1e293b; padding:0.85rem 1.1rem; border-radius:10px; max-width:85%; align-self:flex-start; color:#f8fafc; font-size:0.95rem; border-left: 3px solid #38bdf8;">
                        Hello! I am your 24/7 cloud AI assistant. How can I help you today?
                    </div>
                </div>
                <div style="display:flex; gap:0.5rem;">
                    <input type="text" id="chat-input" placeholder="Type your message here..." style="flex:1; padding:0.85rem; background:#070d19; border:1px solid #334155; color:white; border-radius:8px; font-size:0.95rem;" onkeydown="if(event.key==='Enter') sendGeminiMessage()">
                    <button onclick="sendGeminiMessage()" style="padding:0.85rem 1.8rem; background:linear-gradient(135deg, #2563eb, #7c3aed); border:none; color:white; font-weight:bold; border-radius:8px; cursor:pointer;">Send</button>
                </div>
            </div>
        </div>
    </div>

    <!-- ADMIN MODAL -->
    <!--ROLE_ADMIN_ONLY-->
    <div class="modal" id="admin-modal">
        <div class="modal-content" style="max-width: 850px; height:auto;">
            <div class="modal-header">
                <h3>Admin Management Console</h3>
                <span class="close-btn" onclick="closeApp('admin-modal')">&times;</span>
            </div>
            <div class="modal-body" style="height: 520px; overflow-y: auto;">
                <div style="background:#070d19; padding:1.2rem; border-radius:8px; border:1px solid #1e293b;">
                    <h4 style="margin-top:0; color:#cbd5e1;">Mass Provision Accounts</h4>
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
                                <label>Prefix Name</label>
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
                <div id="users-table-container" style="background:#070d19; border:1px solid #1e293b; border-radius:6px; max-height:200px; overflow-y:auto; padding:0.5rem;">
                </div>
            </div>
        </div>
    </div>
    <!--END_ADMIN_ROLE-->

    <div class="modal" id="whiteboard-modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3>DigiBoard Interactive Whiteboard</h3>
                <div class="header-actions">
                    <!--ROLE_TEACHER_ONLY-->
                    <button class="clear-all-btn" onclick="clearBoard()" title="Clear Entire Whiteboard">
                        <span>Clear All</span> 🗑️
                    </button>
                    <!--END_ROLE-->
                    <span class="close-btn" onclick="closeApp('whiteboard-modal')">&times;</span>
                </div>
            </div>
            <!--ROLE_STUDENT_ONLY-->
            <div class="readonly-banner">Student View (Read-Only Mode) - Live Syncing Teacher Board</div>
            <!--END_STUDENT_ROLE-->
            <div class="modal-body">
                <div class="wb-viewport" id="wb-container">
                    <canvas id="board"></canvas>
                    <!--ROLE_TEACHER_ONLY-->
                    <div class="markup-palette">
                        <button class="markup-btn" onclick="undo()" title="Undo">↩️</button>
                        <button class="markup-btn" onclick="redo()" title="Redo">↪️</button>
                        <div class="palette-divider"></div>
                        <button class="markup-btn active" id="tool-pen" onclick="selectTool('pen')" title="Pen">✏️</button>
                        <button class="markup-btn" id="tool-fountain" onclick="selectTool('fountain')" title="Fountain Pen">✒️</button>
                        <button class="markup-btn" id="tool-marker" onclick="selectTool('marker')" title="Marker">🖊️</button>
                        <button class="markup-btn" id="tool-highlighter" onclick="selectTool('highlighter')" title="Highlighter">🖍️</button>
                        <button class="markup-btn" id="tool-tube" onclick="selectTool('tube')" title="Paint Tube">🎨</button>
                        <button class="markup-btn" id="tool-eraser" onclick="selectTool('eraser')" title="Eraser">🧹</button>
                        <div class="palette-divider"></div>
                        <div class="color-dot active" style="background:#000000;" onclick="setColor('#000000', this)"></div>
                        <div class="color-dot" style="background:#ef4444;" onclick="setColor('#ef4444', this)"></div>
                        <div class="color-dot" style="background:#3b82f6;" onclick="setColor('#3b82f6', this)"></div>
                        <div class="color-dot" style="background:#10b981;" onclick="setColor('#10b981', this)"></div>
                        <div class="color-dot" style="background:#f59e0b;" onclick="setColor('#f59e0b', this)"></div>
                        <input type="color" id="custom-color" style="width:24px; height:24px; border:none; cursor:pointer; background:none;" onchange="setColor(this.value, null)">
                        <div class="palette-divider"></div>
                        <button class="markup-btn" onclick="toggleConfigPopover()" title="Tool Settings">⚙️</button>
                    </div>
                    <div class="tool-config-popover" id="config-popover">
                        <h4>Stroke Thickness</h4>
                        <div class="stroke-options">
                            <div class="stroke-opt" onclick="setStroke(2, this)"><div class="stroke-preview" style="width:3px; height:3px;"></div></div>
                            <div class="stroke-opt active" onclick="setStroke(5, this)"><div class="stroke-preview" style="width:6px; height:6px;"></div></div>
                            <div class="stroke-opt" onclick="setStroke(10, this)"><div class="stroke-preview" style="width:10px; height:10px;"></div></div>
                            <div class="stroke-opt" onclick="setStroke(18, this)"><div class="stroke-preview" style="width:14px; height:14px;"></div></div>
                        </div>
                        <h4>Opacity</h4>
                        <input type="range" id="opacity-range" min="0.1" max="1" step="0.1" value="1" style="width:100%;" onchange="setOpacity(this.value)">
                    </div>
                    <!--END_ROLE-->
                </div>
            </div>
        </div>
    </div>

    <div class="modal" id="filemanager-modal">
        <div class="modal-content" style="max-width: 700px; height:auto;">
            <div class="modal-header">
                <h3>Class File Manager</h3>
                <span class="close-btn" onclick="closeApp('filemanager-modal')">&times;</span>
            </div>
            <!--ROLE_STUDENT_ONLY-->
            <div class="readonly-banner">Student View (Read-Only) - View & Download Available Documents</div>
            <!--END_STUDENT_ROLE-->
            <div class="modal-body" style="height: 520px; overflow-y: auto;">
                <div style="display:flex; gap:1rem; margin-bottom:1rem; background:#070d19; padding:0.75rem; border-radius:6px; border:1px solid #1e293b;">
                    <div style="flex:1;">
                        <label style="display:block; font-size:0.75rem; color:#94a3b8; margin-bottom:0.2rem;">Select Grade / Class</label>
                        <select id="filter-grade" onchange="loadFileList()" style="width:100%; padding:0.4rem; background:#050a14; color:white; border:1px solid #334155; border-radius:4px;"><!--GRADES_OPTIONS--></select>
                    </div>
                    <div style="flex:1;">
                        <label style="display:block; font-size:0.75rem; color:#94a3b8; margin-bottom:0.2rem;">Select Section</label>
                        <select id="filter-section" onchange="loadFileList()" style="width:100%; padding:0.4rem; background:#050a14; color:white; border:1px solid #334155; border-radius:4px;"><!--SECTIONS_OPTIONS--></select>
                    </div>
                </div>

                <!--ROLE_TEACHER_ONLY-->
                <form action="/upload" method="POST" enctype="multipart/form-data" onsubmit="prepareUpload(event)" style="margin-bottom: 1.5rem; background: #070d19; padding: 1rem; border-radius: 6px; border: 1px solid #1e293b;">
                    <input type="hidden" name="grade" id="upload-grade">
                    <input type="hidden" name="section" id="upload-section">
                    <label style="display:block; margin-bottom: 0.5rem; color:#94a3b8; font-weight:600;">Upload Document to Selected Class:</label>
                    <input type="file" name="file" required style="margin-bottom:0.75rem; color:white; width:100%;">
                    <button type="submit" style="width:100%; padding:0.6rem; background:#10b981; border:none; color:white; font-weight:bold; border-radius:4px; cursor:pointer;">Upload File</button>
                </form>
                <!--END_ROLE-->

                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.75rem;">
                    <span style="color:#94a3b8; font-size:0.85rem; font-weight:600;">DOCUMENTS FOR SELECTED CLASS</span>
                    <button onclick="loadFileList()" style="background:transparent; border:1px solid #334155; color:#38bdf8; padding:0.2rem 0.5rem; border-radius:4px; cursor:pointer; font-size:0.75rem;">🔄 Refresh</button>
                </div>
                <ul id="file-list-container" style="list-style:none; padding:0; margin:0;">
                    <li style="color:#94a3b8; text-align:center; padding: 2rem 0;">Select a grade and section to view documents.</li>
                </ul>
            </div>
        </div>
    </div>

    <script>
        const USER_ROLE = "<!--USER_ROLE-->";
        let filePollInterval = null;

        function sendGeminiMessage() {
            const input = document.getElementById('chat-input');
            const msg = input.value.trim();
            if(!msg) return;
            
            const container = document.getElementById('chat-messages');
            container.innerHTML += `<div style="background:#2563eb; padding:0.75rem 1rem; border-radius:8px; max-width:80%; align-self:flex-end; color:#f8fafc; font-size:0.9rem;">${escapeHtml(msg)}</div>`;
            input.value = '';
            container.scrollTop = container.scrollHeight;

            const loadingId = 'loading-' + Date.now();
            container.innerHTML += `<div id="${loadingId}" style="background:#1e293b; padding:0.75rem 1rem; border-radius:8px; max-width:80%; align-self:flex-start; color:#94a3b8; font-size:0.9rem;">Gemini Cloud AI is generating response...</div>`;
            container.scrollTop = container.scrollHeight;

            fetch('/api/gemini', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({prompt: msg})
            })
            .then(r => r.json())
            .then(res => {
                document.getElementById(loadingId).remove();
                const parsedMarkdown = marked.parse(res.response);
                container.innerHTML += `<div class="ai-msg" style="background:#1e293b; padding:0.85rem 1.1rem; border-radius:10px; max-width:85%; align-self:flex-start; color:#f8fafc; font-size:0.95rem; border-left: 3px solid #38bdf8;">${parsedMarkdown}</div>`;
                container.scrollTop = container.scrollHeight;
            })
            .catch(err => {
                document.getElementById(loadingId).remove();
                container.innerHTML += `<div style="background:rgba(239,68,68,0.2); color:#ef4444; padding:0.75rem 1rem; border-radius:8px; max-width:80%; align-self:flex-start; font-size:0.9rem;">Error connecting to cloud AI engine.</div>`;
            });
        }

        function clearChat() {
            document.getElementById('chat-messages').innerHTML = `
                <div class="ai-msg" style="background:#1e293b; padding:0.85rem 1.1rem; border-radius:10px; max-width:85%; align-self:flex-start; color:#f8fafc; font-size:0.95rem; border-left: 3px solid #38bdf8;">
                    New chat session started. Ask me anything!
                </div>`;
        }

        function escapeHtml(text) {
            return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
        }

        if (USER_ROLE === 'admin') {
            function loadUsers() {
                fetch('/api/admin/users')
                    .then(r => r.json())
                    .then(users => {
                        document.getElementById('user-count').innerText = Object.keys(users).length;
                        let html = '<table style="width:100%; border-collapse:collapse; text-align:left; font-size:0.85rem;">';
                        html += '<tr style="border-bottom:1px solid #334155; color:#94a3b8;"><th>Username</th><th>Role</th><th>Class & Section</th><th>Action</th></tr>';
                        for (let u in users) {
                            html += `<tr style="border-bottom:1px solid #1e293b; color:#cbd5e1;">
                                <td style="padding:0.4rem 0;">${u}</td>
                                <td><span class="user-role-badge">${users[u].role}</span></td>
                                <td>${users[u].grade || 'N/A'} - ${users[u].section || 'N/A'}</td>
                                <td><button class="delete-btn" onclick="deleteAccount('${u}')">Delete</button></td>
                            </tr>`;
                        }
                        html += '</table>';
                        document.getElementById('users-table-container').innerHTML = html;
                    });
            }

            function deleteAccount(username) {
                if (!confirm(`Are you sure you want to delete user account: ${username}?`)) return;
                fetch('/api/admin/users?username=' + encodeURIComponent(username), { method: 'DELETE' })
                    .then(r => r.json())
                    .then(res => {
                        alert(`Successfully deleted account: ${username}`);
                        loadUsers();
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

        function openApp(id) { 
            document.getElementById(id).style.display = 'flex'; 
            if(id === 'whiteboard-modal') { resizeCanvas(); }
        }
        
        function closeApp(id) { 
            document.getElementById(id).style.display = 'none'; 
            if(id === 'filemanager-modal' && filePollInterval) {
                clearInterval(filePollInterval);
                filePollInterval = null;
            }
        }

        function openFileManager() { 
            openApp('filemanager-modal'); 
            loadFileList();
            if(!filePollInterval) {
                filePollInterval = setInterval(loadFileList, 4000);
            }
        }

        function loadFileList() {
            const grade = document.getElementById('filter-grade').value;
            const section = document.getElementById('filter-section').value;
            if(!grade || !section) return;

            fetch(`/api/files?grade=${encodeURIComponent(grade)}&section=${encodeURIComponent(section)}&t=` + Date.now(), { cache: "no-store" })
                .then(r => {
                    if (!r.ok) throw new Error("HTTP error " + r.status);
                    return r.json();
                })
                .then(files => {
                    const container = document.getElementById('file-list-container');
                    if (!container) return;
                    if (!files || files.length === 0) {
                        container.innerHTML = '<li style="color:#94a3b8; text-align:center; padding:2rem 0; background:#070d19; border:1px solid #1e293b; border-radius:6px;">No documents uploaded for Grade ' + grade + ' - Section ' + section + ' yet.</li>';
                        return;
                    }
                    container.innerHTML = files.map(file => `
                        <li class="file-item">
                            <a href="/uploads/${grade}/${section}/${encodeURIComponent(file)}" target="_blank" download="${file}">📄 ${file}</a>
                            ${(USER_ROLE === 'teacher' || USER_ROLE === 'admin') ? `<button class="delete-btn" onclick="deleteFile('${file}')">Delete</button>` : ''}
                        </li>
                    `).join('');
                })
                .catch(err => {
                    console.error("Failed to load files:", err);
                });
        }

        function prepareUpload(e) {
            document.getElementById('upload-grade').value = document.getElementById('filter-grade').value;
            document.getElementById('upload-section').value = document.getElementById('filter-section').value;
        }

        function deleteFile(filename) {
            const grade = document.getElementById('filter-grade').value;
            const section = document.getElementById('filter-section').value;
            if (!confirm('Delete file: ' + filename + '?')) return;
            fetch(`/api/delete-file?grade=${encodeURIComponent(grade)}&section=${encodeURIComponent(section)}&name=` + encodeURIComponent(filename), { method: 'DELETE' })
                .then(r => r.json())
                .then(() => loadFileList());
        }

        const canvas = document.getElementById('board');
        const ctx = canvas.getContext('2d');
        const container = document.getElementById('wb-container');

        let isDrawing = false;
        let lines = [];
        let undoStack = [];
        let activeTool = 'pen';
        let currentColor = '#000000';
        let currentLineWidth = 5;
        let currentOpacity = 1.0;

        function resizeCanvas() {
            canvas.width = container.clientWidth;
            canvas.height = container.clientHeight;
            redraw(lines);
        }

        window.addEventListener('resize', resizeCanvas);

        if (USER_ROLE === 'teacher' || USER_ROLE === 'admin') {
            canvas.addEventListener('pointerdown', (e) => {
                isDrawing = true;
                canvas.setPointerCapture(e.pointerId);
                const rect = canvas.getBoundingClientRect();
                let width = currentLineWidth;
                let color = currentColor;
                let opacity = currentOpacity;

                if (activeTool === 'highlighter') {
                    opacity = 0.4;
                    width = Math.max(width, 18);
                } else if (activeTool === 'eraser') {
                    color = '#ffffff';
                    width = 25;
                    opacity = 1.0;
                } else if (activeTool === 'marker') {
                    width = Math.max(width, 10);
                }

                const newLine = {
                    tool: activeTool,
                    color: color,
                    width: width,
                    opacity: opacity,
                    pts: [{ x: e.clientX - rect.left, y: e.clientY - rect.top }]
                };
                lines.push(newLine);
                undoStack = [];
            });

            canvas.addEventListener('pointermove', (e) => {
                if (!isDrawing) return;
                const rect = canvas.getBoundingClientRect();
                const currentLine = lines[lines.length - 1];
                currentLine.pts.push({ x: e.clientX - rect.left, y: e.clientY - rect.top });
                redraw(lines);
            });

            canvas.addEventListener('pointerup', (e) => { 
                if (isDrawing) {
                    isDrawing = false; 
                    canvas.releasePointerCapture(e.pointerId);
                    syncWhiteboard();
                }
            });
            
            canvas.addEventListener('pointercancel', (e) => {
                if (isDrawing) {
                    isDrawing = false;
                    try { canvas.releasePointerCapture(e.pointerId); } catch(err){}
                    syncWhiteboard();
                }
            });
        }

        function redraw(linesToDraw) {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            if (!linesToDraw) return;
            
            linesToDraw.forEach(line => {
                if (!line || !line.pts || line.pts.length === 0) return;
                ctx.save();
                ctx.strokeStyle = line.color || "#000000";
                ctx.lineWidth = line.width || 3;
                ctx.globalAlpha = line.opacity || 1.0;
                ctx.lineCap = 'round';
                ctx.lineJoin = 'round';
                
                ctx.beginPath();
                line.pts.forEach((pt, i) => {
                    if (i === 0) ctx.moveTo(pt.x, pt.y);
                    else ctx.lineTo(pt.x, pt.y);
                });
                ctx.stroke();
                ctx.restore();
            });
        }

        function selectTool(tool) {
            activeTool = tool;
            document.querySelectorAll('.markup-btn').forEach(b => b.classList.remove('active'));
            const activeBtn = document.getElementById('tool-' + tool);
            if(activeBtn) activeBtn.classList.add('active');
        }

        function setColor(hex, el) {
            currentColor = hex;
            if(el) {
                document.querySelectorAll('.color-dot').forEach(d => d.classList.remove('active'));
                el.classList.add('active');
            }
        }

        function setStroke(width, el) {
            currentLineWidth = width;
            document.querySelectorAll('.stroke-opt').forEach(o => o.classList.remove('active'));
            if(el) el.classList.add('active');
        }

        function setOpacity(val) { currentOpacity = parseFloat(val); }

        function toggleConfigPopover() {
            const pop = document.getElementById('config-popover');
            pop.style.display = pop.style.display === 'block' ? 'none' : 'block';
        }

        function undo() {
            if (lines.length > 0) {
                undoStack.push(lines.pop());
                redraw(lines);
                syncWhiteboard();
            }
        }

        function redo() {
            if (undoStack.length > 0) {
                lines.push(undoStack.pop());
                redraw(lines);
                syncWhiteboard();
            }
        }

        function clearBoard() {
            if (lines.length === 0) return;
            if (!confirm("Are you sure you want to clear the entire whiteboard?")) return;
            undoStack.push(...lines);
            lines = [];
            redraw(lines);
            syncWhiteboard();
        }

        function syncWhiteboard() {
            if (USER_ROLE !== 'teacher' && USER_ROLE !== 'admin') return;
            fetch('/api/whiteboard', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(lines)
            });
        }

        function pollWhiteboard() {
            if (USER_ROLE === 'student') {
                fetch('/api/whiteboard?t=' + Date.now(), { cache: "no-store" })
                    .then(r => r.json())
                    .then(data => {
                        lines = data;
                        redraw(lines);
                    })
                    .catch(() => {})
                    .finally(() => setTimeout(pollWhiteboard, 1000));
            }
        }

        if (USER_ROLE === 'student') {
            pollWhiteboard();
        }
    </script>
</body>
</html>"""

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

    def parse_multipart(self):
        content_type = self.headers.get('Content-Type', '')
        if not content_type.startswith('multipart/form-data'):
            return None, None, None, None
        
        boundary = content_type.split('boundary=')[1].encode('utf-8')
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)

        parts = body.split(b'--' + boundary)
        filename = None
        file_data = None
        grade = "10th"
        section = "A"

        for part in parts:
            if b'name="grade"' in part:
                grade = part.split(b'\r\n\r\n')[1].rsplit(b'\r\n', 1)[0].decode('utf-8').strip()
            elif b'name="section"' in part:
                section = part.split(b'\r\n\r\n')[1].rsplit(b'\r\n', 1)[0].decode('utf-8').strip()
            elif b'filename="' in part:
                header_part, file_data = part.split(b'\r\n\r\n', 1)
                file_data = file_data.rsplit(b'\r\n', 1)[0]
                header_text = header_part.decode('utf-8', errors='ignore')
                filename_match = re.search(r'filename="([^"]+)"', header_text)
                if filename_match:
                    filename = os.path.basename(filename_match.group(1))

        return filename, file_data, grade, section

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query_params = urllib.parse.parse_qs(parsed.query)
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
                key_info = session.get('key_info', {})
                html = html.replace("<!--ADMIN_NAME-->", key_info.get("name", "System Administrator"))
                html = html.replace("<!--SUPER_KEY-->", key_info.get("super_key", "UNKNOWN"))
                html = html.replace("<!--ADMIN_PHOTO-->", key_info.get("photo_url", ""))
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

        if path == "/api/files":
            if not session:
                self.send_json({"error": "Unauthorized"}, 401)
                return
            grade = query_params.get('grade', ['10th'])[0]
            section = query_params.get('section', ['A'])[0]
            target_dir = os.path.join(UPLOAD_DIR, grade, section)
            files = os.listdir(target_dir) if os.path.exists(target_dir) else []
            self.send_json(files)
            return

        if path == "/api/whiteboard":
            global BOARD_CACHE
            with CACHE_LOCK:
                try:
                    data = json.loads(BOARD_CACHE)
                except Exception:
                    data = []
            self.send_json(data)
            return

        if path.startswith("/uploads/"):
            rel_path = path[len("/uploads/"):].strip('/')
            filepath = os.path.join(UPLOAD_DIR, rel_path)
            if os.path.exists(filepath):
                filename = os.path.basename(filepath)
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
                self.set_no_cache_headers()
                self.end_headers()
                with open(filepath, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404, "File Not Found")
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

                users = load_users_from_encrypted_csv()
                users[admin_info["email"]] = {"password": "", "role": "admin", "grade": "10th", "section": "A"}
                save_users_to_encrypted_csv(users)

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

        if path == "/api/gemini":
            content_length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(content_length).decode('utf-8'))
            prompt = body.get('prompt', '')
            ai_response = query_gemini(prompt)
            self.send_json({"response": ai_response})
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

            save_users_to_encrypted_csv(users)
            self.send_json({"status": "ok", "created": created_count})
            return

        if path == "/upload":
            if session['role'] not in ['teacher', 'admin']:
                self.send_json({"error": "Forbidden"}, 403)
                return
            filename, file_data, grade, section = self.parse_multipart()
            if filename and file_data:
                target_dir = os.path.join(UPLOAD_DIR, grade, section)
                if not os.path.exists(target_dir):
                    os.makedirs(target_dir)
                filepath = os.path.join(target_dir, filename)
                with open(filepath, "wb") as f:
                    f.write(file_data)
            self.redirect("/")
            return

        if path == "/api/whiteboard":
            if session['role'] not in ['teacher', 'admin']:
                self.send_json({"error": "Forbidden"}, 403)
                return
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            global BOARD_CACHE
            with CACHE_LOCK:
                BOARD_CACHE = body
            self.send_json({"status": "ok"})
            return

        self.send_error(404)

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query_params = urllib.parse.parse_qs(parsed.query)
        session = self.get_session()

        if not session or session.get('role') != 'admin':
            self.send_json({"error": "Forbidden"}, 403)
            return

        if path == "/api/admin/users":
            username = query_params.get('username', [''])[0].strip()
            if username:
                users = load_users_from_encrypted_csv()
                if username in users:
                    del users[username]
                    save_users_to_encrypted_csv(users)
                self.send_json({"status": "deleted"})
                return

        if path == "/api/delete-file":
            grade = query_params.get('grade', ['10th'])[0]
            section = query_params.get('section', ['A'])[0]
            filename = query_params.get('name', [''])[0]
            if filename:
                filepath = os.path.join(UPLOAD_DIR, grade, section, os.path.basename(filename))
                if os.path.exists(filepath):
                    os.remove(filepath)
            self.send_json({"status": "deleted"})
            return

        self.send_error(404)

if __name__ == '__main__':
    ensure_file_manager_structure()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), threaded=True)
    with socketserver.TCPServer(("", PORT), DigiBoardHandler) as httpd:
        print(f"DigiBoard Master Console running on port {PORT}")
        httpd.serve_forever()
