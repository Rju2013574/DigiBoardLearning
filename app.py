import http.server
import socketserver
import json
import urllib.parse
from http import cookies
import os
import uuid
import threading
import re

# Safely attempt to import psutil for USB drive scanning
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

PORT = 8000
UPLOAD_DIR = "uploads"
SESSIONS = {}
BOARD_CACHE = "[]"
CACHE_LOCK = threading.Lock()

# User Account Store (in-memory, expandable via Admin console)
USERS = {
    "juraghav@Digiboardleaning.com": {"password": "2234269580", "role": "teacher"},
    "socialstudiesclass@Digiboardleaning.com": {"password": "2234269580", "role": "student"}
}

EXPECTED_SUPER_KEY = "SUPER-SECRET-PASSCODE-9999"  # Must match the super_key_id in admin_key.ssh

def scan_usb_for_ssh_key():
    """Scans connected removable drives for 'admin_key.ssh'"""
    if not HAS_PSUTIL:
        return False, None, None
    try:
        for partition in psutil.disk_partitions(all=False):
            if 'removable' in partition.opts or partition.fstype != '':
                key_path = os.path.join(partition.mountpoint, "admin_key.ssh")
                if os.path.exists(key_path):
                    try:
                        with open(key_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            return True, data, partition.mountpoint
                    except Exception as e:
                        print(f"Error reading SSH key file: {e}")
    except Exception as e:
        print(f"USB Scan exception: {e}")
    return False, None, None

LOGIN_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>DigiBoard - Login</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #070d19; color: #f8fafc; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }
        .login-card { background: #0f172a; border: 1px solid #1e293b; padding: 2.5rem; border-radius: 12px; width: 360px; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.6); }
        h2 { text-align: center; margin-top: 0; color: #38bdf8; font-size: 1.5rem; }
        label { font-size: 0.85rem; color: #94a3b8; display: block; margin-top: 1rem; }
        input { width: 100%; padding: 0.65rem; margin-top: 0.3rem; border: 1px solid #334155; background: #070d19; color: #fff; border-radius: 6px; box-sizing: border-box; }
        input:focus { outline: none; border-color: #38bdf8; }
        button { width: 100%; padding: 0.75rem; margin-top: 1.2rem; background: #0284c7; border: none; color: white; border-radius: 6px; font-weight: bold; cursor: pointer; transition: background 0.2s; }
        button:hover { background: #0369a1; }
        .admin-btn { background: #7c3aed; }
        .admin-btn:hover { background: #6d28d9; }
        .error { color: #ef4444; font-size: 0.875rem; text-align: center; margin-bottom: 1rem; background: rgba(239, 68, 68, 0.1); padding: 0.5rem; border-radius: 4px; }
        .status-box { display: none; margin-top: 1rem; padding: 0.75rem; border-radius: 6px; background: #1e293b; text-align: center; font-size: 0.85rem; }
    </style>
</head>
<body>
    <div class="login-card">
        <h2>DigiBoard Master Console</h2>
        <!--ERROR-->
        <form action="/login" method="POST">
            <label>Username / Email</label>
            <input type="text" name="username" placeholder="user@domain.com" required>
            <label>Password</label>
            <input type="password" name="password" required>
            <button type="submit">Sign In</button>
        </form>

        <hr style="border: 0; border-top: 1px solid #1e293b; margin: 1.5rem 0;">

        <button type="button" class="admin-btn" onclick="verifyAdminHardwareKey()">🔑 Login in Admin Mode (SSH USB)</button>
        <div class="status-box" id="status-box">Scanning for USB Hardware Key...</div>
    </div>

    <script>
        function verifyAdminHardwareKey() {
            const status = document.getElementById('status-box');
            status.style.display = 'block';
            status.style.color = '#38bdf8';
            status.innerText = "🔍 Scanning USB ports for SSH key file...";

            fetch('/api/admin/verify-ssh', { method: 'POST' })
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        status.style.color = '#10b981';
                        status.innerText = "✅ Hardware Key Verified! Accessing Admin Console...";
                        setTimeout(() => window.location.href = "/", 1000);
                    } else {
                        status.style.color = '#ef4444';
                        status.innerText = "❌ " + data.message;
                    }
                })
                .catch(() => {
                    status.style.color = '#ef4444';
                    status.innerText = "❌ Verification error. Ensure USB key is connected.";
                });
        }
    </script>
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
        .admin-badge { background: #7c3aed; color: #fff; }
        .admin-avatar { width: 36px; height: 36px; border-radius: 50%; border: 2px solid #7c3aed; object-fit: cover; }
        .logout-btn { background: transparent; border: 1px solid #1e293b; color: #38bdf8; padding: 0.4rem 1rem; border-radius: 4px; cursor: pointer; font-size: 0.85rem; }
        .logout-btn:hover { background: #1e293b; color: #fff; }
        .admin-banner { background: #581c87; color: #f3e8ff; padding: 0.5rem; text-align: center; font-size: 0.85rem; font-weight: bold; letter-spacing: 0.5px; }
        .console-container { flex: 1; display: flex; justify-content: center; align-items: center; padding: 2rem; }
        .grid-wrapper { background: rgba(15, 23, 42, 0.6); border: 1px solid #172554; border-radius: 16px; padding: 2.5rem; display: flex; gap: 2rem; box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5); flex-wrap: wrap; justify-content: center; }
        .app-card { width: 150px; height: 150px; background: #091326; border: 1px solid #1e293b; border-radius: 14px; display: flex; flex-direction: column; justify-content: center; align-items: center; cursor: pointer; transition: all 0.2s ease; gap: 0.85rem; }
        .app-card:hover { transform: translateY(-4px); border-color: #38bdf8; background: #0e1d38; box-shadow: 0 10px 20px -5px rgba(56, 189, 248, 0.2); }
        .app-icon { width: 56px; height: 56px; border-radius: 14px; display: flex; justify-content: center; align-items: center; }
        .icon-wb { background: #2563eb; }
        .icon-doc { background: #ef4444; }
        .icon-fm { background: #eab308; }
        .icon-admin { background: #7c3aed; }
        .app-icon svg { width: 30px; height: 30px; fill: white; }
        .app-title { font-size: 0.85rem; font-weight: 600; color: #cbd5e1; text-align: center; }
        
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(3, 7, 18, 0.9); justify-content: center; align-items: center; z-index: 100; }
        .modal-content { background: #0f172a; border: 1px solid #1e293b; border-radius: 12px; width: 95%; max-width: 1150px; height: 88vh; display: flex; flex-direction: column; overflow: hidden; position: relative; }
        .modal-header { display: flex; justify-content: space-between; align-items: center; padding: 1rem 1.5rem; border-bottom: 1px solid #1e293b; background: #070d19; }
        .modal-header h3 { margin: 0; color: #38bdf8; font-size: 1.1rem; }
        .close-btn { color: #94a3b8; font-size: 1.5rem; font-weight: bold; cursor: pointer; line-height: 1; }
        .close-btn:hover { color: #fff; }
        .modal-body { padding: 1.5rem; overflow-y: auto; flex: 1; color: #f8fafc; }
        
        /* Whiteboard styling */
        .wb-viewport { position: relative; width: 100%; height: 100%; flex: 1; background: #ffffff; border-radius: 8px; overflow: hidden; }
        canvas { display: block; width: 100%; height: 100%; background: radial-gradient(#d1d5db 1px, transparent 1px); background-size: 20px 20px; cursor: crosshair; touch-action: none; }
        .markup-palette { position: absolute; left: 20px; top: 50%; transform: translateY(-50%); background: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 30px; padding: 12px 8px; display: flex; flex-direction: column; align-items: center; gap: 10px; box-shadow: 0 12px 30px rgba(0,0,0,0.25); z-index: 20; width: 58px; }
        .markup-btn { width: 38px; height: 38px; border-radius: 50%; border: none; background: transparent; cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 1.1rem; transition: background 0.15s, transform 0.15s; color: #334155; padding: 0; }
        .markup-btn:hover { background: #e2e8f0; transform: scale(1.08); }
        .markup-btn.active { background: #ffffff; box-shadow: 0 2px 6px rgba(0,0,0,0.15); border: 2px solid #0284c7; }
        .palette-divider { width: 30px; height: 1px; background: #cbd5e1; margin: 2px 0; }
        .color-dot { width: 26px; height: 26px; border-radius: 50%; border: 2px solid white; box-shadow: 0 1px 4px rgba(0,0,0,0.3); cursor: pointer; transition: transform 0.15s; }
        .color-dot.active { transform: scale(1.2); border-color: #0284c7; }

        /* File manager & Admin Table styling */
        .file-item { display: flex; justify-content: space-between; align-items: center; padding: 0.75rem 1rem; background: #070d19; border: 1px solid #1e293b; border-radius: 6px; margin-bottom: 0.5rem; }
        .file-item a { color: #38bdf8; text-decoration: none; font-weight: 500; font-size: 0.95rem; }
        .delete-btn { color: #ef4444; background: rgba(239, 68, 68, 0.1); border: 1px solid #ef4444; padding: 0.3rem 0.6rem; border-radius: 4px; cursor: pointer; font-weight: bold; font-size: 0.8rem; }
        .form-section { background: #070d19; border: 1px solid #1e293b; padding: 1.2rem; border-radius: 8px; margin-bottom: 1.5rem; }
        .form-section h4 { margin-top: 0; color: #38bdf8; margin-bottom: 1rem; }
        .form-row { display: flex; gap: 1rem; margin-bottom: 1rem; }
        .form-group { flex: 1; }
        .form-group label { display: block; font-size: 0.8rem; color: #94a3b8; margin-bottom: 0.3rem; }
        .form-group input, .form-group select, .form-group textarea { width: 100%; padding: 0.6rem; background: #0f172a; border: 1px solid #334155; border-radius: 6px; color: #fff; font-family: inherit; }
        .action-btn { background: #0284c7; color: white; border: none; padding: 0.6rem 1.2rem; border-radius: 6px; font-weight: bold; cursor: pointer; }
        .action-btn:hover { background: #0369a1; }
        table { width: 100%; border-collapse: collapse; margin-top: 1rem; }
        th, td { padding: 0.75rem; text-align: left; border-bottom: 1px solid #1e293b; font-size: 0.875rem; }
        th { background: #070d19; color: #94a3b8; font-weight: 600; }
    </style>
</head>
<body>
    <!--ADMIN_BANNER_START-->
    <div class="admin-banner">🔒 SECURE ADMIN MODE ACTIVE — USB Hardware Dongle Connected</div>
    <!--ADMIN_BANNER_END-->

    <header>
        <div class="header-title">DigiBoard Master Console</div>
        <div class="user-section">
            <!--ADMIN_PHOTO_START-->
            <img class="admin-avatar" src="<!--ADMIN_PHOTO_URL-->" alt="Admin Avatar">
            <!--ADMIN_PHOTO_END-->
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
            <div class="app-card" onclick="openAdminAccounts()">
                <div class="app-icon icon-admin">
                    <svg viewBox="0 0 24 24"><path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"/></svg>
                </div>
                <div class="app-title">Account Manager</div>
            </div>
            <!--END_ADMIN_ROLE-->
        </div>
    </div>

    <!-- Whiteboard Modal -->
    <div class="modal" id="whiteboard-modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3>DigiBoard Interactive Whiteboard</h3>
                <span class="close-btn" onclick="closeApp('whiteboard-modal')">&times;</span>
            </div>
            <div class="modal-body" style="padding:0;">
                <div class="wb-viewport" id="wb-container">
                    <canvas id="board"></canvas>
                    <div class="markup-palette">
                        <button class="markup-btn active" id="tool-pen" onclick="selectTool('pen')">✏️</button>
                        <button class="markup-btn" id="tool-eraser" onclick="selectTool('eraser')">🧹</button>
                        <div class="palette-divider"></div>
                        <div class="color-dot active" style="background:#000000;" onclick="setColor('#000000', this)"></div>
                        <div class="color-dot" style="background:#ef4444;" onclick="setColor('#ef4444', this)"></div>
                        <div class="color-dot" style="background:#3b82f6;" onclick="setColor('#3b82f6', this)"></div>
                        <div class="color-dot" style="background:#10b981;" onclick="setColor('#10b981', this)"></div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- File Manager Modal -->
    <div class="modal" id="filemanager-modal">
        <div class="modal-content" style="max-width: 650px; height:auto;">
            <div class="modal-header">
                <h3>Class File Manager</h3>
                <span class="close-btn" onclick="closeApp('filemanager-modal')">&times;</span>
            </div>
            <div class="modal-body" style="height: 480px;">
                <form action="/upload" method="POST" enctype="multipart/form-data" style="margin-bottom: 1.5rem; background: #070d19; padding: 1rem; border-radius: 6px; border: 1px solid #1e293b;">
                    <label style="display:block; margin-bottom: 0.5rem; color:#94a3b8; font-weight:600;">Upload New Document:</label>
                    <input type="file" name="file" required style="margin-bottom:0.75rem; color:white; width:100%;">
                    <button type="submit" class="action-btn" style="width:100%;">Upload File</button>
                </form>
                <ul id="file-list-container" style="list-style:none; padding:0; margin:0;">
                    <li style="color:#94a3b8; text-align:center; padding: 2rem 0;">Loading files...</li>
                </ul>
            </div>
        </div>
    </div>

    <!-- Admin Mass Account Creator Modal -->
    <!--ROLE_ADMIN_ONLY-->
    <div class="modal" id="admin-accounts-modal">
        <div class="modal-content" style="max-width: 800px;">
            <div class="modal-header">
                <h3>Mass Account Creator (Teachers & Digital Boards)</h3>
                <span class="close-btn" onclick="closeApp('admin-accounts-modal')">&times;</span>
            </div>
            <div class="modal-body">
                <!-- Single Account Form -->
                <div class="form-section">
                    <h4>➕ Create Single Account</h4>
                    <div class="form-row">
                        <div class="form-group">
                            <label>Username / ID</label>
                            <input type="text" id="single-username" placeholder="teacher1@school.com or board101">
                        </div>
                        <div class="form-group">
                            <label>Password</label>
                            <input type="password" id="single-password" placeholder="Passcode">
                        </div>
                        <div class="form-group">
                            <label>Account Role</label>
                            <select id="single-role">
                                <option value="teacher">Teacher (Full Access)</option>
                                <option value="student">Digital Board / Classroom (View Only)</option>
                            </select>
                        </div>
                    </div>
                    <button class="action-btn" onclick="createSingleAccount()">Create Account</button>
                </div>

                <!-- Mass Account Batch Form -->
                <div class="form-section">
                    <h4>⚡ Batch / Massive Account Creator (CSV Format)</h4>
                    <p style="font-size:0.8rem; color:#94a3b8; margin-top:-0.5rem;">Format per line: <code>username, password, role</code> (role must be <b>teacher</b> or <b>student</b>)</p>
                    <div class="form-group">
                        <textarea id="mass-accounts-text" rows="5" placeholder="teacher101@school.com, pass123, teacher&#10;class6a_board@school.com, pass123, student&#10;class6b_board@school.com, pass123, student"></textarea>
                    </div>
                    <button class="action-btn" style="background:#7c3aed;" onclick="createMassiveAccounts()">Generate Batch Accounts</button>
                </div>

                <!-- Account List -->
                <h4>Active Accounts System List</h4>
                <table>
                    <thead>
                        <tr>
                            <th>Username / ID</th>
                            <th>Role</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody id="accounts-table-body">
                        <tr><td colspan="3">Loading active accounts...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    <!--END_ADMIN_ROLE-->

    <script>
        const USER_ROLE = "<!--USER_ROLE-->";

        // Active USB Heartbeat Monitoring for Admin
        if (USER_ROLE === "admin") {
            setInterval(() => {
                fetch('/api/admin/heartbeat')
                    .then(r => r.json())
                    .then(data => {
                        if (!data.connected) {
                            alert("⚠️ USB Hardware Key Disconnected! Logging out for security...");
                            window.location.href = "/logout";
                        }
                    })
                    .catch(() => { window.location.href = "/logout"; });
            }, 2000);
        }

        function openApp(id) { document.getElementById(id).style.display = 'flex'; }
        function closeApp(id) { document.getElementById(id).style.display = 'none'; }
        function launchWPS() { window.location.href = '/launch-wps'; }

        function openFileManager() {
            openApp('filemanager-modal');
            loadFileList();
        }

        function loadFileList() {
            fetch('/api/files?t=' + Date.now())
                .then(r => r.json())
                .then(files => {
                    const container = document.getElementById('file-list-container');
                    if (!files || files.length === 0) {
                        container.innerHTML = '<li style="color:#94a3b8; text-align:center; padding:2rem 0;">No files uploaded.</li>';
                        return;
                    }
                    container.innerHTML = files.map(f => `
                        <li class="file-item">
                            <a href="/uploads/${encodeURIComponent(f)}" target="_blank" download="${f}">📄 ${f}</a>
                            ${USER_ROLE === 'teacher' || USER_ROLE === 'admin' ? `<button class="delete-btn" onclick="deleteFile('${f}')">Delete</button>` : ''}
                        </li>
                    `).join('');
                });
        }

        function deleteFile(filename) {
            if (!confirm('Delete ' + filename + '?')) return;
            fetch('/api/delete-file?name=' + encodeURIComponent(filename), { method: 'DELETE' })
                .then(() => loadFileList());
        }

        /* Admin Accounts Management JavaScript */
        function openAdminAccounts() {
            openApp('admin-accounts-modal');
            loadAccountsList();
        }

        function loadAccountsList() {
            fetch('/api/admin/users')
                .then(r => r.json())
                .then(users => {
                    const tbody = document.getElementById('accounts-table-body');
                    tbody.innerHTML = Object.keys(users).map(u => `
                        <tr>
                            <td>${u}</td>
                            <td><span class="user-role-badge">${users[u].role}</span></td>
                            <td>
                                <button class="delete-btn" onclick="deleteUser('${u}')">Delete</button>
                            </td>
                        </tr>
                    `).join('');
                });
        }

        function createSingleAccount() {
            const u = document.getElementById('single-username').value.trim();
            const p = document.getElementById('single-password').value.trim();
            const r = document.getElementById('single-role').value;

            if(!u || !p) { alert('Fill in all fields'); return; }

            fetch('/api/admin/create-user', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ accounts: [{ username: u, password: p, role: r }] })
            })
            .then(res => res.json())
            .then(() => {
                document.getElementById('single-username').value = '';
                document.getElementById('single-password').value = '';
                loadAccountsList();
            });
        }

        function createMassiveAccounts() {
            const text = document.getElementById('mass-accounts-text').value.trim();
            if(!text) return;

            const lines = text.split('\\n');
            const accounts = [];

            lines.forEach(line => {
                const parts = line.split(',').map(s => s.trim());
                if(parts.length >= 3) {
                    accounts.push({ username: parts[0], password: parts[1], role: parts[2] });
                }
            });

            if(accounts.length === 0) {
                alert('No valid accounts found. Ensure format is username, password, role');
                return;
            }

            fetch('/api/admin/create-user', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ accounts: accounts })
            })
            .then(res => res.json())
            .then(data => {
                alert(`Successfully processed ${data.added} accounts!`);
                document.getElementById('mass-accounts-text').value = '';
                loadAccountsList();
            });
        }

        function deleteUser(username) {
            if(!confirm('Delete account ' + username + '?')) return;
            fetch('/api/admin/delete-user', {
                method: 'DELETE',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ username: username })
            }).then(() => loadAccountsList());
        }

        /* Whiteboard initialization */
        const canvas = document.getElementById('board');
        const ctx = canvas.getContext('2d');
        let isDrawing = false, lines = [];

        function selectTool(t) {}
        function setColor(c, el) {}
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
                html = html.replace("<!--ADMIN_PHOTO_URL-->", session.get('photo', ''))
                html = html.replace("<!--ROLE_ADMIN_ONLY-->", "").replace("<!--END_ADMIN_ROLE-->", "")
            else:
                html = re.sub(r'<!--ADMIN_BANNER_START-->.*?<!--ADMIN_BANNER_END-->', '', html, flags=re.DOTALL)
                html = re.sub(r'<!--ADMIN_PHOTO_START-->.*?<!--ADMIN_PHOTO_END-->', '', html, flags=re.DOTALL)
                html = re.sub(r'<!--ROLE_ADMIN_ONLY-->.*?<!--END_ADMIN_ROLE-->', '', html, flags=re.DOTALL)
                html = html.replace("<!--ADMIN_CLASS-->", "")

            self.send_html(html)
            return

        if path == "/api/admin/heartbeat":
            if not session or session.get('role') != 'admin':
                self.send_json({"connected": False}, 401)
                return
            found, key_data, _ = scan_usb_for_ssh_key()
            if found and key_data.get('super_key_id') == EXPECTED_SUPER_KEY:
                self.send_json({"connected": True})
            else:
                self.send_json({"connected": False})
            return

        if path == "/api/admin/users":
            if not session or session.get('role') != 'admin':
                self.send_json({"error": "Forbidden"}, 403)
                return
            self.send_json(USERS)
            return

        if path == "/api/files":
            if not session:
                self.send_json({"error": "Unauthorized"}, 401)
                return
            files = os.listdir(UPLOAD_DIR) if os.path.exists(UPLOAD_DIR) else []
            self.send_json(files)
            return

        self.send_error(404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/admin/verify-ssh":
            found, key_data, mountpoint = scan_usb_for_ssh_key()
            if not found:
                self.send_json({"success": False, "message": "No USB Pen Drive with 'admin_key.ssh' detected."}, 404)
                return

            if key_data.get("super_key_id") != EXPECTED_SUPER_KEY:
                self.send_json({"success": False, "message": "Invalid Super Key Passcode on Pen Drive."}, 403)
                return

            sid = str(uuid.uuid4())
            SESSIONS[sid] = {
                "username": key_data.get("admin_name", "Admin"),
                "email": key_data.get("email", "admin@domain.com"),
                "role": "admin",
                "photo": key_data.get("photo_b64", ""),
                "usb_mount": mountpoint
            }

            self.send_response(200)
            self.send_header("Set-Cookie", f"session_id={sid}; Path=/; HttpOnly")
            self.set_no_cache_headers()
            self.send_json({"success": True})
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
        if not session or session.get('role') != 'admin':
            self.send_json({"error": "Forbidden"}, 403)
            return

        if path == "/api/admin/create-user":
            content_length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(content_length).decode('utf-8'))
            accounts = body.get('accounts', [])
            
            added = 0
            for acc in accounts:
                u, p, r = acc.get('username'), acc.get('password'), acc.get('role', 'student')
                if u and p:
                    USERS[u] = {"password": p, "role": r}
                    added += 1
            self.send_json({"success": True, "added": added})
            return

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        session = self.get_session()

        if not session or session.get('role') != 'admin':
            self.send_json({"error": "Forbidden"}, 403)
            return

        if path == "/api/admin/delete-user":
            content_length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(content_length).decode('utf-8'))
            u = body.get('username')
            if u in USERS:
                del USERS[u]
            self.send_json({"success": True})
            return

if __name__ == "__main__":
    if not os.path.exists(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR)
    
    with socketserver.TCPServer(("", PORT), DigiBoardHandler) as httpd:
        print(f"DigiBoard Console running at http://localhost:{PORT}")
        httpd.serve_forever()
