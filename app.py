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

# Retrieve the secret decryption key from environment variables (GitHub Secrets / Render / Local)[cite: 6]
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AQ.Ab8RN6J-yO8rxDJAcCcM7EHM2_c_POYdGhFoNmetjTi6vue-2A")
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

# --- ENCRYPTED CSV DATABASE & LOGGING MANAGEMENT ---
def get_fernet():
    """Initializes and returns the Fernet encryption instance."""[cite: 6]
    if not CSV_ENCRYPTION_KEY:
        return Fernet(b'VlD8h2tEiJkQpKKnDNKnu8ya2fpIBMOo5oc7JKNasvk=')
    return Fernet(CSV_ENCRYPTION_KEY.encode())

def init_encrypted_csv():
    """Initializes accounts_encrypted.csv with an empty structure (headers only) if it does not exist."""[cite: 6]
    if not os.path.exists(ENCRYPTED_CSV_FILE):
        save_users_to_encrypted_csv({})

def load_users_from_encrypted_csv():
    """Decrypts accounts_encrypted.csv in memory and loads all user credentials."""[cite: 6]
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
    """Takes the complete users dictionary, formats to CSV, encrypts, and saves to disk."""[cite: 6]
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
    """Logs login activity to login_logs.csv audit trail."""[cite: 6]
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
        .icon-doc { background: #ef4444; }
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
        
        canvas { 
            display: block; 
            width: 100%; 
            height: 100%; 
            background: radial-gradient(#d1d5db 1px, transparent 1px); 
            background-size: 20px 20px; 
            cursor: crosshair; 
            touch-action: none; 
        }
        
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
        .user-photo { width: 64px; height: 64px; border-radius: 50%; object-fit: cover; border: 2px solid #38bdf8; }
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
                    <svg viewBox="0 0 24 24"><path d="M3 17.2
