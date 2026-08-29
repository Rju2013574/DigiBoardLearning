import http.server
import socketserver
import json
import urllib.parse
from http import cookies
import os
import uuid
import threading

PORT = 8000
UPLOAD_DIR = "uploads"
SESSIONS = {}
BOARD_CACHE = "[]"
CACHE_LOCK = threading.Lock()

USERS = {
    "teacher": {"password": "teacherpassword", "role": "teacher"},
    "student": {"password": "studentpassword", "role": "student"}
}

LOGIN_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>DigiBoard - Login</title>
    <style>
        body { font-family: sans-serif; background: #0f172a; color: #f8fafc; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .login-card { background: #1e293b; padding: 2rem; border-radius: 8px; width: 320px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.5); }
        h2 { text-align: center; margin-top: 0; color: #38bdf8; }
        input { width: 100%; padding: 0.5rem; margin: 0.5rem 0 1rem 0; border: 1px solid #475569; background: #0f172a; color: #fff; border-radius: 4px; box-sizing: border-box; }
        button { width: 100%; padding: 0.6rem; background: #0284c7; border: none; color: white; border-radius: 4px; font-weight: bold; cursor: pointer; }
        button:hover { background: #0369a1; }
        .error { color: #ef4444; font-size: 0.875rem; text-align: center; margin-bottom: 1rem; }
    </style>
</head>
<body>
    <div class="login-card">
        <h2>DigiBoard Login</h2>
        <!--ERROR-->
        <form action="/login" method="POST">
            <label>Username</label>
            <input type="text" name="username" required>
            <label>Password</label>
            <input type="password" name="password" required>
            <button type="submit">Sign In</button>
        </form>
    </div>
</body>
</html>"""

TEACHER_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>DigiBoard - Teacher Dashboard</title>
    <style>
        body { font-family: sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 1rem; }
        header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #334155; padding-bottom: 1rem; }
        .nav-btns button { margin-left: 0.5rem; padding: 0.5rem 1rem; background: #334155; border: none; color: white; border-radius: 4px; cursor: pointer; }
        .nav-btns button:hover { background: #475569; }
        .main-content { display: flex; gap: 1rem; margin-top: 1rem; }
        .board-container { flex: 2; background: #1e293b; padding: 1rem; border-radius: 8px; }
        canvas { background: #fff; border-radius: 4px; cursor: crosshair; display: block; width: 100%; height: 500px; }
        .sidebar { flex: 1; background: #1e293b; padding: 1rem; border-radius: 8px; display: flex; flex-direction: column; gap: 1rem; }
        .chat-box { flex: 1; background: #0f172a; border-radius: 4px; padding: 0.5rem; height: 250px; overflow-y: auto; }
        .chat-msg { margin-bottom: 0.5rem; font-size: 0.875rem; }
        .user-msg { color: #38bdf8; }
        .ai-msg { color: #4ade80; }
        .input-group { display: flex; gap: 0.5rem; }
        .input-group input { flex: 1; padding: 0.5rem; background: #0f172a; border: 1px solid #334155; color: white; border-radius: 4px; }
        .input-group button { padding: 0.5rem 1rem; background: #0284c7; border: none; color: white; border-radius: 4px; cursor: pointer; }
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); justify-content: center; align-items: center; }
        .modal-content { background: #1e293b; padding: 1.5rem; border-radius: 8px; width: 400px; max-height: 80vh; overflow-y: auto; }
        .close-btn { float: right; cursor: pointer; color: #94a3b8; font-weight: bold; }
        .file-item { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; padding: 0.5rem; background: #0f172a; border-radius: 4px; }
        .file-item a { color: #38bdf8; text-decoration: none; }
        .delete-btn { color: #ef4444; cursor: pointer; background: none; border: none; }
    </style>
</head>
<body>
    <header>
        <h2>DigiBoard Teacher Panel (Welcome, <!--USERNAME-->)</h2>
        <div class="nav-btns">
            <button onclick="openFileManager()">Files Manager</button>
            <button onclick="launchWPS()">Launch Document Viewer</button>
            <button onclick="window.location.href='/logout'">Logout</button>
        </div>
    </header>
    <div class="main-content">
        <div class="board-container">
            <canvas id="board" width="800" height="500"></canvas>
            <div style="margin-top:0.5rem; display:flex; gap:0.5rem;">
                <button onclick="clearBoard()" style="background:#ef4444; color:white; border:none; padding:0.5rem 1rem; border-radius:4px; cursor:pointer;">Clear Board</button>
            </div>
        </div>
        <div class="sidebar">
            <h3>AI Assistant & Resources</h3>
            <div class="chat-box" id="chat-box"></div>
            <div class="input-group">
                <input type="text" id="chat-input" placeholder="Prompt AI to generate resource...">
                <button onclick="sendChatMessage()">Send</button>
            </div>
            <hr style="border-color:#334155; width:100%;">
            <h3>Upload Resource File</h3>
            <form action="/upload" method="POST" enctype="multipart/form-data">
                <input type="file" name="file" required style="margin-bottom:0.5rem; color:white;">
                <button type="submit" style="width:100%; padding:0.5rem; background:#10b981; border:none; color:white; border-radius:4px; cursor:pointer;">Upload to Class</button>
            </form>
        </div>
    </div>

    <div class="modal" id="filemanager-modal">
        <div class="modal-content">
            <span class="close-btn" onclick="closeModal('filemanager-modal')">&times;</span>
            <h3 style="margin-top:0;">Managed Class Files</h3>
            <ul id="file-list-container" style="list-style:none; padding:0;"></ul>
        </div>
    </div>

    <script>
        function openModal(id) { document.getElementById(id).style.display = 'flex'; }
        function closeModal(id) { document.getElementById(id).style.display = 'none'; }

        function launchWPS() {
            window.location.href = '/launch-wps';
        }

        function openFileManager() {
            openModal('filemanager-modal');
            loadFileList();
        }

        function loadFileList() {
            fetch('/api/files')
                .then(r => r.json())
                .then(files => {
                    const container = document.getElementById('file-list-container');
                    if (files.length === 0) {
                        container.innerHTML = '<li style="color:#94a3b8;">No uploaded files found.</li>';
                        return;
                    }
                    container.innerHTML = files.map(file => `
                        <li class="file-item">
                            <a href="/uploads/${encodeURIComponent(file)}" target="_blank">${file}</a>
                            <button class="delete-btn" onclick="deleteFile('${file}')">Delete</button>
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
            const uDiv = document.createElement('div');
            uDiv.className = 'chat-msg user-msg';
            uDiv.textContent = promptText;
            box.appendChild(uDiv);
            input.value = '';

            const aiDiv = document.createElement('div');
            aiDiv.className = 'chat-msg ai-msg';
            aiDiv.textContent = 'Generating resource...';
            box.appendChild(aiDiv);
            box.scrollTop = box.scrollHeight;

            const docName = "Resource_" + Date.now() + ".txt";

            fetch('/api/generate-resource', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    filename: docName,
                    content: "DigiBoard Generated Resource\\nPrompt: " + promptText + "\\n\\nContent created successfully."
                })
            })
            .then(r => r.json())
            .then(data => {
                if (data.status === 'success') {
                    aiDiv.textContent = `Generated resource saved as "${data.file}".`;
                } else {
                    aiDiv.textContent = "Error: " + data.message;
                }
                box.scrollTop = box.scrollHeight;
            });
        }

        // Whiteboard Logic
        const canvas = document.getElementById('board');
        const ctx = canvas.getContext('2d');
        let isDrawing = false;
        let currentLine = null;
        let lines = [];

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
            redraw();
            syncWhiteboard();
        });

        canvas.addEventListener('mouseup', () => { isDrawing = false; });

        function redraw() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            lines.forEach(line => {
                ctx.strokeStyle = line.color;
                ctx.lineWidth = line.width;
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
            redraw();
            syncWhiteboard();
        }

        function syncWhiteboard() {
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
    <title>DigiBoard - Student Viewer</title>
    <style>
        body { font-family: sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 1rem; }
        header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #334155; padding-bottom: 1rem; }
        .nav-btns button { margin-left: 0.5rem; padding: 0.5rem 1rem; background: #334155; border: none; color: white; border-radius: 4px; cursor: pointer; }
        .main-content { display: flex; gap: 1rem; margin-top: 1rem; }
        .board-container { flex: 2; background: #1e293b; padding: 1rem; border-radius: 8px; }
        canvas { background: #fff; border-radius: 4px; display: block; width: 100%; height: 500px; }
        .sidebar { flex: 1; background: #1e293b; padding: 1rem; border-radius: 8px; display: flex; flex-direction: column; gap: 1rem; }
        .chat-box { flex: 1; background: #0f172a; border-radius: 4px; padding: 0.5rem; height: 350px; overflow-y: auto; }
        .chat-msg { margin-bottom: 0.5rem; font-size: 0.875rem; }
        .user-msg { color: #38bdf8; }
        .ai-msg { color: #4ade80; }
        .input-group { display: flex; gap: 0.5rem; }
        .input-group input { flex: 1; padding: 0.5rem; background: #0f172a; border: 1px solid #334155; color: white; border-radius: 4px; }
        .input-group button { padding: 0.5rem 1rem; background: #0284c7; border: none; color: white; border-radius: 4px; cursor: pointer; }
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); justify-content: center; align-items: center; }
        .modal-content { background: #1e293b; padding: 1.5rem; border-radius: 8px; width: 400px; max-height: 80vh; overflow-y: auto; }
        .close-btn { float: right; cursor: pointer; color: #94a3b8; font-weight: bold; }
        .file-item { margin-bottom: 0.5rem; padding: 0.5rem; background: #0f172a; border-radius: 4px; }
        .file-item a { color: #38bdf8; text-decoration: none; }
    </style>
</head>
<body>
    <header>
        <h2>DigiBoard Live Stream (Welcome, <!--USERNAME-->)</h2>
        <div class="nav-btns">
            <button onclick="openFileManager()">Class Files</button>
            <button onclick="launchWPS()">Open Viewer</button>
            <button onclick="window.location.href='/logout'">Logout</button>
        </div>
    </header>
    <div class="main-content">
        <div class="board-container">
            <canvas id="board" width="800" height="500"></canvas>
        </div>
        <div class="sidebar">
            <h3>AI Study Assistant</h3>
            <div class="chat-box" id="chat-box"></div>
            <div class="input-group">
                <input type="text" id="chat-input" placeholder="Ask AI for study notes...">
                <button onclick="sendChatMessage()">Send</button>
            </div>
        </div>
    </div>

    <div class="modal" id="filemanager-modal">
        <div class="modal-content">
            <span class="close-btn" onclick="closeModal('filemanager-modal')">&times;</span>
            <h3 style="margin-top:0;">Class Files</h3>
            <ul id="file-list-container" style="list-style:none; padding:0;"></ul>
        </div>
    </div>

    <script>
        function openModal(id) { document.getElementById(id).style.display = 'flex'; }
        function closeModal(id) { document.getElementById(id).style.display = 'none'; }

        function launchWPS() {
            window.location.href = '/launch-wps';
        }

        function openFileManager() {
            openModal('filemanager-modal');
            loadFileList();
        }

        function loadFileList() {
            fetch('/api/files')
                .then(r => r.json())
                .then(files => {
                    const container = document.getElementById('file-list-container');
                    if (files.length === 0) {
                        container.innerHTML = '<li style="color:#94a3b8;">No uploaded files found.</li>';
                        return;
                    }
                    container.innerHTML = files.map(file => `
                        <li class="file-item">
                            <a href="/uploads/${encodeURIComponent(file)}" target="_blank">${file}</a>
                        </li>
                    `).join('');
                })
                .catch(() => {
                    document.getElementById('file-list-container').innerHTML = '<li style="color:#ef4444;">Error loading files.</li>';
                });
        }

        function sendChatMessage() {
            const input = document.getElementById('chat-input');
            const promptText = input.value.trim();
            if (!promptText) return;

            const box = document.getElementById('chat-box');
            
            const uDiv = document.createElement('div');
            uDiv.className = 'chat-msg user-msg';
            uDiv.textContent = promptText;
            box.appendChild(uDiv);
            input.value = '';

            const aiDiv = document.createElement('div');
            aiDiv.className = 'chat-msg ai-msg';
            aiDiv.textContent = 'Generating response...';
            box.appendChild(aiDiv);
            box.scrollTop = box.scrollHeight;

            const docName = "Student_Notes_" + Date.now() + ".txt";

            fetch('/api/generate-resource', {
                method: 'POST',
                headers: {'Content-Type': 'application/json; charset=utf-8'},
                body: JSON.stringify({
                    filename: docName,
                    content: "DigiBoard AI Study Guide\\nPrompt: " + promptText + "\\n\\n[Content generated automatically]"
                })
            })
            .then(r => r.json())
            .then(data => {
                if (data.status === 'success') {
                    aiDiv.textContent = `Study guide generated successfully! Saved to Class Files as "${data.file}".`;
                } else {
                    aiDiv.textContent = "Error: " + data.message;
                }
                box.scrollTop = box.scrollHeight;
            })
            .catch(() => {
                aiDiv.textContent = "Error connecting to AI backend.";
                box.scrollTop = box.scrollHeight;
            });
        }

        const canvas = document.getElementById('board');
        const ctx = canvas.getContext('2d');

        function redraw(lines) {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            lines.forEach(line => {
                if (!line || !line.pts || line.pts.length === 0) return;
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

        function pollWhiteboard() {
            fetch('/api/whiteboard')
                .then(r => r.json())
                .then(lines => {
                    redraw(lines);
                })
                .catch(() => {})
                .finally(() => {
                    setTimeout(pollWhiteboard, 1000);
                });
        }

        pollWhiteboard();
    </script>
</body>
</html>"""


def get_local_ip():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


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


# --- REQUEST HANDLER ---
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

        if path == "/" or path == "/dashboard":
            if not session:
                self.redirect("/login")
                return
            if session['role'] == 'teacher':
                html = TEACHER_HTML.replace("<!--USERNAME-->", session['username'])
            else:
                html = STUDENT_HTML.replace("<!--USERNAME-->", session['username'])
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

        if path == "/api/generate-resource":
            body = self.rfile.read(content_length).decode('utf-8')
            try:
                data = json.loads(body)
                filename = data.get("filename", "resource.txt")
                content = data.get("content", "")
                saved_name = save_to_file_manager(filename, content)
                self.send_json({"status": "success", "file": saved_name})
            except Exception as e:
                self.send_json({"status": "error", "message": str(e)}, 400)
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
    server_address = ('', PORT)
    httpd = socketserver.ThreadingTCPServer(server_address, DigiBoardHandler)
    local_ip = get_local_ip()
    print(f"[DigiBoard Server Running]")
    print(f" Local Access:   http://localhost:{PORT}")
    print(f" Network Access: http://{local_ip}:{PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
        httpd.server_close()

if __name__ == "__main__":
    run_server()
