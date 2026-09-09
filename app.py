import http.server
import socketserver
import json
import urllib.parse
from http import cookies
import os
import uuid
import threading
import re

PORT = 8000
DATA_FILE = "db.json"
UPLOAD_DIR = "uploads"
SESSIONS = {}
BOARD_CACHE = "{}"
CACHE_LOCK = threading.Lock()

# Initial database structure
DEFAULT_DB = {
    "users": {
        "admin@digiboard.com": {
            "password": "admin",
            "role": "admin",
            "name": "System Administrator"
        }
    },
    "digiboards": {},
    "teachers": {}
}

def load_db():
    if not os.path.exists(DATA_FILE):
        save_db(DEFAULT_DB)
        return DEFAULT_DB
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return DEFAULT_DB

def save_db(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

DB = load_db()

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
        button { width: 100%; padding: 0.75rem; margin-top: 1.5rem; background: #0284c7; border: none; color: white; border-radius: 6px; font-weight: bold; cursor: pointer; transition: background 0.2s; }
        button:hover { background: #0369a1; }
        .error { color: #ef4444; font-size: 0.875rem; text-align: center; margin-bottom: 1rem; background: rgba(239, 68, 68, 0.1); padding: 0.5rem; border-radius: 4px; }
    </style>
</head>
<body>
    <div class="login-card">
        <h2>DigiBoard Portal Login</h2>
        <!--ERROR-->
        <form action="/login" method="POST">
            <label>Username / Email</label>
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
        header { display: flex; justify-content: space-between; align-items: center; padding: 1rem 2.5rem; border-bottom: 1px solid #111c30; background: #070d19; }
        .header-title { font-size: 1.25rem; font-weight: bold; color: #ffffff; }
        .user-section { display: flex; align-items: center; gap: 1rem; font-size: 0.875rem; color: #94a3b8; }
        .user-id { color: #ffffff; font-weight: 600; }
        .user-role-badge { background: #1e293b; color: #38bdf8; padding: 0.2rem 0.6rem; border-radius: 4px; font-weight: 600; text-transform: uppercase; font-size: 0.75rem; }
        .profile-tile { background: #0284c7; color: #fff; padding: 0.4rem 0.8rem; border-radius: 6px; cursor: pointer; font-weight: bold; font-size: 0.85rem; border: 1px solid #38bdf8; display: flex; align-items: center; gap: 0.4rem; }
        .profile-tile:hover { background: #0369a1; }
        .logout-btn { background: transparent; border: 1px solid #1e293b; color: #38bdf8; padding: 0.4rem 1rem; border-radius: 4px; cursor: pointer; font-size: 0.85rem; }
        .logout-btn:hover { background: #1e293b; color: #fff; }
        .console-container { flex: 1; display: flex; justify-content: center; align-items: center; padding: 2rem; }
        .grid-wrapper { background: rgba(15, 23, 42, 0.6); border: 1px solid #172554; border-radius: 16px; padding: 2.5rem; display: flex; gap: 2rem; box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5); }
        .app-card { width: 150px; height: 150px; background: #091326; border: 1px solid #1e293b; border-radius: 14px; display: flex; flex-direction: column; justify-content: center; align-items: center; cursor: pointer; transition: all 0.2s ease; gap: 0.85rem; }
        .app-card:hover { transform: translateY(-4px); border-color: #38bdf8; background: #0e1d38; }
        .app-icon { width: 56px; height: 56px; border-radius: 14px; display: flex; justify-content: center; align-items: center; }
        .icon-wb { background: #2563eb; }
        .icon-fm { background: #eab308; }
        .app-icon svg { width: 30px; height: 30px; fill: white; }
        .app-title { font-size: 0.85rem; font-weight: 600; color: #cbd5e1; text-align: center; }
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(3, 7, 18, 0.9); justify-content: center; align-items: center; z-index: 100; }
        .modal-content { background: #0f172a; border: 1px solid #1e293b; border-radius: 12px; width: 95%; max-width: 900px; max-height: 90vh; display: flex; flex-direction: column; overflow: hidden; }
        .modal-header { display: flex; justify-content: space-between; align-items: center; padding: 1rem 1.5rem; border-bottom: 1px solid #1e293b; background: #070d19; }
        .modal-header h3 { margin: 0; color: #38bdf8; }
        .close-btn { color: #94a3b8; font-size: 1.5rem; font-weight: bold; cursor: pointer; }
        .modal-body { padding: 1.5rem; overflow-y: auto; flex: 1; color: #f8fafc; }
        form-group { display: block; margin-bottom: 1rem; }
        label { font-size: 0.85rem; color: #94a3b8; display: block; margin-bottom: 0.3rem; }
        input, select { width: 100%; padding: 0.6rem; border: 1px solid #334155; background: #070d19; color: #fff; border-radius: 6px; box-sizing: border-box; }
        .btn-submit { background: #10b981; color: white; border: none; padding: 0.75rem 1.5rem; border-radius: 6px; font-weight: bold; cursor: pointer; width: 100%; margin-top: 1rem; }
        .subject-teacher-row { display: flex; gap: 0.5rem; margin-bottom: 0.5rem; }
        .file-item { display: flex; justify-content: space-between; align-items: center; padding: 0.75rem 1rem; background: #070d19; border: 1px solid #1e293b; border-radius: 6px; margin-bottom: 0.5rem; }
        .file-item a { color: #38bdf8; text-decoration: none; font-weight: 500; }
    </style>
</head>
<body>
    <header>
        <div class="header-title">DigiBoard Master Console</div>
        <div class="user-section">
            <!--ADMIN_PROFILE_TILE-->
            User ID: <span class="user-id"><!--USERNAME--></span>
            <span class="user-role-badge"><!--USER_ROLE--></span>
            <button class="logout-btn" onclick="window.location.href='/logout'">Logout</button>
        </div>
    </header>

    <div class="console-container">
        <div class="grid-wrapper">
            <div class="app-card" onclick="openFileManager()">
                <div class="app-icon icon-fm">
                    <svg viewBox="0 0 24 24"><path d="M10 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z"/></svg>
                </div>
                <div class="app-title">File Manager</div>
            </div>
        </div>
    </div>

    <!-- ADMIN ACCOUNT CREATION MODAL -->
    <div class="modal" id="admin-modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3>Admin Console - Account Creation</h3>
                <span class="close-btn" onclick="closeApp('admin-modal')">&times;</span>
            </div>
            <div class="modal-body">
                <div style="display:flex; gap:1rem; margin-bottom:1.5rem; border-bottom:1px solid #1e293b; padding-bottom:1rem;">
                    <button style="flex:1; padding:0.5rem; background:#0284c7; border:none; color:white; border-radius:6px; cursor:pointer;" onclick="switchTab('digiboard')">Create Digital Board Account</button>
                    <button style="flex:1; padding:0.5rem; background:#334155; border:none; color:white; border-radius:6px; cursor:pointer;" onclick="switchTab('teacher')">Create Teacher Account</button>
                </div>

                <!-- Digital Board Form -->
                <form id="form-digiboard" action="/admin/create-digiboard" method="POST">
                    <h4>Digital Board Account Creation Format</h4>
                    <label>Class Teacher Name</label>
                    <input type="text" name="class_teacher_name" required>
                    <label>Class</label>
                    <input type="text" name="class_name" placeholder="e.g. Grade6" required>
                    <label>Section</label>
                    <input type="text" name="section_name" placeholder="e.g. E" required>
                    <label>Room Number</label>
                    <input type="text" name="room_number" required>
                    <label>Username</label>
                    <input type="text" name="username" required>
                    <label>Password</label>
                    <input type="password" name="password" required>
                    <button type="submit" class="btn-submit">Create Digital Board Account</button>
                </form>

                <!-- Teacher Form -->
                <form id="form-teacher" action="/admin/create-teacher" method="POST" style="display:none;">
                    <h4>Teacher Account Creation Format</h4>
                    <label>Class Teacher Name</label>
                    <input type="text" name="class_teacher_name" required>
                    
                    <label>Subject Teachers (Can add up to 12+ teachers)</label>
                    <div id="subject-teachers-container">
                        <div class="subject-teacher-row">
                            <input type="text" name="subject_name[]" placeholder="Subject Name (e.g., Math)" required>
                            <input type="text" name="teacher_name[]" placeholder="Teacher Name" required>
                        </div>
                    </div>
                    <button type="button" onclick="addSubjectTeacherRow()" style="background:#1e293b; color:#38bdf8; border:1px solid #334155; padding:0.4rem; border-radius:4px; margin-bottom:1rem; cursor:pointer;">+ Add Subject Teacher</button>

                    <label>Class</label>
                    <input type="text" name="class_name" placeholder="e.g. Grade6" required>
                    <label>Section</label>
                    <input type="text" name="section_name" placeholder="e.g. E" required>
                    <label>Room Number</label>
                    <input type="text" name="room_number" required>
                    <label>Username</label>
                    <input type="text" name="username" required>
                    <label>Password</label>
                    <input type="password" name="password" required>
                    <button type="submit" class="btn-submit">Create Teacher Account</button>
                </form>
            </div>
        </div>
    </div>

    <!-- FILE MANAGER MODAL -->
    <div class="modal" id="filemanager-modal">
        <div class="modal-content" style="max-width: 700px;">
            <div class="modal-header">
                <h3>Class File Manager (<span id="fm-scope">Loading...</span>)</h3>
                <span class="close-btn" onclick="closeApp('filemanager-modal')">&times;</span>
            </div>
            <div class="modal-body">
                <!-- TEACHER UPLOAD SECTION -->
                <!--ROLE_TEACHER_ONLY-->
                <form action="/upload" method="POST" enctype="multipart/form-data" style="background:#070d19; padding:1rem; border-radius:6px; margin-bottom:1rem; border:1px solid #1e293b;">
                    <label>Save File To Class:</label>
                    <input type="text" id="upload_class" name="class_name" placeholder="Grade6" required>
                    <label>Section:</label>
                    <input type="text" id="upload_section" name="section_name" placeholder="E" required>
                    <label>Subject:</label>
                    <input type="text" name="subject_name" placeholder="Sanskrit / Math / Social" required>
                    <label>Select Document:</label>
                    <input type="file" name="file" required style="margin-bottom:0.5rem;">
                    <button type="submit" class="btn-submit" style="margin-top:0.5rem;">Save Document</button>
                </form>
                <!--END_ROLE-->

                <!-- SUBJECT SELECTOR -->
                <div style="margin-bottom:1rem;">
                    <label>Select Subject Folder:</label>
                    <select id="subject-filter" onchange="loadFileList()">
                        <option value="">-- Select Subject --</option>
                    </select>
                </div>

                <div id="file-list-container">
                    <p style="color:#94a3b8; text-align:center;">Select a subject folder to view files.</p>
                </div>
            </div>
        </div>
    </div>

    <script>
        const USER_ROLE = "<!--USER_ROLE-->";
        const USER_CLASS = "<!--USER_CLASS-->";
        const USER_SECTION = "<!--USER_SECTION-->";

        function openApp(id) { document.getElementById(id).style.display = 'flex'; }
        function closeApp(id) { document.getElementById(id).style.display = 'none'; }

        function openAdminModal() { openApp('admin-modal'); }

        function switchTab(tab) {
            if(tab === 'digiboard') {
                document.getElementById('form-digiboard').style.display = 'block';
                document.getElementById('form-teacher').style.display = 'none';
            } else {
                document.getElementById('form-digiboard').style.display = 'none';
                document.getElementById('form-teacher').style.display = 'block';
            }
        }

        function addSubjectTeacherRow() {
            const container = document.getElementById('subject-teachers-container');
            const row = document.createElement('div');
            row.className = 'subject-teacher-row';
            row.innerHTML = `<input type="text" name="subject_name[]" placeholder="Subject Name" required>
                             <input type="text" name="teacher_name[]" placeholder="Teacher Name" required>`;
            container.appendChild(row);
        }

        function openFileManager() {
            openApp('filemanager-modal');
            document.getElementById('fm-scope').innerText = USER_ROLE === 'student' ? `${USER_CLASS} - ${USER_SECTION}` : "Teacher Portal";
            
            if(USER_ROLE === 'teacher') {
                document.getElementById('upload_class').value = USER_CLASS;
                document.getElementById('upload_section').value = USER_SECTION;
            }

            fetch('/api/subjects')
                .then(r => r.json())
                .then(subjects => {
                    const sel = document.getElementById('subject-filter');
                    sel.innerHTML = '<option value="">-- Select Subject --</option>' + subjects.map(s => `<option value="${s}">${s}</option>`).join('');
                });
        }

        function loadFileList() {
            const subject = document.getElementById('subject-filter').value;
            if(!subject) return;

            fetch(`/api/files?subject=${encodeURIComponent(subject)}`)
                .then(r => r.json())
                .then(files => {
                    const container = document.getElementById('file-list-container');
                    if (!files || files.length === 0) {
                        container.innerHTML = '<p style="color:#94a3b8; text-align:center;">No files available in this subject directory.</p>';
                        return;
                    }
                    container.innerHTML = files.map(file => `
                        <div class="file-item">
                            <a href="/uploads/${encodeURIComponent(file.path)}" target="_blank" download="${file.name}">📄 ${file.name}</a>
                        </div>
                    `).join('');
                });
        }
    </script>
</body>
</html>"""

class DigiBoardHandler(http.server.BaseHTTPRequestHandler):

    def set_no_cache_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
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
            return {}, None, None
        
        boundary = content_type.split('boundary=')[1].encode('utf-8')
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)

        form_data = {}
        file_name = None
        file_bytes = None

        parts = body.split(b'--' + boundary)
        for part in parts:
            if b'Content-Disposition' in part:
                headers_part, data = part.split(b'\r\n\r\n', 1)
                data = data.rsplit(b'\r\n', 1)[0]
                header_text = headers_part.decode('utf-8', errors='ignore')
                
                name_match = re.search(r'name="([^"]+)"', header_text)
                filename_match = re.search(r'filename="([^"]+)"', header_text)

                if filename_match:
                    file_name = os.path.basename(filename_match.group(1))
                    file_bytes = data
                elif name_match:
                    form_data[name_match.group(1)] = data.decode('utf-8').strip()

        return form_data, file_name, file_bytes

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
                    SESSIONS.pop(cookie['session_id'].value, None)
            self.redirect("/login")
            return

        if path in ("/", "/dashboard"):
            if not session:
                self.redirect("/login")
                return
            
            html = CONSOLE_HTML.replace("<!--USERNAME-->", session['username'])
            html = html.replace("<!--USER_ROLE-->", session['role'])
            html = html.replace("<!--USER_CLASS-->", session.get('class', ''))
            html = html.replace("<!--USER_SECTION-->", session.get('section', ''))

            if session['role'] == 'admin':
                tile_html = '<div class="profile-tile" onclick="openAdminModal()">👤 Profile / Admin Portal</div>'
                html = html.replace("<!--ADMIN_PROFILE_TILE-->", tile_html)
            else:
                html = html.replace("<!--ADMIN_PROFILE_TILE-->", "")

            if session['role'] != 'teacher':
                html = re.sub(r'<!--ROLE_TEACHER_ONLY-->.*?<!--END_ROLE-->', '', html, flags=re.DOTALL)
            else:
                html = html.replace("<!--ROLE_TEACHER_ONLY-->", "").replace("<!--END_ROLE-->", "")
                
            self.send_html(html)
            return

        if path == "/api/subjects":
            if not session:
                self.send_json([], 401)
                return
            
            cls, sec = session.get('class'), session.get('section')
            target_dir = os.path.join(UPLOAD_DIR, cls, sec) if cls and sec else UPLOAD_DIR
            
            subjects = []
            if os.path.exists(target_dir):
                subjects = [d for d in os.listdir(target_dir) if os.path.isdir(os.path.join(target_dir, d))]
            self.send_json(subjects)
            return

        if path == "/api/files":
            if not session:
                self.send_json([], 401)
                return
            
            query = urllib.parse.parse_qs(parsed.query)
            subject = query.get('subject', [''])[0]
            cls, sec = session.get('class'), session.get('section')

            if not cls or not sec or not subject:
                self.send_json([])
                return

            subj_dir = os.path.join(UPLOAD_DIR, cls, sec, subject)
            files = []
            if os.path.exists(subj_dir):
                for f in os.listdir(subj_dir):
                    rel_path = f"{cls}/{sec}/{subject}/{f}"
                    files.append({"name": f, "path": rel_path})
            self.send_json(files)
            return

        if path.startswith("/uploads/"):
            filepath = os.path.join(UPLOAD_DIR, urllib.parse.unquote(path[len("/uploads/"):].lstrip('/')))
            if os.path.exists(filepath) and os.path.isfile(filepath):
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
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

        if path == "/login":
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length).decode('utf-8')
            params = urllib.parse.parse_qs(body)
            username = params.get('username', [''])[0]
            password = params.get('password', [''])[0]

            user_data = DB["users"].get(username)
            if user_data and user_data['password'] == password:
                sid = str(uuid.uuid4())
                SESSIONS[sid] = {
                    "username": username,
                    "role": user_data['role'],
                    "class": user_data.get('class', ''),
                    "section": user_data.get('section', '')
                }
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

        if path == "/admin/create-digiboard" and session['role'] == 'admin':
            length = int(self.headers.get('Content-Length', 0))
            params = urllib.parse.parse_qs(self.rfile.read(length).decode('utf-8'))
            
            username = params.get('username', [''])[0]
            DB["users"][username] = {
                "password": params.get('password', [''])[0],
                "role": "student",
                "class": params.get('class_name', [''])[0],
                "section": params.get('section_name', [''])[0],
                "room": params.get('room_number', [''])[0],
                "class_teacher": params.get('class_teacher_name', [''])[0]
            }
            save_db(DB)
            self.redirect("/")
            return

        if path == "/admin/create-teacher" and session['role'] == 'admin':
            length = int(self.headers.get('Content-Length', 0))
            params = urllib.parse.parse_qs(self.rfile.read(length).decode('utf-8'))
            
            username = params.get('username', [''])[0]
            subjects = params.get('subject_name[]', [])
            teachers = params.get('teacher_name[]', [])
            
            subject_teacher_map = dict(zip(subjects, teachers))

            DB["users"][username] = {
                "password": params.get('password', [''])[0],
                "role": "teacher",
                "class": params.get('class_name', [''])[0],
                "section": params.get('section_name', [''])[0],
                "room": params.get('room_number', [''])[0],
                "class_teacher": params.get('class_teacher_name', [''])[0],
                "subject_teachers": subject_teacher_map
            }
            save_db(DB)
            self.redirect("/")
            return

        if path == "/upload" and session['role'] == 'teacher':
            form_data, filename, file_data = self.parse_multipart()
            cls = form_data.get('class_name')
            sec = form_data.get('section_name')
            subject = form_data.get('subject_name')

            if cls and sec and subject and filename and file_data:
                target_dir = os.path.join(UPLOAD_DIR, cls, sec, subject)
                os.makedirs(target_dir, exist_ok=True)
                with open(os.path.join(target_dir, filename), "wb") as f:
                    f.write(file_data)

            self.redirect("/")
            return

        self.send_error(404)

if __name__ == "__main__":
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    with socketserver.TCPServer(("", PORT), DigiBoardHandler) as httpd:
        print(f"DigiBoard Portal active at http://localhost:{PORT}")
        httpd.serve_forever()
