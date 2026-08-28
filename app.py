import update
update.start_background_updater()

import http.server
import socketserver
import urllib.parse
import urllib.request
import json
import os
import sys
import uuid
import subprocess
import threading
import socket
from http import cookies

# --- OS-SAFE FILE LAUNCHER ---
def open_local_file(filepath):
    """Safely open local documents across Windows, macOS, and Linux servers."""
    try:
        if hasattr(os, 'startfile'):
            os.startfile(filepath)
        elif sys.platform.startswith('darwin'):
            subprocess.Popen(['open', filepath])
        else:
            subprocess.Popen(['xdg-open', filepath], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"[File Launcher] Cannot open file locally: {e}")

PORT = int(os.environ.get("PORT", 8000))
UPLOAD_DIR = "uploads"

# --- SUPABASE CONFIG ---
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://wkiihxsqvwdsmmppqrwx.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndraWloeHNxdndkc21tcHBxcnd4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODcwNDk3ODUsImV4cCI6MjEwMjYyNTc4NX0.kqcgJH-bBHDgwMkxg7vbdXIvPUQynA2fPnq65oQ0v20")

os.makedirs(UPLOAD_DIR, exist_ok=True)
SESSIONS = {}
BOARD_CACHE = "[]"
CACHE_LOCK = threading.Lock()

USERS = {
    "juraghav@Digiboardleaning.com": {"password": "2234269580", "role": "teacher"},
    "socialstudiesclass@Digiboardleaning.com": {"password": "2234269580", "role": "student"}
}

def get_local_ip():
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
        with CACHE_LOCK:
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
        .modal-content { background: #091a34; border: 1px solid #38bdf8; border-radius: 16px; padding: 25px; width: 1000px; max-width: 95%; position: relative; }
        .close-btn { position: absolute; top: 15px; right: 20px; color: #ef4444; font-size: 24px; cursor: pointer; z-index: 110; }
        
        /* Interactive Whiteboard Tool Palette (Apple PencilKit Style) */
        .wb-container { position: relative; width: 100%; height: 520px; background: #ffffff; border-radius: 12px; overflow: hidden; background-image: radial-gradient(#cbd5e1 1.5px, transparent 1.5px); background-size: 24px 24px; }
        canvas { width: 100%; height: 100%; cursor: crosshair; touch-action: none; display: block; }
        
        .toolbar { position: absolute; left: 15px; top: 50%; transform: translateY(-50%); background: rgba(248, 250, 252, 0.92); backdrop-filter: blur(16px); border: 1px solid #e2e8f0; border-radius: 35px; padding: 12px 10px; display: flex; flex-direction: column; align-items: center; gap: 10px; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.3); z-index: 10; }
        .tool-btn { width: 44px; height: 44px; border-radius: 50%; border: 2px solid transparent; background: transparent; cursor: pointer; display: flex; justify-content: center; align-items: center; font-size: 18px; transition: all 0.2s; }
        .tool-btn.active { border-color: #0284c7; background: #e0f2fe; transform: scale(1.1); }
        .color-dot { width: 28px; height: 28px; border-radius: 50%; border: 2px solid #ffffff; cursor: pointer; box-shadow: 0 2px 4px rgba(0,0,0,0.2); }
        .color-dot.active { border-color: #0284c7; transform: scale(1.15); }
        
        .sub-panel { position: absolute; left: 75px; top: 50%; transform: translateY(-50%); background: rgba(255,255,255,0.95); backdrop-filter: blur(12px); border: 1px solid #cbd5e1; border-radius: 16px; padding: 12px 16px; display: flex; flex-direction: column; gap: 10px; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.2); z-index: 9; }
        .thickness-opts { display: flex; gap: 8px; align-items: center; }
        .size-circle { background: #334155; border-radius: 50%; cursor: pointer; }
        .size-circle.active { outline: 2px solid #0284c7; outline-offset: 2px; }

        /* File Manager List Styles */
        .file-list { list-style: none; margin-top: 15px; max-height: 280px; overflow-y: auto; }
        .file-item { display: flex; justify-content: space-between; align-items: center; background: rgba(15, 42, 86, 0.7); padding: 10px 15px; border-radius: 6px; margin-bottom: 8px; border: 1px solid rgba(56, 189, 248, 0.2); }
        .file-item a { color: #38bdf8; text-decoration: none; font-weight: bold; word-break: break-all; }
        .file-actions a { color: #ef4444; margin-left: 15px; text-decoration: none; font-size: 13px; font-weight: bold; }
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
            <div class="app-card" onclick="openModal('whiteboard-modal'); resizeCanvas();">
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
                <span>Document Viewer</span>
            </div>

            <div class="app-card" onclick="openFileManager()">
                <svg viewBox="0 0 100 100">
                    <path d="M10 25 C10 20, 20 20, 35 20 L45 30 L90 30 L95 40 L95 80 L15 85 Z" fill="#eab308"/>
                    <rect x="25" y="50" width="50" height="30" rx="5" fill="#0284c7"/>
                </svg>
                <span>File Manager</span>
            </div>
        </div>
    </div>

    <!-- Apple PencilKit Style Whiteboard Modal -->
    <div id="whiteboard-modal" class="modal">
        <div class="modal-content">
            <span class="close-btn" onclick="closeModal('whiteboard-modal')">&times;</span>
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                <h3 style="color:#38bdf8;">Interactive Studio Whiteboard</h3>
                <div style="display:flex; gap:10px;">
                    <button onclick="undoStroke()" style="padding:6px 14px; background:#0284c7; color:white; border:none; border-radius:6px; cursor:pointer;">↩ Undo</button>
                    <button onclick="clearBoard()" style="padding:6px 14px; background:#ef4444; color:white; border:none; border-radius:6px; cursor:pointer;">🗑 Clear Board</button>
                </div>
            </div>
            
            <div class="wb-container">
                <!-- Floating Vertical Palette -->
                <div class="toolbar">
                    <button class="tool-btn active" title="Pen" onclick="selectTool('pen', this)">🖊️</button>
                    <button class="tool-btn" title="Fine Tip Marker" onclick="selectTool('marker', this)">🖋️</button>
                    <button class="tool-btn" title="Highlighter" onclick="selectTool('highlighter', this)">🖍️</button>
                    <button class="tool-btn" title="Eraser" onclick="selectTool('eraser', this)">🧹</button>
                    <div style="width:28px; height:1px; background:#cbd5e1; margin:4px 0;"></div>
                    <div class="color-dot active" style="background:#000000;" onclick="selectColor('#000000', this)"></div>
                    <div class="color-dot" style="background:#ef4444;" onclick="selectColor('#ef4444', this)"></div>
                    <div class="color-dot" style="background:#3b82f6;" onclick="selectColor('#3b82f6', this)"></div>
                    <div class="color-dot" style="background:#10b981;" onclick="selectColor('#10b981', this)"></div>
                    <div class="color-dot" style="background:#eab308;" onclick="selectColor('#eab308', this)"></div>
                </div>

                <!-- Stroke Customization Options -->
                <div class="sub-panel">
                    <span style="font-size:11px; font-weight:bold; color:#475569;">STROKE SIZE</span>
                    <div class="thickness-opts">
                        <div class="size-circle" style="width:6px; height:6px;" onclick="setSize(2, this)"></div>
                        <div class="size-circle active" style="width:12px; height:12px;" onclick="setSize(5, this)"></div>
                        <div class="size-circle" style="width:18px; height:18px;" onclick="setSize(12, this)"></div>
                        <div class="size-circle" style="width:24px; height:24px;" onclick="setSize(22, this)"></div>
                    </div>
                    <span style="font-size:11px; font-weight:bold; color:#475569; margin-top:4px;">OPACITY</span>
                    <input type="range" id="opacitySlider" min="0.1" max="1" step="0.1" value="1" onchange="currentOpacity = parseFloat(this.value)">
                </div>

                <canvas id="board"></canvas>
            </div>
        </div>
    </div>

    <!-- File Manager & Upload Modal -->
    <div id="upload-modal" class="modal">
        <div class="modal-content" style="width: 550px;">
            <span class="close-btn" onclick="closeModal('upload-modal')">&times;</span>
            <h3 style="color:#38bdf8; margin-bottom:15px;">Upload Class Resource</h3>
            <form action="/upload" method="post" enctype="multipart/form-data" style="margin-bottom: 25px;">
                <input type="file" name="file" required style="margin-bottom:15px; color:#e0f2fe; display:block;">
                <button type="submit" style="padding:10px 20px; background:#0284c7; color:white; border:none; border-radius:6px; cursor:pointer;">Upload File</button>
            </form>

            <h4 style="color:#38bdf8; border-top: 1px solid rgba(56, 189, 248, 0.3); padding-top: 15px;">Uploaded Files</h4>
            <ul id="file-list-container" class="file-list">
                <li style="color:#94a3b8;">Loading files...</li>
            </ul>
        </div>
    </div>

    <script>
        function openModal(id) { document.getElementById(id).style.display = 'flex'; }
        function closeModal(id) { document.getElementById(id).style.display = 'none'; }
        
        function launchWPS() { window.location.href = '/launch-wps'; }

        function openFileManager() {
            openModal('upload-modal');
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
                            <div class="file-actions">
                                <a href="#" onclick="deleteFile('${encodeURIComponent(file)}'); return false;">Delete</a>
                            </div>
                        </li>
                    `).join('');
                })
                .catch(() => {
                    document.getElementById('file-list-container').innerHTML = '<li style="color:#ef4444;">Error loading files.</li>';
                });
        }

        function deleteFile(filename) {
            if (confirm("Are you sure you want to delete this file?")) {
                fetch('/api/delete-file?name=' + filename, { method: 'DELETE' })
                    .then(() => loadFileList());
            }
        }

        // --- WHITEBOARD ENGINE ---
        const canvas = document.getElementById('board');
        const ctx = canvas.getContext('2d');
        let drawing = false, strokes = [], currentStroke = null;
        let currentTool = 'pen', currentColor = '#000000', currentSize = 5, currentOpacity = 1.0;

        function resizeCanvas() {
            const rect = canvas.parentElement.getBoundingClientRect();
            canvas.width = rect.width;
            canvas.height = rect.height;
            redraw();
        }

        function selectTool(tool, el) {
            currentTool = tool;
            document.querySelectorAll('.tool-btn').forEach(b => b.classList.remove('active'));
            el.classList.add('active');
            if (tool === 'highlighter') {
                currentOpacity = 0.4;
                document.getElementById('opacitySlider').value = 0.4;
            } else if (tool === 'eraser') {
                currentOpacity = 1.0;
            }
        }

        function selectColor(color, el) {
            currentColor = color;
            document.querySelectorAll('.color-dot').forEach(d => d.classList.remove('active'));
            el.classList.add('active');
        }

        function setSize(size, el) {
            currentSize = size;
            document.querySelectorAll('.size-circle').forEach(c => c.classList.remove('active'));
            el.classList.add('active');
        }

        canvas.onpointerdown = (e) => { 
            drawing = true; 
            const rect = canvas.getBoundingClientRect();
            currentStroke = {
                tool: currentTool,
                color: currentColor,
                size: currentSize,
                opacity: currentOpacity,
                pts: [{x: e.clientX - rect.left, y: e.clientY - rect.top}]
            }; 
        };

        canvas.onpointermove = (e) => {
            if (!drawing) return;
            const rect = canvas.getBoundingClientRect();
            currentStroke.pts.push({x: e.clientX - rect.left, y: e.clientY - rect.top});
            redraw();
        };

        canvas.onpointerup = () => { 
            if (drawing) { 
                strokes.push(currentStroke); 
                drawing = false; 
                currentStroke = null;
                saveBoard(); 
            } 
        };

        function redraw() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            const allStrokes = currentStroke ? strokes.concat([currentStroke]) : strokes;
            
            allStrokes.forEach(s => {
                if (s.pts.length < 1) return;
                ctx.save();
                ctx.beginPath();
                ctx.lineCap = "round";
                ctx.lineJoin = "round";

                if (s.tool === 'eraser') {
                    ctx.globalCompositeOperation = 'destination-out';
                    ctx.lineWidth = s.size * 3;
                } else {
                    ctx.globalCompositeOperation = 'source-over';
                    ctx.strokeStyle = s.color;
                    ctx.globalAlpha = s.opacity;
                    ctx.lineWidth = s.size;
                }

                s.pts.forEach((pt, i) => {
                    if (i === 0) ctx.moveTo(pt.x, pt.y);
                    else ctx.lineTo(pt.x, pt.y);
                });
                ctx.stroke();
                ctx.restore();
            });
        }

        function undoStroke() { strokes.pop(); redraw(); saveBoard(); }
        function clearBoard() { strokes = []; redraw(); saveBoard(); }

        function saveBoard() {
            fetch('/api/whiteboard', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(strokes)
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
        .main-container { display: flex; justify-content: center; align-items: center; flex-grow: 1; padding: 40px; }
        .app-grid { display: grid; grid-template-columns: repeat(2, 180px); gap: 40px; background: rgba(8, 28, 58, 0.75); backdrop-filter: blur(12px); padding: 40px; border-radius: 20px; border: 1px solid rgba(0, 195, 255, 0.4); }
        .app-card { display: flex; flex-direction: column; align-items: center; justify-content: center; background: rgba(15, 42, 86, 0.6); border: 1px solid rgba(56, 189, 248, 0.2); border-radius: 16px; padding: 20px; cursor: pointer; transition: all 0.3s; text-decoration: none; }
        .app-card:hover { transform: translateY(-8px); border-color: #38bdf8; background: rgba(20, 55, 110, 0.8); }
        .app-card svg { width: 70px; height: 70px; margin-bottom: 12px; }
        .app-card span { color: #f0f9ff; font-size: 14px; font-weight: 600; }
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(2, 11, 24, 0.85); backdrop-filter: blur(8px); justify-content: center; align-items: center; z-index: 100; }
        .modal-content { background: #091a34; border: 1px solid #38bdf8; border-radius: 16px; padding: 25px; width: 900px; max-width: 95%; position: relative; }
        .close-btn { position: absolute; top: 15px; right: 20px; color: #ef4444; font-size: 24px; cursor: pointer; }
        
        .wb-container { position: relative; width: 100%; height: 480px; background: #ffffff; border-radius: 12px; overflow: hidden; background-image: radial-gradient(#cbd5e1 1.5px, transparent 1.5px); background-size: 24px 24px; }
        canvas { width: 100%; height: 100%; pointer-events: none; }
        
        .file-list { list-style: none; margin-top: 15px; max-height: 250px; overflow-y: auto; }
        .file-item { display: flex; justify-content: space-between; align-items: center; background: rgba(15, 42, 86, 0.7); padding: 12px 16px; border-radius: 6px; margin-bottom: 10px; border: 1px solid rgba(56, 189, 248, 0.2); }
        .media-preview { margin-top: 10px; display: none; background: #020b18; border-radius: 8px; padding: 10px; }
        video, audio { width: 100%; max-height: 250px; }
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
        <div class="app-grid">
            <div class="app-card" onclick="openModal('whiteboard-modal'); resizeCanvas();">
                <svg viewBox="0 0 100 100">
                    <rect width="100" height="100" rx="20" fill="url(#blue-grad)"/>
                    <path d="M20 65 Q 40 30, 60 65 T 90 40" stroke="white" stroke-width="8" fill="none" stroke-linecap="round"/>
                    <defs>
                        <linearGradient id="blue-grad" x1="0%" y1="0%" x2="100%" y2="100%">
                            <stop offset="0%" style="stop-color:#0052D4;" />
                            <stop offset="100%" style="stop-color:#4364F7;" />
                        </linearGradient>
                    </defs>
                </svg>
                <span>Live Whiteboard</span>
            </div>

            <div class="app-card" onclick="openFileManager()">
                <svg viewBox="0 0 100 100">
                    <path d="M10 25 C10 20, 20 20, 35 20 L45 30 L90 30 L95 40 L95 80 L15 85 Z" fill="#eab308"/>
                    <rect x="25" y="50" width="50" height="30" rx="5" fill="#0284c7"/>
                </svg>
                <span>Resource Viewer</span>
            </div>
        </div>
    </div>

    <!-- Student Read-Only Whiteboard View -->
    <div id="whiteboard-modal" class="modal">
        <div class="modal-content">
            <span class="close-btn" onclick="closeModal('whiteboard-modal')">&times;</span>
            <h3 style="color:#38bdf8; margin-bottom:12px;">Teacher Live Stream (Read-Only)</h3>
            <div class="wb-container">
                <canvas id="board"></canvas>
            </div>
        </div>
    </div>

    <!-- Student Resource Viewer (Read/Listen/Watch Only) -->
    <div id="upload-modal" class="modal">
        <div class="modal-content" style="width: 650px;">
            <span class="close-btn" onclick="closeModal('upload-modal')">&times;</span>
            <h3 style="color:#38bdf8; margin-bottom:15px;">Class Resources & Media</h3>
            
            <ul id="file-list-container" class="file-list">
                <li style="color:#94a3b8;">Loading resources...</li>
            </ul>

            <div id="media-player-box" class="media-preview">
                <!-- Media dynamically mounted here -->
            </div>
        </div>
    </div>

    <script>
        function openModal(id) { document.getElementById(id).style.display = 'flex'; }
        function closeModal(id) { document.getElementById(id).style.display = 'none'; }

        function openFileManager() {
            openModal('upload-modal');
            loadFileList();
        }

        function loadFileList() {
            fetch('/api/files')
                .then(r => r.json())
                .then(files => {
                    const container = document.getElementById('file-list-container');
                    if (files.length === 0) {
                        container.innerHTML = '<li style="color:#94a3b8;">No class resources available.</li>';
                        return;
                    }
                    container.innerHTML = files.map(file => {
                        const ext = file.split('.').pop().toLowerCase();
                        let actionBtn = `<a href="/uploads/${encodeURIComponent(file)}" target="_blank" style="color:#38bdf8; text-decoration:none;">📄 Read / Open</a>`;
                        
                        if (['mp4', 'webm', 'ogg'].includes(ext)) {
                            actionBtn = `<button onclick="playMedia('/uploads/${encodeURIComponent(file)}', 'video')" style="background:#0284c7; color:white; border:none; padding:4px 10px; border-radius:4px; cursor:pointer;">▶ Play Video</button>`;
                        } else if (['mp3', 'wav', 'aac'].includes(ext)) {
                            actionBtn = `<button onclick="playMedia('/uploads/${encodeURIComponent(file)}', 'audio')" style="background:#10b981; color:white; border:none; padding:4px 10px; border-radius:4px; cursor:pointer;">🎵 Listen Audio</button>`;
                        }

                        return `
                            <li class="file-item">
                                <span style="font-weight:bold;">${file}</span>
                                <div>${actionBtn}</div>
                            </li>
                        `;
                    }).join('');
                });
        }

        function playMedia(url, type) {
            const box = document.getElementById('media-player-box');
            box.style.display = 'block';
            if (type === 'video') {
                box.innerHTML = `<video controls autoplay src="${url}"></video>`;
            } else if (type === 'audio') {
                box.innerHTML = `<audio controls autoplay src="${url}"></audio>`;
            }
        }

        // --- LIVE CANVAS SYNC ---
        const canvas = document.getElementById('board');
        const ctx = canvas.getContext('2d');
        let lastRaw = "";

        function resizeCanvas() {
            const rect = canvas.parentElement.getBoundingClientRect();
            canvas.width = rect.width;
            canvas.height = rect.height;
            fetchBoard();
        }

        function fetchBoard() {
            fetch('/api/whiteboard')
                .then(r => r.text())
                .then(rawText => {
                    if (rawText === lastRaw) return;
                    lastRaw = rawText;
                    const strokes = JSON.parse(rawText);
                    ctx.clearRect(0, 0, canvas.width, canvas.height);
                    
                    strokes.forEach(s => {
                        if (s.pts.length < 1) return;
                        ctx.save();
                        ctx.beginPath();
                        ctx.lineCap = "round";
                        ctx.lineJoin = "round";

                        if (s.tool === 'eraser') {
                            ctx.globalCompositeOperation = 'destination-out';
                            ctx.lineWidth = s.size * 3;
                        } else {
                            ctx.globalCompositeOperation = 'source-over';
                            ctx.strokeStyle = s.color;
                            ctx.globalAlpha = s.opacity;
                            ctx.lineWidth = s.size;
                        }

                        s.pts.forEach((pt, i) => {
                            if (i === 0) ctx.moveTo(pt.x, pt.y);
                            else ctx.lineTo(pt.x, pt.y);
                        });
                        ctx.stroke();
                        ctx.restore();
                    });
                }).catch(() => {});
        }
        setInterval(fetchBoard, 150);
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
        elif parsed.path == "/launch-wps":
            default_doc = os.path.join(UPLOAD_DIR, "Document.docx")
            if not os.path.exists(default_doc):
                with open(default_doc, "wb") as f:
                    f.write(b"")

            open_local_file(default_doc)

            self.send_response(200)
            self.send_header('Content-Type', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
            self.send_header('Content-Disposition', 'attachment; filename="Document.docx"')
            self.end_headers()
            with open(default_doc, 'rb') as f:
                self.wfile.write(f.read())
        elif parsed.path == "/api/files":
            files = os.listdir(UPLOAD_DIR) if os.path.exists(UPLOAD_DIR) else []
            self.send_json(files)
        elif parsed.path.startswith("/uploads/"):
            filename = urllib.parse.unquote(parsed.path.replace("/uploads/", ""))
            filepath = os.path.join(UPLOAD_DIR, filename)
            if os.path.exists(filepath):
                self.send_response(200)
                self.send_header('Content-Type', 'application/octet-stream')
                self.send_header('Content-Disposition', f'inline; filename="{filename}"')
                self.end_headers()
                with open(filepath, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404, "File Not Found")
        elif parsed.path == "/api/whiteboard":
            with CACHE_LOCK:
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

        elif self.path == "/api/whiteboard":
            session = self.get_session()
            if not session or session.get('role') != 'teacher':
                self.send_error(403, "Students cannot modify the whiteboard")
                return

            with CACHE_LOCK:
                BOARD_CACHE = body.decode('utf-8')
            threading.Thread(
                target=supabase_request,
                args=("whiteboard?id=eq.1", "PATCH", {"lines": BOARD_CACHE}),
                daemon=True
            ).start()
            self.send_json('{"status":"ok"}')

    def do_DELETE(self):
        session = self.get_session()
        if not session or session.get('role') != 'teacher':
            self.send_error(403, "Students cannot delete files")
            return

        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/delete-file":
            params = urllib.parse.parse_qs(parsed.query)
            filename = params.get('name', [''])[0]
            if filename:
                filepath = os.path.join(UPLOAD_DIR, os.path.basename(filename))
                if os.path.exists(filepath):
                    os.remove(filepath)
            self.send_json('{"status":"deleted"}')

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
    print(f"Local Access:    http://localhost:{PORT}")
    print(f"Network Access: http://{local_ip}:{PORT}")
    print("==================================================")
    
    with socketserver.TCPServer(("0.0.0.0", PORT), DigiBoardHandler) as httpd:
        httpd.serve_forever()
