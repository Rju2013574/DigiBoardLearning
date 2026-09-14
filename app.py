import http.server
import socketserver
import json
import urllib.parse
from http import cookies
import os
import uuid
import threading
import re
import psutil

PORT = 8000
UPLOAD_DIR = "uploads"
SESSIONS = {}
BOARD_CACHE = "[]"
CACHE_LOCK = threading.Lock()

USERS = {
    "juraghav@Digiboardleaning.com": {"password": "2234269580", "role": "teacher"},
    "socialstudiesclass@Digiboardleaning.com": {"password": "2234269580", "role": "student"}
}

EXPECTED_SUPER_KEY = "SUPER-SECRET-PASSCODE-9999"  # Match this with the key on your USB drive

def scan_usb_for_ssh_key():
    """Scans all connected removable drives for 'admin_key.ssh'"""
    for partition in psutil.disk_partitions(all=False):
        # 'removable' flag or external mounts
        if 'removable' in partition.opts or partition.fstype != '':
            key_path = os.path.join(partition.mountpoint, "admin_key.ssh")
            if os.path.exists(key_path):
                try:
                    with open(key_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        return True, data, partition.mountpoint
                except Exception as e:
                    print(f"Error reading SSH key file: {e}")
    return False, None, None

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
        button { width: 100%; padding: 0.75rem; margin-top: 1.2rem; background: #0284c7; border: none; color: white; border-radius: 6px; font-weight: bold; cursor: pointer; }
        button:hover { background: #0369a1; }
        .admin-btn { background: #7c3aed; }
        .admin-btn:hover { background: #6d28d9; }
        .error { color: #ef4444; font-size: 0.875rem; text-align: center; margin-bottom: 1rem; background: rgba(239, 68, 68, 0.1); padding: 0.5rem; border-radius: 4px; }
        .status-box { display: none; margin-top: 1rem; padding: 0.75rem; border-radius: 6px; background: #1e293b; text-align: center; font-size: 0.85rem; }
    </style>
</head>
<body>
    <div class="login-card">
        <h2>DigiBoard Console</h2>
        <!--ERROR-->
        <form action="/login" method="POST">
            <label>Username</label>
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
            status.innerText = "🔍 Scanning USB ports for SSH verification key...";

            fetch('/api/admin/verify-ssh', { method: 'POST' })
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        status.style.color = '#10b981';
                        status.innerText = "✅ Hardware Key Verified! Redirecting...";
                        setTimeout(() => window.location.href = "/", 1000);
                    } else {
                        status.style.color = '#ef4444';
                        status.innerText = "❌ " + data.message;
                    }
                })
                .catch(() => {
                    status.style.color = '#ef4444';
                    status.innerText = "❌ Verification failed. Ensure USB Pen Drive is connected.";
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
        .header-title { font-size: 1.25rem; font-weight: bold; color: #ffffff; }
        .user-section { display: flex; align-items: center; gap: 1rem; font-size: 0.875rem; color: #94a3b8; }
        .user-id { color: #ffffff; font-weight: 600; }
        .user-role-badge { background: #1e293b; color: #38bdf8; padding: 0.2rem 0.6rem; border-radius: 4px; font-weight: 600; text-transform: uppercase; font-size: 0.75rem; }
        .admin-badge { background: #7c3aed; color: #fff; }
        .admin-avatar { width: 36px; height: 36px; border-radius: 50%; border: 2px solid #7c3aed; object-fit: cover; }
        .logout-btn { background: transparent; border: 1px solid #1e293b; color: #38bdf8; padding: 0.4rem 1rem; border-radius: 4px; cursor: pointer; }
        .console-container { flex: 1; display: flex; justify-content: center; align-items: center; padding: 2rem; }
        .admin-banner { background: #581c87; color: #f3e8ff; padding: 0.5rem; text-align: center; font-size: 0.85rem; font-weight: bold; letter-spacing: 0.5px; }
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
        <h2 style="color: #94a3b8;">Welcome to DigiBoard Console</h2>
    </div>

    <script>
        const IS_ADMIN = "<!--USER_ROLE-->" === "admin";

        // Active USB Heartbeat Monitoring (Auto Logout if USB Pen Drive is unplugged)
        if (IS_ADMIN) {
            setInterval(() => {
                fetch('/api/admin/heartbeat')
                    .then(r => r.json())
                    .then(data => {
                        if (!data.connected) {
                            alert("⚠️ USB Hardware Key Disconnected! Logging out for security...");
                            window.location.href = "/logout";
                        }
                    })
                    .catch(() => {
                        window.location.href = "/logout";
                    });
            }, 2000); // Checks every 2 seconds
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
            else:
                html = re.sub(r'<!--ADMIN_BANNER_START-->.*?<!--ADMIN_BANNER_END-->', '', html, flags=re.DOTALL)
                html = re.sub(r'<!--ADMIN_PHOTO_START-->.*?<!--ADMIN_PHOTO_END-->', '', html, flags=re.DOTALL)
                html = html.replace("<!--ADMIN_CLASS-->", "")

            self.send_html(html)
            return

        if path == "/api/admin/heartbeat":
            if not session or session.get('role') != 'admin':
                self.send_json({"connected": False}, 401)
                return
            
            # Check if drive is still attached
            found, key_data, _ = scan_usb_for_ssh_key()
            if found and key_data.get('super_key_id') == EXPECTED_SUPER_KEY:
                self.send_json({"connected": True})
            else:
                self.send_json({"connected": False})
            return

        self.send_error(404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/admin/verify-ssh":
            found, key_data, mountpoint = scan_usb_for_ssh_key()
            if not found:
                self.send_json({"success": False, "message": "No USB Pen Drive containing 'admin_key.ssh' detected."}, 404)
                return

            if key_data.get("super_key_id") != EXPECTED_SUPER_KEY:
                self.send_json({"success": False, "message": "Invalid Super Key Passcode on Pen Drive."}, 403)
                return

            # Login Admin Session
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

if __name__ == "__main__":
    if not os.path.exists(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR)
    
    with socketserver.TCPServer(("", PORT), DigiBoardHandler) as httpd:
        print(f"DigiBoard Console running at http://localhost:{PORT}")
        httpd.serve_forever()
