import http.server
import socketserver
import json
import urllib.parse
import urllib.request
from http import cookies
import os
import uuid
import threading

PORT = 8000
UPLOAD_DIR = "uploads"
SESSIONS = {}
BOARD_CACHE = "[]"
CACHE_LOCK = threading.Lock()

# Retrieve Gemini API Key from system environment
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyCKzHuwsH4Rv4Uagia8tcRnwt-reHI-8")

USERS = {
    "juraghav@Digiboardleaning.com": {"password": "2234269580", "role": "teacher"},
    "socialstudiesclass@Digiboardleaning.com": {"password": "2234269580", "role": "student"}
}

def call_gemini_api(prompt):
    """Calls the official Google Gemini API using Python built-in urllib."""
    if GEMINI_API_KEY == "YOUR_GEMINI_API_KEY_HERE" or not GEMINI_API_KEY:
        return (
            "Error: Gemini API key missing. Pass your key via terminal variable "
            "or update GEMINI_API_KEY in app.py."
        )

    # Updated endpoint to gemini-2.5-flash
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            
            # Safely extract response text
            candidates = res_data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "No text returned.")
            return "No response content generated."
            
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        return f"Gemini API HTTP Error {e.code}: {error_body}"
    except Exception as e:
        return f"Gemini Error: {str(e)}"

LOGIN_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>DigiBoard - Login</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #070d19; color: #f8fafc; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .login-card { background: #0f172a; border: 1px solid #1e293b; padding: 2.5rem; border-radius: 12px; width: 340px; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.6); }
        h2 { text-align: center; margin-top: 0; color: #38bdf8; font-size: 1.5rem; }
        label { font-size: 0.85rem; color: #94a3b8; display: block; margin-top: 1rem; }
        input { width: 100%; padding: 0.65rem; margin-top: 0.3rem; border: 1px solid #334155; background: #070d19; color: #fff; border-radius: 6px; box-sizing: border-box; }
        input:focus { outline: none; border-color: #38bdf8; }
        button { width: 100%; padding: 0.75rem; margin-top: 1.5rem; background: #0284c7; border: none; color: white; border-radius: 6px; font-weight: bold; cursor: pointer; transition: background 0.2s; }
        button:hover { background: #0369a1; }
        .error { color: #ef4444; font-size: 0.875rem; text-align: center; margin-bottom: 1rem; background: rgba(239, 68, 68, 0.1); padding: 0.5rem; border-radius: 4px; }
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
        .logout-btn { background: transparent; border: 1px solid #1e293b; color: #38bdf8; padding: 0.4rem 1rem; border-radius: 4px; cursor: pointer; font-size: 0.85rem; }
        .logout-btn:hover { background: #1e293b; color: #fff; }

        .console-container { flex: 1; display: flex; justify-content: center; align-items: center; padding: 2rem; }
        
        .grid-wrapper {
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid #172554;
            border-radius: 16px;
            padding: 2.5rem;
            display: flex;
            gap: 1.5rem;
            box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5);
        }

        .app-card {
            width: 140px;
            height: 140px;
            background: #091326;
            border: 1px solid #1e293b;
            border-radius: 12px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            cursor: pointer;
            transition: all 0.2s ease;
            gap: 0.75rem;
        }

        .app-card:hover {
            transform: translateY(-4px);
            border-color: #38bdf8;
            background: #0e1d38;
            box-shadow: 0 10px 20px -5px rgba(56, 189, 248, 0.2);
        }

        .app-icon {
            width: 52px;
            height: 52px;
            border-radius: 12px;
            display: flex;
            justify-content: center;
            align-items: center;
        }

        .icon-wb { background: #2563eb; }
        .icon-doc { background: #ef4444; }
        .icon-fm { background: #eab308; }
        .icon-ai { background: #c026d3; }

        .app-icon svg { width: 28px; height: 28px; fill: white; }
        .app-title { font-size: 0.8rem; font-weight: 600; color: #cbd5e1; text-align: center; }

        /* Modal Styles */
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(3, 7, 18, 0.9); justify-content: center; align-items: center; z-index: 100; }
        .modal-content { background: #0f172a; border: 1px solid #1e293b; border-radius: 12px; width: 90%; max-width: 1000px; max-height: 90vh; display: flex; flex-direction: column; overflow: hidden; }
        .modal-header { display: flex; justify-content: space-between; align-items: center; padding: 1rem 1.5rem; border-bottom: 1px solid #1e293b; }
        .modal-header h3 { margin: 0; color: #38bdf8; }
        .close-btn { color: #94a3b8; font-size: 1.5rem; font-weight: bold; cursor: pointer; }
        .close-btn:hover { color: #fff; }
        .modal-body { padding: 1.5rem; overflow-y: auto; flex: 1; }

        /* App Specific Styles */
        canvas { background: #ffffff; border-radius: 6px; cursor: crosshair; display: block; width: 100%; height: 500px; }
        .chat-box { background: #070d19; border: 1px solid #1e293b; border-radius: 6px; padding: 1rem; height: 380px; overflow-y: auto; margin-bottom: 1rem; display: flex; flex-direction: column; gap: 0.75rem; }
        .chat-msg { font-size: 0.9rem; line-height: 1.5; padding: 0.75rem 1rem; border-radius: 8px; max-width: 85%; whitespace: pre-wrap; }
        .user-msg { color: #38bdf8; background: #0f172a; align-self: flex-end; border: 1px solid #1e293b; }
        .ai-msg { color: #f8fafc; background: #111c30; align-self: flex-start; border: 1px solid #1e293b; }
        .input-group { display: flex; gap: 0.5rem; }
        .input-group input { flex: 1; padding: 0.65rem; background: #070d19; border: 1px solid #1e293b; color: white; border-radius: 6px; }
        .input-group button { padding: 0.65rem 1.25rem; background: #0284c7; border: none; color: white; border-radius: 6px; cursor: pointer; }
        .file-item { display: flex; justify-content: space-between; align-items: center; padding: 0.75rem 1rem; background: #070d19; border: 1px solid #1e293b; border-radius: 6px; margin-bottom: 0.5rem; }
        .file-item a { color: #38bdf8; text-decoration: none; }
        .delete-btn { color: #ef4444; background: none; border: none; cursor: pointer; }
    </style>
</head>
<body>
    <header>
        <div class="header-title">DigiBoard Master Console</div>
        <div class="user-section">
            User ID: <span class="user-id"><!--USERNAME--></span>
            <button class="logout-btn" onclick="window.location.href='/logout'">Logout</button>
        </div>
    </header>

    <div class="console-container">
        <div class="grid-wrapper">
            <!-- Whiteboard Tile -->
            <div class="app-card" onclick="openApp('whiteboard-modal')">
                <div class="app-icon icon-wb">
                    <svg viewBox="0 0 24 24"><path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg>
                </div>
                <div class="app-title">WhiteBoard</div>
            </div>

            <!-- Document Viewer Tile -->
            <div class="app-card" onclick="launchWPS()">
                <div class="app-icon icon-doc">
                    <svg viewBox="0 0 24 24"><path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z"/></svg>
                </div>
                <div class="app-title">Document Viewer</div>
            </div>

            <!-- File Manager Tile -->
            <div class="app-card" onclick="openFileManager()">
                <div class="app-icon icon-fm">
                    <svg viewBox="0 0 24 24"><path d="M10 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z"/></svg>
                </div>
                <div class="app-title">File Manager</div>
            </div>

            <!-- AI Assistant Tile -->
            <div class="app-card" onclick="openApp('ai-modal')">
                <div class="app-icon icon-ai">
                    <svg viewBox="0 0 24 24"><path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm1 14.93V17a1 1 0 0 1-2 0v-.07A7 7 0 0 1 5.07 13H5a1 1 0 0 1 0-2h.07A7 7 0 0 1 11 5.07V5a1 1 0 0 1 2 0v.07A7 7 0 0 1 18.93 11H19a1 1 0 0 1 0 2h-.07A7 7 0 0 1 13 16.93z"/></svg>
                </div>
                <div class="app-title">AI Assistant</div>
            </div>
        </div>
    </div>

    <!-- Whiteboard Modal -->
    <div class="modal" id="whiteboard-modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3>DigiBoard Interactive Whiteboard</h3>
                <span class="close-btn" onclick="closeApp('whiteboard-modal')">&times;</span>
            </div>
            <div class="modal-body">
                <canvas id="board" width="950" height="480"></canvas>
                <!--ROLE_TEACHER_ONLY-->
                <div style="margin-top:0.75rem; text-align:right;">
                    <button onclick="clearBoard()" style="background:#ef4444; color:white; border:none; padding:0.5rem 1rem; border-radius:4px; cursor:pointer;">Clear Board</button>
                </div>
                <!--END_ROLE-->
            </div>
        </div>
    </div>

    <!-- File Manager Modal -->
    <div class="modal" id="filemanager-modal">
        <div class="modal-content" style="max-width: 600px;">
            <div class="modal-header">
                <h3>Class File Manager</h3>
                <span class="close-btn" onclick="closeApp('filemanager-modal')">&times;</span>
            </div>
            <div class="modal-body">
                <!--ROLE_TEACHER_ONLY-->
                <form action="/upload" method="POST" enctype="multipart/form-data" style="margin-bottom: 1.5rem; background: #070d19; padding: 1rem; border-radius: 6px;">
                    <label style="display:block; margin-bottom: 0.5rem; color:#94a3b8;">Upload New Document:</label>
                    <input type="file" name="file" required style="margin-bottom:0.75rem; color:white;">
                    <button type="submit" style="width:100%; padding:0.5rem; background:#10b981; border:none; color:white; border-radius:4px; cursor:pointer;">Upload File</button>
                </form>
                <!--END_ROLE-->
                <ul id="file-list-container" style="list-style:none; padding:0; margin:0;"></ul>
            </div>
        </div>
    </div>

    <!-- AI Assistant Modal -->
    <div class="modal" id="ai-modal">
        <div class="modal-content" style="max-width: 800px;">
            <div class="modal-header">
                <h3>Gemini AI Assistant</h3>
                <span class="close-btn" onclick="closeApp('ai-modal')">&times;</span>
            </div>
            <div class="modal-body">
                <div class="chat-box" id="chat-box"></div>
                <div class="input-group">
                    <input type="text" id="chat-input" placeholder="Ask Gemini anything..." onkeypress="if(event.key==='Enter') sendChatMessage()">
                    <button onclick="sendChatMessage()">Send</button>
                </div>
            </div>
        </div>
    </div>

    <script>
        const USER_ROLE = "<!--USER_ROLE-->";

        function openApp(id) { document.getElementById(id).style.display = 'flex'; }
        function closeApp(id) { document.getElementById(id).style.display = 'none'; }

        function launchWPS() {
            window.location.href = '/launch-wps';
        }

        function openFileManager() {
            openApp('filemanager-modal');
            loadFileList();
        }

        function loadFileList() {
            fetch('/api/files')
                .then(r => r.json())
                .then(files => {
                    const container = document.getElementById('file-list-container');
                    if (!files || files.length === 0) {
                        container.innerHTML = '<li style="color:#94a3b8; text-align:center;">No files available.</li>';
                        return;
                    }
                    container.innerHTML = files.map(file => `
                        <li class="file-item">
                            <a href="/uploads/${encodeURIComponent(file)}" target="_blank">${file}</a>
                            ${USER_ROLE === 'teacher' ? `<button class="delete-btn" onclick="deleteFile('${file}')">Delete</button>` : ''}
                        </li>
                    `).join('');
                });
        }

        function deleteFile(filename) {
            if (!confirm('Delete file: ' + filename + '?')) return;
            fetch('/api/delete-file?name=' + encodeURIComponent(filename), { method: 'DELETE' })
                .then(r => r.json())
                .then(() => loadFileList());
        }

        function sendChatMessage() {
            const input = document.getElementById('chat-input');
            const promptText = input.value.trim();
            if (!promptText) return;

            const box = document.getElementById('chat-box');
            
            // Add user message to UI
            const uDiv = document.createElement('div');
            uDiv.className = 'chat-msg user-msg';
            uDiv.textContent = promptText;
            box.appendChild(uDiv);
            input.value = '';

            // Add placeholder AI message
            const aiDiv = document.createElement('div');
            aiDiv.className = 'chat-msg ai-msg';
            aiDiv.textContent = 'Gemini is thinking...';
            box.appendChild(aiDiv);
            box.scrollTop = box.scrollHeight;

            // Call backend Gemini proxy
            fetch('/api/chat-gemini', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ prompt: promptText })
            })
            .then(r => r.json())
            .then(data => {
                aiDiv.textContent = data.response;
                box.scrollTop = box.scrollHeight;
            })
            .catch(err => {
                aiDiv.textContent = "Error receiving response from Gemini.";
                box.scrollTop = box.scrollHeight;
            });
        }

        // Whiteboard Logic
        const canvas = document.getElementById('board');
        const ctx = canvas.getContext('2d');
        let isDrawing = false;
        let currentLine = null;
        let lines = [];

        if (USER_ROLE === 'teacher') {
            canvas.addEventListener('mousedown', (e) => {
                isDrawing = true;
                const rect = canvas.getBoundingClientRect();
                currentLine = { color: 'red', width: 3, pts: [{ x: e.clientX - rect.left, y: e.clientY - rect.top }] };
                lines.push(currentLine);
            });

            canvas.addEventListener('mousemove', (e) => {
                if (!isDrawing) return;
                const rect = canvas.getBoundingClientRect();
                currentLine.pts.push({ x: e.clientX - rect.left, y: e.clientY - rect.top });
                redraw(lines);
                syncWhiteboard();
            });

            canvas.addEventListener('mouseup', () => { isDrawing = false; });
        }

        function redraw(linesToDraw) {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            if (!linesToDraw) return;
            linesToDraw.forEach(line => {
                if (!line || !line.pts) return;
                ctx.strokeStyle = line.color || "red";
                ctx.lineWidth = line.width || 3;
                ctx.beginPath();
                line.pts.forEach((pt, i) => {
                    if (i === 0) ctx.moveTo(pt.x, pt.y);
                    else ctx.lineTo(pt.x, pt.y);
                });
                ctx.stroke();
            });
        }

        function clearBoard() {
            lines = [];
            redraw(lines);
            syncWhiteboard();
        }

        function syncWhiteboard() {
            fetch('/api/whiteboard', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(lines)
            });
        }

        function pollWhiteboard() {
            if (USER_ROLE === 'student') {
                fetch('/api/whiteboard')
                    .then(r => r.json())
                    .then(data => redraw(data))
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

def save_to_file_manager(filename, content):
    if not os.path.exists(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR)
    filepath = os.path.join(UPLOAD_DIR, os.path.basename(filename))
    if isinstance(content, str):
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
    else:
        with open(filepath, "wb") as f:
            f.write(content)
    return filename

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
        self.end_headers()
        self.wfile.write(content.encode('utf-8'))

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def redirect(self, location):
        self.send_response(302)
        self.send_header("Location", location)
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
            
            if session['role'] != 'teacher':
                import re
                html = re.sub(r'<!--ROLE_TEACHER_ONLY-->.*?<!--END_ROLE-->', '', html, flags=re.DOTALL)
            else:
                html = html.replace("<!--ROLE_TEACHER_ONLY-->", "").replace("<!--END_ROLE-->", "")
                
            self.send_html(html)
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
        content_length = int(self.headers.get('Content-Length', 0))

        if path == "/login":
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
                self.end_headers()
            else:
                err_html = LOGIN_HTML.replace("<!--ERROR-->", '<div class="error">Invalid username or password</div>')
                self.send_html(err_html, 401)
            return

        session = self.get_session()
        if not session:
            self.send_json({"error": "Unauthorized"}, 401)
            return

        if path == "/upload":
            if session['role'] != 'teacher':
                self.send_json({"error": "Forbidden"}, 403)
                return
            
            boundary = self.headers.get('Content-Type').split("boundary=")[1].encode()
            body = self.rfile.read(content_length)
            parts = body.split(b"--" + boundary)
            
            for part in parts:
                if b'name="file";' in part:
                    headers_part, file_data = part.split(b"\r\n\r\n", 1)
                    file_data = file_data.rsplit(b"\r\n", 1)[0]
                    
                    filename = "uploaded_file"
                    for line in headers_part.decode(errors='ignore').split("\r\n"):
                        if "filename=" in line:
                            filename = line.split('filename=')[1].strip('"')
                    
                    save_to_file_manager(filename, file_data)
            
            self.redirect("/")
            return

        if path == "/api/chat-gemini":
            body = self.rfile.read(content_length).decode('utf-8')
            try:
                data = json.loads(body)
                prompt = data.get("prompt", "")
                response_text = call_gemini_api(prompt)
                self.send_json({"response": response_text})
            except Exception as e:
                self.send_json({"response": f"Error: {str(e)}"}, 400)
            return

        if path == "/api/whiteboard":
            if session['role'] != 'teacher':
                self.send_json({"error": "Forbidden"}, 403)
                return
            
            body = self.rfile.read(content_length).decode('utf-8')
            global BOARD_CACHE
            with CACHE_LOCK:
                BOARD_CACHE = body

            self.send_json({"status": "success"})
            return

        self.send_error(404)

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        session = self.get_session()
        if not session or session['role'] != 'teacher':
            self.send_json({"error": "Forbidden"}, 403)
            return

        if path == "/api/delete-file":
            qs = urllib.parse.parse_qs(parsed.query)
            filename = qs.get('name', [''])[0]
            if filename:
                filepath = os.path.join(UPLOAD_DIR, os.path.basename(filename))
                if os.path.exists(filepath):
                    os.remove(filepath)
                    self.send_json({"status": "success"})
                    return
            self.send_json({"error": "File not found"}, 404)
            return

        self.send_error(404)

def run_server():
    port = int(os.environ.get("PORT", PORT))
    server_address = ('', port)
    httpd = socketserver.ThreadingTCPServer(server_address, DigiBoardHandler)
    print(f"[DigiBoard Master Console Running on port {port}]")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
        httpd.server_close()

if __name__ == "__main__":
    run_server()
