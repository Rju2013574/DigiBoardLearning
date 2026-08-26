import update
update.start_background_updater()
import http.server
import socketserver
import urllib.parse
import urllib.request
import json
import os
import uuid
import subprocess
import threading
import socket
from http import cookies

PORT = 8000
UPLOAD_DIR = "uploads"

# --- SUPABASE CONFIG ---
SUPABASE_URL = "https://wkiihxsqvwdsmmppqrwx.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndraWloeHNxdndkc21tcHBxcnd4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODcwNDk3ODUsImV4cCI6MjEwMjYyNTc4NX0.kqcgJH-bBHDgwMkxg7vbdXIvPUQynA2fPnq65oQ0v20"

os.makedirs(UPLOAD_DIR, exist_ok=True)
SESSIONS = {}
BOARD_CACHE = "[]"

USERS = {
    "juraghav@Digiboardleaning.com": {"password": "2234269580", "role": "teacher"},
    "socialstudiesclass@Digiboardleaning.com": {"password": "2234269580", "role": "student"}
}

def get_local_ip():
    """Detects the computer's local Wi-Fi/LAN IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "127.0.0.1"

def supabase_request(endpoint, method="GET", data=None):
    url = f"{SUPABASE_URL}/rest/v1/{endpoint}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    body = json.dumps(data).encode('utf-8') if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            res_body = resp.read().decode('utf-8')
            return json.loads(res_body) if res_body else []
    except Exception as e:
        print(f"Cloud DB Error [{endpoint}]:", e)
        return []

def init_board():
    global BOARD_CACHE
    res = supabase_request("whiteboard?id=eq.1&select=lines")
    if res and len(res) > 0 and 'lines' in res[0]:
        BOARD_CACHE = res[0]['lines']

threading.Thread(target=init_board, daemon=True).start()

LOGIN_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>DigiBoard - Login</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, sans-serif; }
        body { background: radial-gradient(circle at 50% 50%, #0c2340 0%, #020b18 100%); color: #e0f2fe; min-height: 100vh; display: flex; justify-content: center; align-items: center; }
        .login-card { background: rgba(8, 28, 58, 0.85); backdrop-filter: blur(12px); padding: 40px; border-radius: 16px; border: 1px solid rgba(0, 195, 255, 0.4); box-shadow: 0 0 30px rgba(0, 195, 255, 0.2); width: 380px; }
        h2 { text-align: center; margin-bottom: 25px; color: #38bdf8; }
        input { width: 100%; padding: 12px; margin-bottom: 15px; background: rgba(15, 42, 86, 0.7); border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 6px; color: #fff; outline: none; }
        button { width: 100%; padding: 12px; background: #0284c7; color: white; border: none; border-radius: 6px; font-weight: bold; cursor: pointer; }
        button:hover { background: #0369a1; }
        .error { color: #ef4444; margin-bottom: 15px; font-size: 14px; text-align: center; }
    </style>
</head>
<body>
    <div class="login-card">
        <h2>DigiBoard Login</h2>
        <!--ERROR-->
        <form action="/login" method="post">
            <input type="text" name="username" placeholder="Username / User ID" required>
            <input type="password" name="password" placeholder="Password" required>
            <button type="submit">Sign In</button>
        </form>
    </div>
</body>
</html>"""

TEACHER_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>DigiBoard Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, sans-serif; }
        body { background: radial-gradient(circle at 50% 50%, #0c2340 0%, #020b18 100%); color: #e0f2fe; min-height: 100vh; display: flex; flex-direction: column; }
        header { background: rgba(4, 19, 41, 0.85); backdrop-filter: blur(10px); padding: 15px 30px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(0, 195, 255, 0.3); }
        .user-info a { color: #38bdf8; text-decoration: none; margin-left: 15px; padding: 5px 12px; border: 1px solid #38bdf8; border-radius: 4px; }
        .main-container { display: flex; justify-content: center; align-items: center; flex-grow: 1; padding: 40px; }
        .app-grid { display: grid; grid-template-columns: repeat(3, 180px); gap: 40px; background: rgba(8, 28, 58, 0.75); backdrop-filter: blur(12px); padding: 40px; border-radius: 20px; border: 1px solid rgba(0, 195, 255, 0.4); }
        .app-card { display: flex; flex-direction: column; align-items: center; justify-content: center; background: rgba(15, 42, 86, 0.6); border: 1px solid rgba(56, 189, 248, 0.2); border-radius: 16px; padding: 20px; cursor: pointer; transition: all 0.3s; text-decoration: none; }
        .app-card:hover { transform: translateY(-8px); border-color: #38bdf8; background: rgba(20, 55, 110, 0.8); }
        .app-card svg { width: 70px; height: 70px; margin-bottom: 12px; }
        .app-card span { color: #f0f9ff; font-size: 14px; font-weight: 600; }
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(2, 11, 24, 0.85); backdrop-filter: blur(8px); justify-content: center; align-items: center; z-index: 100; }
        .modal-content { background: #091a34; border: 1px solid #38bdf8; border-radius: 16px; padding: 25px; width: 860px; max-width: 95%; position: relative; }
        .close-btn { position: absolute; top: 15px; right: 20px; color: #ef4444; font-size: 24px; cursor: pointer; }
        canvas { background: white; border-radius: 8px; cursor: crosshair; display: block; margin-top: 15px; touch-action: none; }
    </style>
</head>
<body>
    <header>
        <h2>DigiBoard Master Console</h2>
        <div class="user-info">
            User ID: <b><!--USERNAME--></b>
            <a href="/logout">Logout</a>
        </div>
    </header>

    <div class="main-container">
        <div class="app-grid">
            <div class="app-card" onclick="openModal('whiteboard-modal')">
                <svg viewBox="0 0 100 100">
                    <rect width="100" height="100" rx="20" fill="url(#blue-grad)"/>
                    <path d="M20 65 Q 40 30, 60 65 T 90 40" stroke="white" stroke-width="8" fill="none" stroke-linecap="round"/>
                    <polygon points="65,30 85,10 90,15 70,35" fill="#333"/>
                    <defs>
                        <linearGradient id="blue-grad" x1="0%" y1="0%" x2="100%" y2="100%">
                            <stop offset="0%" style="stop-color:#0052D4;" />
                            <stop offset="100%" style="stop-color:#4364F7;" />
                        </linearGradient>
                    </defs>
                </svg>
                <span>Whiteboard</span>
            </div>

            <div class="app-card" onclick="launchWPS()">
                <svg viewBox="0 0 100 100">
                    <rect width="100" height="100" rx="20" fill="#ff334b"/>
                    <path d="M20 30 L35 70 L50 45 L65 70 L80 30" stroke="white" stroke-width="12" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                <span>WPS Office</span>
            </div>

            <div class="app-card" onclick="openModal('upload-modal')">
                <svg viewBox="0 0 100 100">
                    <path d="M10 25 C10 20, 20 20, 35 20 L45 30 L90 30 L95 40 L95 80 L15 85 Z" fill="#eab308"/>
                    <rect x="25" y="50" width="50" height="30" rx="5" fill="#0284c7"/>
                </svg>
                <span>File Manager</span>
            </div>
        </div>
    </div>

    <div id="whiteboard-modal" class="modal">
        <div class="modal-content">
            <span class="close-btn" onclick="closeModal('whiteboard-modal')">&times;</span>
            <h3 style="color:#38bdf8;">Interactive Whiteboard</h3>
            <button onclick="clearBoard()" style="margin-top:10px; padding:6px 12px; background:#ef4444; color:white; border:none; border-radius:4px; cursor:pointer;">Clear Board</button>
            <canvas id="board" width="800" height="400"></canvas>
        </div>
    </div>

    <div id="upload-modal" class="modal">
        <div class="modal-content" style="width: 450px;">
            <span class="close-btn" onclick="closeModal('upload-modal')">&times;</span>
            <h3 style="color:#38bdf8; margin-bottom:15px;">Upload Class Resource</h3>
            <form action="/upload" method="post" enctype="multipart/form-data">
                <input type="file" name="file" required style="margin-bottom:20px; color:#e0f2fe;">
                <button type="submit" style="padding:10px 20px; background:#0284c7; color:white; border:none; border-radius:6px; cursor:pointer;">Upload File</button>
            </form>
        </div>
    </div>

    <script>
        function openModal(id) { document.getElementById(id).style.display = 'flex'; }
        function closeModal(id) { document.getElementById(id).style.display = 'none'; }
        function launchWPS() {
            fetch('/launch-wps', { method: 'POST' })
                .then(r => r.json()).then(d => alert(d.message));
        }

        const canvas = document.getElementById('board');
        const ctx = canvas.getContext('2d');
        let drawing = false, lines = [], currentLine = [];

        canvas.onpointerdown = (e) => { 
            drawing = true; 
            const rect = canvas.getBoundingClientRect();
            currentLine = [{x: e.clientX - rect.left, y: e.clientY - rect.top}]; 
        };

        canvas.onpointermove = (e) => {
            if (!drawing) return;
            const rect = canvas.getBoundingClientRect();
            currentLine.push({x: e.clientX - rect.left, y: e.clientY - rect.top});
            redraw();
        };

        canvas.onpointerup = () => { 
            if (drawing) { 
                lines.push(currentLine); 
                drawing = false; 
                saveBoard(); 
            } 
        };

        function redraw() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.strokeStyle = "red"; ctx.lineWidth = 3;
            lines.concat([currentLine]).forEach(line => {
                ctx.beginPath();
                line.forEach((pt, i) => { if (i === 0) ctx.moveTo(pt.x, pt.y); else ctx.lineTo(pt.x, pt.y); });
                ctx.stroke();
            });
        }
        function clearBoard() { lines = []; currentLine = []; redraw(); saveBoard(); }
        function saveBoard() {
            fetch('/api/whiteboard', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(lines)
            });
        }
    </script>
</body>
</html>"""

STUDENT_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>DigiBoard Student View</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, sans-serif; }
        body { background: radial-gradient(circle at 50% 50%, #0c2340 0%, #020b18 100%); color: #e0f2fe; min-height: 100vh; display: flex; flex-direction: column; }
        header { background: rgba(4, 19, 41, 0.85); backdrop-filter: blur(10px); padding: 15px 30px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(0, 195, 255, 0.3); }
        .user-info a { color: #38bdf8; text-decoration: none; margin-left: 15px; padding: 5px 12px; border: 1px solid #38bdf8; border-radius: 4px; }
        .main-container { display: flex; flex-direction: column; align-items: center; flex-grow: 1; padding: 20px; }
        canvas { background: white; border-radius: 8px; margin-top: 20px; max-width: 100%; height: auto; }
    </style>
</head>
<body>
    <header>
        <h2>DigiBoard Student Console</h2>
        <div class="user-info">
            User ID: <b><!--USERNAME--></b>
            <a href="/logout">Logout</a>
        </div>
    </header>
    <div class="main-container">
        <h3 style="color:#38bdf8;">Live Whiteboard Stream</h3>
        <canvas id="board" width="800" height="400"></canvas>
    </div>
    <script>
        const canvas = document.getElementById('board');
        const ctx = canvas.getContext('2d');
        let lastRaw = "";

        function fetchBoard() {
            fetch('/api/whiteboard')
                .then(r => r.text())
                .then(rawText => {
                    if (rawText === lastRaw) return;
                    lastRaw = rawText;
                    const lines = JSON.parse(rawText);
                    ctx.clearRect(0, 0, canvas.width, canvas.height);
                    ctx.strokeStyle = "red"; ctx.lineWidth = 3;
                    lines.forEach(line => {
                        ctx.beginPath();
                        line.forEach((pt, i) => { if (i === 0) ctx.moveTo(pt.x, pt.y); else ctx.lineTo(pt.x, pt.y); });
                        ctx.stroke();
                    });
                }).catch(() => {});
        }
        setInterval(fetchBoard, 150);
        fetchBoard();
    </script>
</body>
</html>"""

class DigiBoardHandler(http.server.BaseHTTPRequestHandler):
    def get_session(self):
        cookie_header = self.headers.get('Cookie')
        if cookie_header:
            C = cookies.SimpleCookie(cookie_header)
            if 'session_id' in C:
                return SESSIONS.get(C['session_id'].value)
        return None

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        session = self.get_session()

        if parsed.path == "/":
            if session:
                self.redirect("/teacher" if session['role'] == 'teacher' else "/student")
            else:
                self.send_html(LOGIN_HTML.replace("<!--ERROR-->", ""))
        elif parsed.path == "/logout":
            cookie_header = self.headers.get('Cookie')
            if cookie_header:
                C = cookies.SimpleCookie(cookie_header)
                if 'session_id' in C and C['session_id'].value in SESSIONS:
                    del SESSIONS[C['session_id'].value]
            self.redirect("/")
        elif parsed.path == "/teacher":
            if not session or session['role'] != 'teacher':
                self.redirect("/")
                return
            self.send_html(TEACHER_HTML.replace("<!--USERNAME-->", session['username']))
        elif parsed.path == "/student":
            if not session or session['role'] != 'student':
                self.redirect("/")
                return
            self.send_html(STUDENT_HTML.replace("<!--USERNAME-->", session['username']))
        elif parsed.path == "/api/whiteboard":
            self.send_json(BOARD_CACHE)
        else:
            self.send_error(404)

    def do_POST(self):
        global BOARD_CACHE
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length) if length > 0 else b""

        if self.path == "/login":
            params = urllib.parse.parse_qs(body.decode('utf-8'))
            user = params.get('username', [''])[0]
            pwd = params.get('password', [''])[0]

            if user in USERS and USERS[user]['password'] == pwd:
                sid = str(uuid.uuid4())
                SESSIONS[sid] = {"username": user, "role": USERS[user]['role']}
                self.send_response(303)
                self.send_header('Set-Cookie', f'session_id={sid}; Path=/')
                self.send_header('Location', "/teacher" if USERS[user]['role'] == 'teacher' else "/student")
                self.end_headers()
            else:
                self.send_html(LOGIN_HTML.replace("<!--ERROR-->", "<p class='error'>Invalid User ID or Password</p>"))

        elif self.path == "/upload":
            session = self.get_session()
            if not session or session.get('role') != 'teacher':
                self.redirect("/")
                return
            try:
                content_type = self.headers.get('Content-Type', '')
                if 'boundary=' in content_type:
                    boundary = content_type.split("boundary=")[1].encode()
                    parts = body.split(b'--' + boundary)
                    for part in parts:
                        if b'filename="' in part:
                            header_part, file_data = part.split(b'\r\n\r\n', 1)
                            file_data = file_data.rsplit(b'\r\n', 1)[0]
                            header_str = header_part.decode('utf-8', errors='ignore')
                            for line in header_str.split('\r\n'):
                                if 'filename=' in line:
                                    filename = line.split('filename=')[1].strip('"')
                                    filename = os.path.basename(filename)
                                    if filename:
                                        with open(os.path.join(UPLOAD_DIR, filename), 'wb') as f:
                                            f.write(file_data)
                self.redirect("/teacher")
            except Exception as e:
                print("Upload processing error:", e)
                self.redirect("/teacher")

        elif self.path == "/launch-wps":
            try:
                default_doc = os.path.join(UPLOAD_DIR, "Document.docx")
                if not os.path.exists(default_doc):
                    with open(default_doc, "wb") as f:
                        f.write(b"")

                os.startfile(default_doc)
                self.send_json('{"message":"Opening WPS Office via default document association..."}')
            except Exception as e:
                print("Failed to open default viewer:", e)
                self.send_json(f'{{"message":"Error opening default viewer: {e}"}}')

        elif self.path == "/api/whiteboard":
            BOARD_CACHE = body.decode('utf-8')
            threading.Thread(
                target=supabase_request,
                args=("whiteboard?id=eq.1", "PATCH", {"lines": BOARD_CACHE}),
                daemon=True
            ).start()
            self.send_json('{"status":"ok"}')

    def redirect(self, path):
        self.send_response(303)
        self.send_header('Location', path)
        self.end_headers()

    def send_html(self, html_str):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(html_str.encode('utf-8'))

    def send_json(self, json_str):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        if isinstance(json_str, str):
            self.wfile.write(json_str.encode('utf-8'))
        else:
            self.wfile.write(json.dumps(json_str).encode('utf-8'))

if __name__ == "__main__":
    local_ip = get_local_ip()
    print("==================================================")
    print("DigiBoard Console is running!")
    print(f"Local Access:   http://localhost:{PORT}")
    print(f"Network Access: http://{local_ip}:{PORT}")
    print("==================================================")
    
    with socketserver.TCPServer(("0.0.0.0", PORT), DigiBoardHandler) as httpd:
        httpd.serve_forever()
