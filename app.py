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

PORT = 8000
UPLOAD_DIR = "uploads"
SESSIONS = {}
BOARD_CACHE = "[]"
CACHE_LOCK = threading.Lock()

USERS = {
    "juraghav@Digiboardleaning.com": {"password": "2234269580", "role": "teacher"},
    "socialstudiesclass@Digiboardleaning.com": {"password": "2234269580", "role": "student"}
}

def scan_usb_for_key():
    system = platform.system()
    possible_paths = []

    if system == "Windows":
        for letter in string.ascii_uppercase:
            drive_path = f"{letter}:\\"
            if os.path.exists(drive_path):
                possible_paths.append(drive_path)

    # Print out detected drive paths in your terminal/console
    print(f"[DEBUG] Active Windows Drives Found: {possible_paths}")

    for path in possible_paths:
        key_file = os.path.join(path, "admin_key.json")
        print(f"[DEBUG] Checking path: {key_file} | Exists: {os.path.exists(key_file)}")
        if os.path.exists(key_file):
            try:
                with open(key_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    print(f"[DEBUG] File read successfully! Keys in file: {list(data.keys())}")
                    if data.get("super_key"):
                        data["drive_path"] = path
                        return data
                    else:
                        print("[DEBUG] 'super_key' field missing or empty in JSON.")
            except Exception as e:
                print(f"[DEBUG] Failed to read JSON file at {key_file}: {e}")

    return None
LOGIN_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>DigiBoard - Login</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #070d19; color: #f8fafc; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .login-card { background: #0f172a; border: 1px solid #1e293b; padding: 2.5rem; border-radius: 12px; width: 360px; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.6); }
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
            <button type="submit" class="admin-btn">🔑 Authenticate Admin Mode (USB Hardware Key)</button>
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
                    <svg viewBox="0 0 24 24"><path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg>
                </div>
                <div class="app-title">WhiteBoard</div>
            </div>
            <div class="app-card" onclick="launchWPS()">
                <div class="app-icon icon-doc">
                    <svg viewBox="0 0 24 24"><path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z"/></svg>
                </div>
                <div class="app-title">WPS Office</div>
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

    <!-- ADMIN MODAL -->
    <!--ROLE_ADMIN_ONLY-->
    <div class="modal" id="admin-modal">
        <div class="modal-content" style="max-width: 800px; height:auto;">
            <div class="modal-header">
                <h3>Admin Management & Provisioning Console</h3>
                <span class="close-btn" onclick="closeApp('admin-modal')">&times;</span>
            </div>
            <div class="modal-body" style="height: 520px; overflow-y: auto;">
                <div style="display:flex; align-items:center; gap:1.5rem; background:#070d19; padding:1rem; border-radius:8px; margin-bottom:1.5rem; border:1px solid #1e293b;">
                    <img src="<!--ADMIN_PHOTO-->" class="user-photo" alt="Admin Photo" onerror="this.src='https://via.placeholder.com/64'">
                    <div>
                        <h4 style="margin:0; color:#38bdf8;"><!--ADMIN_NAME--> (Admin Mode Active)</h4>
                        <p style="margin:0.2rem 0 0 0; font-size:0.8rem; color:#94a3b8;">Key Serial ID: <!--SUPER_KEY--></p>
                        <p style="margin:0.2rem 0 0 0; font-size:0.75rem; color:#10b981;">🔒 Hardware Security Token Verified (Active Drive Session)</p>
                    </div>
                </div>

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
                                <label>Prefix Name (e.g. board / teacher)</label>
                                <input type="text" id="mass-prefix" placeholder="digitalboard" required>
                            </div>
                            <div class="admin-form-group">
                                <label>Number of Accounts</label>
                                <input type="number" id="mass-count" min="1" max="100" value="5" required>
                            </div>
                            <div class="admin-form-group">
                                <label>Default Password</label>
                                <input type="password" id="mass-password" required value="2234269580">
                            </div>
                        </div>
                        <button type="submit" style="width:100%; padding:0.6rem; background:#4f46e5; border:none; color:white; font-weight:bold; border-radius:4px; cursor:pointer;">Generate Accounts Batch</button>
                    </form>
                </div>

                <h4 style="margin-top:1.5rem; color:#cbd5e1;">Active System Users (<span id="user-count">0</span>)</h4>
                <div id="users-table-container" style="background:#070d19; border:1px solid #1e293b; border-radius:6px; max-height:180px; overflow-y:auto; padding:0.5rem;">
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
        <div class="modal-content" style="max-width: 650px; height:auto;">
            <div class="modal-header">
                <h3>Class File Manager</h3>
                <span class="close-btn" onclick="closeApp('filemanager-modal')">&times;</span>
            </div>
            <!--ROLE_STUDENT_ONLY-->
            <div class="readonly-banner">Student View (Read-Only) - View & Download Available Documents</div>
            <!--END_STUDENT_ROLE-->
            <div class="modal-body" style="height: 480px; overflow-y: auto;">
                <!--ROLE_TEACHER_ONLY-->
                <form action="/upload" method="POST" enctype="multipart/form-data" style="margin-bottom: 1.5rem; background: #070d19; padding: 1rem; border-radius: 6px; border: 1px solid #1e293b;">
                    <label style="display:block; margin-bottom: 0.5rem; color:#94a3b8; font-weight:600;">Upload New Document:</label>
                    <input type="file" name="file" required style="margin-bottom:0.75rem; color:white; width:100%;">
                    <button type="submit" style="width:100%; padding:0.6rem; background:#10b981; border:none; color:white; font-weight:bold; border-radius:4px; cursor:pointer;">Upload File</button>
                </form>
                <!--END_ROLE-->
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.75rem;">
                    <span style="color:#94a3b8; font-size:0.85rem; font-weight:600;">AVAILABLE DOCUMENTS</span>
                    <button onclick="loadFileList()" style="background:transparent; border:1px solid #334155; color:#38bdf8; padding:0.2rem 0.5rem; border-radius:4px; cursor:pointer; font-size:0.75rem;">🔄 Refresh</button>
                </div>
                <ul id="file-list-container" style="list-style:none; padding:0; margin:0;">
                    <li style="color:#94a3b8; text-align:center; padding: 2rem 0;">Loading files...</li>
                </ul>
            </div>
        </div>
    </div>

    <script>
        const USER_ROLE = "<!--USER_ROLE-->";
        let filePollInterval = null;

        // Admin Heartbeat to ensure physical pen drive stays plugged in
        if (USER_ROLE === 'admin') {
            setInterval(() => {
                fetch('/api/admin-heartbeat')
                    .then(r => r.json())
                    .then(data => {
                        if (!data.valid) {
                            alert('⚠️ Hardware SSH Key Pen Drive Disconnected! Logging out for security...');
                            window.location.href = '/logout';
                        }
                    })
                    .catch(() => { window.location.href = '/logout'; });
            }, 3000);

            function loadUsers() {
                fetch('/api/admin/users')
                    .then(r => r.json())
                    .then(users => {
                        document.getElementById('user-count').innerText = Object.keys(users).length;
                        let html = '<table style="width:100%; border-collapse:collapse; text-align:left; font-size:0.85rem;">';
                        html += '<tr style="border-bottom:1px solid #334155; color:#94a3b8;"><th>Username</th><th>Role</th></tr>';
                        for (let u in users) {
                            html += `<tr style="border-bottom:1px solid #1e293b; color:#cbd5e1;"><td style="padding:0.4rem 0;">${u}</td><td><span class="user-role-badge">${users[u].role}</span></td></tr>`;
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
                    alert(`Successfully created ${res.created} accounts!`);
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
        
        function launchWPS() { window.location.href = '/launch-wps'; }

        function openFileManager() { 
            openApp('filemanager-modal'); 
            loadFileList();
            if(!filePollInterval) {
                filePollInterval = setInterval(loadFileList, 4000);
            }
        }

        function loadFileList() {
            fetch('/api/files?t=' + Date.now(), { cache: "no-store" })
                .then(r => {
                    if (!r.ok) throw new Error("HTTP error " + r.status);
                    return r.json();
                })
                .then(files => {
                    const container = document.getElementById('file-list-container');
                    if (!container) return;
                    if (!files || files.length === 0) {
                        container.innerHTML = '<li style="color:#94a3b8; text-align:center; padding:2rem 0; background:#070d19; border:1px solid #1e293b; border-radius:6px;">No documents uploaded yet.</li>';
                        return;
                    }
                    container.innerHTML = files.map(file => `
                        <li class="file-item">
                            <a href="/uploads/${encodeURIComponent(file)}" target="_blank" download="${file}">📄 ${file}</a>
                            ${(USER_ROLE === 'teacher' || USER_ROLE === 'admin') ? `<button class="delete-btn" onclick="deleteFile('${file}')">Delete</button>` : ''}
                        </li>
                    `).join('');
                })
                .catch(err => {
                    console.error("Failed to load files:", err);
                });
        }

        function deleteFile(filename) {
            if (!confirm('Delete file: ' + filename + '?')) return;
            fetch('/api/delete-file?name=' + encodeURIComponent(filename), { method: 'DELETE' })
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

def open_local_file(filepath):
    import subprocess, sys
    try:
        if sys.platform.startswith('win'):
            os.startfile(filepath)
        elif sys.platform.startswith('darwin'):
            subprocess.run(['open', filepath])
        else:
            subprocess.run(['xdg-open', filepath])
    except Exception as e:
        print(f"Error opening document: {e}")

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
            return None, None
        
        boundary = content_type.split('boundary=')[1].encode('utf-8')
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)

        parts = body.split(b'--' + boundary)
        for part in parts:
            if b'filename="' in part:
                header_part, file_data = part.split(b'\r\n\r\n', 1)
                file_data = file_data.rsplit(b'\r\n', 1)[0]
                
                header_text = header_part.decode('utf-8', errors='ignore')
                filename_match = re.search(r'filename="([^"]+)"', header_text)
                if filename_match:
                    filename = filename_match.group(1)
                    return os.path.basename(filename), file_data
        return None, None

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
            
            if session['role'] == 'admin':
                html = html.replace("<!--ADMIN_CLASS-->", "admin-badge")
                html = html.replace("<!--ROLE_ADMIN_ONLY-->", "").replace("<!--END_ADMIN_ROLE-->", "")
                html = html.replace("<!--ROLE_TEACHER_ONLY-->", "").replace("<!--END_ROLE-->", "")
                html = re.sub(r'<!--ROLE_STUDENT_ONLY-->.*?<!--END_STUDENT_ROLE-->', '', html, flags=re.DOTALL)
                
                key_info = session.get('key_info', {})
                html = html.replace("<!--ADMIN_NAME-->", key_info.get("name", "System Administrator"))
                html = html.replace("<!--SUPER_KEY-->", key_info.get("super_key", "UNKNOWN"))
                html = html.replace("<!--ADMIN_PHOTO-->", key_info.get("photo_url", ""))
            elif session['role'] == 'teacher':
                html = html.replace("<!--ADMIN_CLASS-->", "")
                html = re.sub(r'<!--ROLE_ADMIN_ONLY-->.*?<!--END_ADMIN_ROLE-->', '', html, flags=re.DOTALL)
                html = re.sub(r'<!--ROLE_STUDENT_ONLY-->.*?<!--END_STUDENT_ROLE-->', '', html, flags=re.DOTALL)
                html = html.replace("<!--ROLE_TEACHER_ONLY-->", "").replace("<!--END_ROLE-->", "")
            else:
                html = html.replace("<!--ADMIN_CLASS-->", "")
                html = re.sub(r'<!--ROLE_ADMIN_ONLY-->.*?<!--END_ADMIN_ROLE-->', '', html, flags=re.DOTALL)
                html = re.sub(r'<!--ROLE_TEACHER_ONLY-->.*?<!--END_ROLE-->', '', html, flags=re.DOTALL)
                html = html.replace("<!--ROLE_STUDENT_ONLY-->", "").replace("<!--END_STUDENT_ROLE-->", "")
                
            self.send_html(html)
            return

        if path == "/api/admin-heartbeat":
            if not session or session.get('role') != 'admin':
                self.send_json({"valid": False}, 401)
                return
            key_data = scan_usb_for_key()
            if key_data and key_data.get("super_key") == session.get('key_info', {}).get('super_key'):
                self.send_json({"valid": True})
            else:
                cookie_header = self.headers.get('Cookie')
                if cookie_header:
                    cookie = cookies.SimpleCookie()
                    cookie.load(cookie_header)
                    if 'session_id' in cookie:
                        SESSIONS.pop(cookie['session_id'].value, None)
                self.send_json({"valid": False})
            return

        if path == "/api/admin/users":
            if not session or session.get('role') != 'admin':
                self.send_json({"error": "Forbidden"}, 403)
                return
            self.send_json(USERS)
            return

        if path == "/launch-wps":
            if not session:
                self.redirect("/login")
                return
            files = os.listdir(UPLOAD_DIR) if os.path.exists(UPLOAD_DIR) else []
            if files:
                target = os.path.join(UPLOAD_DIR, files[0])
                open_local_file(target)
            self.redirect("/")
            return

        if path == "/api/files":
            if not session:
                self.send_json({"error": "Unauthorized"}, 401)
                return
            files = os.listdir(UPLOAD_DIR) if os.path.exists(UPLOAD_DIR) else []
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
            filename = urllib.parse.unquote(path[len("/uploads/"):])
            filepath = os.path.join(UPLOAD_DIR, os.path.basename(filename))
            if os.path.exists(filepath):
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
            key_data = scan_usb_for_key()
            if key_data:
                sid = str(uuid.uuid4())
                admin_email = key_data.get("email", "admin@Digiboardleaning.com")
                SESSIONS[sid] = {
                    "username": admin_email,
                    "role": "admin",
                    "key_info": key_data
                }
                USERS[admin_email] = {"password": "", "role": "admin"}

                self.send_response(302)
                self.send_header("Set-Cookie", f"session_id={sid}; Path=/; HttpOnly")
                self.send_header("Location", "/")
                self.set_no_cache_headers()
                self.end_headers()
            else:
                err_html = LOGIN_HTML.replace(
                    "<!--ERROR-->", 
                    '<div class="error">❌ Hardware Security Key Not Detected! Connect your USB drive containing admin_key.json.</div>'
                )
                self.send_html(err_html, 401)
            return

        if path == "/login":
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            params = urllib.parse.parse_qs(body)
            username = params.get('username', [''])[0]
            password = params.get('password', [''])[0]

            if username in USERS and USERS[username]['password'] == password:
                sid = str(uuid.uuid4())
                SESSIONS[sid] = {"username": username, "role": USERS[username]['role']}
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
            prefix = body.get('prefix', 'board')
            count = int(body.get('count', 1))
            password = body.get('password', '2234269580')

            created = 0
            for i in range(1, count + 1):
                acc_email = f"{prefix}{i:02d}@Digiboardleaning.com"
                USERS[acc_email] = {"password": password, "role": role}
                created += 1

            self.send_json({"status": "ok", "created": created})
            return

        if path == "/upload":
            if session['role'] not in ['teacher', 'admin']:
                self.send_json({"error": "Forbidden"}, 403)
                return
            filename, file_data = self.parse_multipart()
            if filename and file_data:
                if not os.path.exists(UPLOAD_DIR):
                    os.makedirs(UPLOAD_DIR)
                filepath = os.path.join(UPLOAD_DIR, filename)
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
        session = self.get_session()

        if not session or session['role'] not in ['teacher', 'admin']:
            self.send_json({"error": "Forbidden"}, 403)
            return

        if path == "/api/delete-file":
            params = urllib.parse.parse_qs(parsed.query)
            filename = params.get('name', [''])[0]
            if filename:
                filepath = os.path.join(UPLOAD_DIR, os.path.basename(filename))
                if os.path.exists(filepath):
                    os.remove(filepath)
            self.send_json({"status": "deleted"})
            return

        self.send_error(404)

if __name__ == "__main__":
    if not os.path.exists(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR)
    
    with socketserver.TCPServer(("", PORT), DigiBoardHandler) as httpd:
        print(f"DigiBoard Master Console running at http://localhost:{PORT}")
        httpd.serve_forever()
