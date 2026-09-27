import os
import json
import shutil
import docker
from flask import Flask, render_template_string, request, redirect, url_for, session, flash, jsonify, Response
from datetime import timedelta

app = Flask(__name__)
app.secret_key = "super_secret_pterodactyl_key"
app.permanent_session_lifetime = timedelta(days=30)

# Cookie isolation settings to prevent session collisions on localhost
app.config['SESSION_COOKIE_NAME'] = 'ptero_panel_session'
app.config['SESSION_COOKIE_PATH'] = '/'

DB_FILE = "data.json"
SERVERS_DIR = os.path.abspath("server_files")

os.makedirs(SERVERS_DIR, exist_ok=True)

try:
    docker_client = docker.from_env()
except Exception:
    docker_client = None

# --- EMBEDDED HTML TEMPLATES & CSS ---

BASE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Pterodactyl Panel Replica</title>
    <style>
        body { background-color: #1e1e2f; color: #cfd8dc; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 0; }
        .navbar { background-color: #151522; display: flex; justify-content: space-between; padding: 15px 30px; border-bottom: 1px solid #2a2a40; }
        .nav-brand { font-weight: bold; font-size: 1.2rem; color: #3b82f6; text-transform: uppercase; }
        .nav-links a { color: #94a3b8; text-decoration: none; margin-left: 20px; }
        .nav-links a:hover { color: #ffffff; }
        .container { max-width: 1050px; margin: 40px auto; padding: 0 20px; }
        .auth-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 25px; }
        .auth-card, .admin-card, .server-card, .panel-card { background-color: #252538; padding: 25px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); margin-bottom: 20px; }
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; margin-bottom: 5px; color: #94a3b8; }
        .form-group input, .form-group select, .form-group textarea { width: 100%; padding: 10px; background-color: #1e1e2f; border: 1px solid #33334d; border-radius: 4px; color: white; box-sizing: border-box; font-family: monospace; }
        .btn { padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; text-decoration: none; display: inline-block; text-align: center; }
        .btn-primary { background-color: #2563eb; color: white; width: 100%; box-sizing: border-box; }
        .btn-primary:hover { background-color: #1d4ed8; }
        .btn-success { background-color: #16a34a; color: white; }
        .btn-warning { background-color: #ca8a04; color: white; }
        .btn-danger { background-color: #dc2626; color: white; }
        .btn-secondary { background-color: #475569; color: white; }
        .server-info { display: flex; justify-content: space-between; align-items: center; }
        .server-specs { margin: 15px 0; display: flex; gap: 20px; color: #94a3b8; font-size: 0.9rem; flex-wrap: wrap; }
        .badge { padding: 4px 8px; border-radius: 4px; font-size: 0.85rem; }
        .status-online { background-color: #14532d; color: #4ade80; }
        .status-offline { background-color: #7f1d1d; color: #f87171; }
        .alert { padding: 12px; border-radius: 4px; margin-bottom: 20px; }
        .alert-success { background-color: #14532d; color: #4ade80; }
        .alert-danger { background-color: #7f1d1d; color: #f87171; }
        .alert-info { background-color: #1e3a8a; color: #93c5fd; }
        .admin-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .nav-tabs { display: flex; gap: 10px; margin-bottom: 20px; border-bottom: 1px solid #33334d; padding-bottom: 10px; }
        .nav-tabs a { color: #94a3b8; text-decoration: none; padding: 8px 15px; border-radius: 4px; background-color: #1e1e2f; }
        .nav-tabs a.active { background-color: #2563eb; color: white; }
        table.file-table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        table.file-table th, table.file-table td { text-align: left; padding: 12px; border-bottom: 1px solid #33334d; }
        table.file-table th { color: #94a3b8; font-size: 0.85rem; }
        table.file-table tr:hover { background-color: #2a2a40; }
        .file-actions { display: flex; gap: 10px; }
        .breadcrumb { background-color: #1e1e2f; padding: 10px 15px; border-radius: 4px; margin-bottom: 15px; font-family: monospace; }
        .breadcrumb a { color: #60a5fa; text-decoration: none; }
    </style>
</head>
<body>
    <nav class="navbar">
        <div class="nav-brand">pterodactyl</div>
        <div class="nav-links">
            {% if session.get('user_id') %}
                <a href="{{ url_for('dashboard') }}">Dashboard</a>
                {% if session.get('is_admin') %}
                    <a href="{{ url_for('admin_panel') }}">Admin Area</a>
                {% endif %}
                <a href="{{ url_for('logout') }}">Logout ({{ session.get('username') }})</a>
            {% else %}
                <a href="{{ url_for('login') }}">Login / Register</a>
            {% endif %}
        </div>
    </nav>

    <div class="container">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        CONTENT_PLACEHOLDER
    </div>
</body>
</html>
"""

LOGIN_HTML = """
<div class="auth-grid">
    <div class="auth-card">
        <h2>Login to Panel</h2>
        <form method="POST">
            <input type="hidden" name="action" value="login">
            <div class="form-group">
                <label>Username</label>
                <input type="text" name="username" required>
            </div>
            <div class="form-group">
                <label>Password</label>
                <input type="password" name="password" required>
            </div>
            <button type="submit" class="btn btn-primary">Login</button>
        </form>
    </div>

    <div class="auth-card">
        <h2>Create Account</h2>
        <form method="POST">
            <input type="hidden" name="action" value="register">
            <div class="form-group">
                <label>Username</label>
                <input type="text" name="reg_username" required>
            </div>
            <div class="form-group">
                <label>Password</label>
                <input type="password" name="reg_password" required>
            </div>
            <div class="form-group">
                <label>Select Node Allocation</label>
                <select name="node_id" required>
                    {% if nodes %}
                        {% for node in nodes %}
                            <option value="{{ node.id }}">{{ node.name }} ({{ node.ip }})</option>
                        {% endfor %}
                    {% else %}
                        <option value="" disabled selected>No nodes available (Contact Admin)</option>
                    {% endif %}
                </select>
            </div>
            <button type="submit" class="btn btn-primary" style="background-color: #16a34a;">Register Account</button>
        </form>
    </div>
</div>
"""

DASHBOARD_HTML = """
<div class="dashboard-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px;">
    <div>
        <h1>Welcome, {{ user.username }}</h1>
        <p>Manage your dedicated server environments below.</p>
    </div>
    <form method="POST" action="{{ url_for('create_server') }}">
        <button type="submit" class="btn btn-success">+ Create New Server</button>
    </form>
</div>

{% if servers %}
    {% for server in servers %}
    <div class="server-card">
        <div class="server-info">
            <h3>{{ server.name }}</h3>
            <span class="badge status-{{ server.status | lower }}">{{ server.status }}</span>
        </div>
        <div class="server-specs">
            <span>RAM Limit: <strong>{{ server.memory }} MB</strong></span>
            <span>CPU Limit: <strong>{{ server.cpu }}%</strong></span>
            <span>Disk Limit: <strong>{{ server.disk }} MB</strong></span>
            <span>Address: <strong style="color: #34d399;">localhost:{{ server.port }}</strong></span>
        </div>
        <div style="display: flex; gap: 10px; flex-wrap: wrap;">
            <a href="{{ url_for('server_console', server_id=server.id) }}" class="btn btn-secondary">Manage Server</a>
            <a href="{{ url_for('server_action', server_id=server.id, action='start') }}" class="btn btn-success">Start</a>
            <a href="{{ url_for('server_action', server_id=server.id, action='restart') }}" class="btn btn-warning">Restart</a>
            <a href="{{ url_for('server_action', server_id=server.id, action='stop') }}" class="btn btn-danger">Stop</a>
        </div>
    </div>
    {% endfor %}
{% else %}
<div class="alert alert-info">
    You do not have any servers assigned yet. Click the "+ Create New Server" button above to spin one up!
</div>
{% endif %}
"""

SERVER_MANAGEMENT_HTML = """
<div class="nav-tabs">
    <a href="{{ url_for('server_console', server_id=server.id) }}" class="{% if tab == 'console' %}active{% endif %}">Console & Metrics</a>
    <a href="{{ url_for('server_files', server_id=server.id) }}" class="{% if tab == 'files' or tab == 'edit_file' %}active{% endif %}">File Manager</a>
    <a href="{{ url_for('server_startup', server_id=server.id) }}" class="{% if tab == 'startup' %}active{% endif %}">Startup Settings</a>
    <a href="{{ url_for('dashboard') }}" style="margin-left: auto; background-color: #334155;">Back to Dashboard</a>
</div>

<h2>{{ server.name }} <span class="badge status-{{ server.status | lower }}" style="font-size: 0.9rem; vertical-align: middle;">{{ server.status }}</span></h2>

{% if tab == 'console' %}
<div class="panel-card">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
        <h3 style="margin: 0;">Live Container Console</h3>
        <span style="font-size: 0.85rem; color: #34d399;">● Live Stream Active</span>
    </div>
    <p style="font-size: 0.85rem; color: #94a3b8; margin-bottom: 15px;">Unique Address: <strong style="color: #34d399;">http://localhost:{{ server.port }}</strong></p>
    
    <div id="terminal-box" style="background: #09090b; border: 1px solid #27272a; border-radius: 6px; padding: 15px; height: 320px; overflow-y: scroll; font-family: monospace; font-size: 0.85rem; color: #38bdf8; white-space: pre-wrap; word-break: break-all; line-height: 1.4;">Connecting to container logs...</div>

    <div class="server-specs" style="background: #1e1e2f; padding: 12px; border-radius: 6px; margin: 15px 0;">
        <span>Realtime RAM: <strong id="console-ram" style="color: #60a5fa;">0 MB</strong></span>
        <span>Realtime CPU: <strong id="console-cpu" style="color: #60a5fa;">0.00%</strong></span>
        <span>Allowed Limits: <strong style="color: #34d399;">RAM: {{ server.memory }}MB | CPU: {{ server.cpu }}% | Disk: {{ server.disk }}MB</strong></span>
    </div>

    <div style="display: flex; gap: 15px;">
        <a href="{{ url_for('server_action', server_id=server.id, action='start') }}" class="btn btn-success">Start Container</a>
        <a href="{{ url_for('server_action', server_id=server.id, action='restart') }}" class="btn btn-warning">Restart Container</a>
        <a href="{{ url_for('server_action', server_id=server.id, action='stop') }}" class="btn btn-danger">Stop Container</a>
    </div>
</div>

<script>
async function updateConsoleLogs() {
    try {
        let res = await fetch("/server/{{ server.id }}/api/logs");
        let text = await res.text();
        let box = document.getElementById("terminal-box");
        let isAtBottom = box.scrollHeight - box.clientHeight <= box.scrollTop + 15;
        box.innerText = text;
        if (isAtBottom) {
            box.scrollTop = box.scrollHeight;
        }
    } catch(e) {}
}

async function updateConsoleStats() {
    try {
        let res = await fetch("/server/{{ server.id }}/stats");
        let data = await res.json();
        if(data.online) {
            document.getElementById("console-ram").innerText = data.memory_usage + " MB";
            document.getElementById("console-cpu").innerText = data.cpu_percent + "%";
        }
    } catch(e) {}
}

setInterval(updateConsoleLogs, 1500);
setInterval(updateConsoleStats, 2000);
updateConsoleLogs();
updateConsoleStats();
</script>
{% endif %}

{% if tab == 'files' %}
<div class="panel-card">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
        <h3>File Manager</h3>
        <div style="display: flex; gap: 10px;">
            <button onclick="document.getElementById('createFolderModal').style.display='block'" class="btn btn-secondary" style="padding: 6px 12px; font-size: 0.85rem;">+ New Folder</button>
            <button onclick="document.getElementById('createFileModal').style.display='block'" class="btn btn-primary" style="padding: 6px 12px; font-size: 0.85rem; width: auto;">+ New File</button>
            <button onclick="document.getElementById('uploadModal').style.display='block'" class="btn btn-success" style="padding: 6px 12px; font-size: 0.85rem;">Upload Files</button>
        </div>
    </div>

    <div class="breadcrumb">
        📁 /home/container/{{ subpath }}
    </div>

    <table class="file-table">
        <thead>
            <tr>
                <th>Name</th>
                <th>Type</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody>
            {% if subpath %}
            <tr>
                <td><a href="{{ url_for('server_files', server_id=server.id, subpath=parent_subpath) }}" style="color: #60a5fa; text-decoration: none;">⬅️ .. (Parent Directory)</a></td>
                <td>-</td>
                <td>-</td>
            </tr>
            {% endif %}
            
            {% for folder in folders %}
            <tr>
                <td>📁 <a href="{{ url_for('server_files', server_id=server.id, subpath=folder.path) }}" style="color: #cfd8dc; text-decoration: none; font-weight: bold;">{{ folder.name }}</a></td>
                <td>Folder</td>
                <td>
                    <div class="file-actions">
                        <button onclick="openRenameModal('{{ folder.path }}', '{{ folder.name }}')" class="btn btn-secondary" style="padding: 4px 8px; font-size: 0.75rem;">Rename</button>
                        <form method="POST" action="{{ url_for('delete_file', server_id=server.id) }}" onsubmit="return confirm('Delete folder and contents?');" style="display:inline;">
                            <input type="hidden" name="filepath" value="{{ folder.path }}">
                            <input type="hidden" name="current_subpath" value="{{ subpath }}">
                            <button type="submit" class="btn btn-danger" style="padding: 4px 8px; font-size: 0.75rem;">Delete</button>
                        </form>
                    </div>
                </td>
            </tr>
            {% endfor %}

            {% for file in files %}
            <tr>
                <td>📄 {{ file.name }}</td>
                <td>File</td>
                <td>
                    <div class="file-actions">
                        <button onclick="openRenameModal('{{ file.path }}', '{{ file.name }}')" class="btn btn-secondary" style="padding: 4px 8px; font-size: 0.75rem;">Rename</button>
                        <a href="{{ url_for('edit_file', server_id=server.id, filepath=file.path) }}" class="btn btn-secondary" style="padding: 4px 8px; font-size: 0.75rem;">Edit</a>
                        <form method="POST" action="{{ url_for('delete_file', server_id=server.id) }}" onsubmit="return confirm('Delete file?');" style="display:inline;">
                            <input type="hidden" name="filepath" value="{{ file.path }}">
                            <input type="hidden" name="current_subpath" value="{{ subpath }}">
                            <button type="submit" class="btn btn-danger" style="padding: 4px 8px; font-size: 0.75rem;">Delete</button>
                        </form>
                    </div>
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>

<div id="createFileModal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.6); z-index:100;">
    <div style="background:#252538; max-width:400px; margin: 100px auto; padding:25px; border-radius:8px;">
        <h3>Create New File</h3>
        <form method="POST" action="{{ url_for('create_file', server_id=server.id) }}">
            <input type="hidden" name="current_subpath" value="{{ subpath }}">
            <div class="form-group">
                <label>File Name</label>
                <input type="text" name="filename" required>
            </div>
            <div style="display: flex; gap: 10px;">
                <button type="submit" class="btn btn-primary">Create</button>
                <button type="button" onclick="document.getElementById('createFileModal').style.display='none'" class="btn btn-secondary">Cancel</button>
            </div>
        </form>
    </div>
</div>

<div id="createFolderModal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.6); z-index:100;">
    <div style="background:#252538; max-width:400px; margin: 100px auto; padding:25px; border-radius:8px;">
        <h3>Create New Folder</h3>
        <form method="POST" action="{{ url_for('create_folder', server_id=server.id) }}">
            <input type="hidden" name="current_subpath" value="{{ subpath }}">
            <div class="form-group">
                <label>Folder Name</label>
                <input type="text" name="foldername" required>
            </div>
            <div style="display: flex; gap: 10px;">
                <button type="submit" class="btn btn-primary">Create</button>
                <button type="button" onclick="document.getElementById('createFolderModal').style.display='none'" class="btn btn-secondary">Cancel</button>
            </div>
        </form>
    </div>
</div>

<div id="renameModal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.6); z-index:100;">
    <div style="background:#252538; max-width:400px; margin: 100px auto; padding:25px; border-radius:8px;">
        <h3>Rename Item</h3>
        <form method="POST" action="{{ url_for('rename_file', server_id=server.id) }}">
            <input type="hidden" name="current_subpath" value="{{ subpath }}">
            <input type="hidden" name="old_filepath" id="renameOldPath">
            <div class="form-group">
                <label>New Name</label>
                <input type="text" name="new_name" id="renameNewName" required>
            </div>
            <div style="display: flex; gap: 10px;">
                <button type="submit" class="btn btn-primary">Rename</button>
                <button type="button" onclick="document.getElementById('renameModal').style.display='none'" class="btn btn-secondary">Cancel</button>
            </div>
        </form>
    </div>
</div>

<div id="uploadModal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.6); z-index:100;">
    <div style="background:#252538; max-width:400px; margin: 100px auto; padding:25px; border-radius:8px;">
        <h3>Upload Files</h3>
        <form method="POST" action="{{ url_for('upload_files', server_id=server.id) }}" enctype="multipart/form-data">
            <input type="hidden" name="current_subpath" value="{{ subpath }}">
            <div class="form-group">
                <label>Select Files</label>
                <input type="file" name="files" multiple required style="font-family: inherit;">
            </div>
            <div style="display: flex; gap: 10px;">
                <button type="submit" class="btn btn-success">Upload</button>
                <button type="button" onclick="document.getElementById('uploadModal').style.display='none'" class="btn btn-secondary">Cancel</button>
            </div>
        </form>
    </div>
</div>

<script>
function openRenameModal(path, name) {
    document.getElementById('renameOldPath').value = path;
    document.getElementById('renameNewName').value = name;
    document.getElementById('renameModal').style.display = 'block';
}
</script>
{% endif %}

{% if tab == 'edit_file' %}
<div class="panel-card">
    <h3>Editing File: <code>{{ filepath }}</code></h3>
    <form method="POST" action="{{ url_for('edit_file', server_id=server.id) }}">
        <input type="hidden" name="filepath" value="{{ filepath }}">
        <div class="form-group">
            <textarea name="file_content" rows="15" required>{{ file_content }}</textarea>
        </div>
        <div style="display: flex; gap: 10px;">
            <button type="submit" class="btn btn-primary" style="width: auto;">Save File</button>
            <a href="{{ url_for('server_files', server_id=server.id) }}" class="btn btn-secondary">Back to Files</a>
        </div>
    </form>
</div>
{% endif %}

{% if tab == 'startup' %}
<div class="panel-card">
    <h3>Startup Configuration</h3>
    <form method="POST" action="{{ url_for('server_startup', server_id=server.id) }}">
        <div class="form-group">
            <label>Docker Image</label>
            <input type="text" name="docker_image" value="{{ server.docker_image }}" required>
        </div>
        <div class="form-group">
            <label>Startup Command</label>
            <input type="text" name="startup_command" value="{{ server.startup_command }}" required>
        </div>
        <button type="submit" class="btn btn-primary" style="width: auto;">Save Startup Settings</button>
    </form>
</div>
{% endif %}
"""

ADMIN_HTML = """
<h2>Admin Area</h2>

<div class="admin-grid">
    <div class="admin-card">
        <h3>Create Node</h3>
        <form method="POST">
            <input type="hidden" name="action" value="add_node">
            <div class="form-group">
                <label>Node Name</label>
                <input type="text" name="node_name" required>
            </div>
            <div class="form-group">
                <label>Node IP Address</label>
                <input type="text" name="node_ip" value="127.0.0.1" required>
            </div>
            <button type="submit" class="btn btn-primary">Add Node</button>
        </form>
    </div>

    <div class="admin-card">
        <h3>Default Resource Settings</h3>
        <form method="POST">
            <input type="hidden" name="action" value="update_settings">
            <div class="form-group">
                <label>Default Memory (MB)</label>
                <input type="number" name="default_memory" value="{{ db.settings.default_memory }}" required>
            </div>
            <div class="form-group">
                <label>Default CPU (%)</label>
                <input type="number" name="default_cpu" value="{{ db.settings.default_cpu }}" required>
            </div>
            <div class="form-group">
                <label>Default Disk (MB)</label>
                <input type="number" name="default_disk" value="{{ db.settings.default_disk }}" required>
            </div>
            <button type="submit" class="btn btn-primary">Save Settings</button>
        </form>
    </div>
</div>

<div class="admin-card" style="margin-top: 20px;">
    <h3>Existing Nodes</h3>
    <ul>
        {% for node in db.nodes %}
            <li><strong>{{ node.name }}</strong> — {{ node.ip }}</li>
        {% else %}
            <p>No nodes added yet.</p>
        {% endfor %}
    </ul>
</div>
"""

# --- HELPER ROUTER RENDERER ---
def render_page(template_content, **kwargs):
    full_html = BASE_HTML.replace("CONTENT_PLACEHOLDER", template_content)
    return render_template_string(full_html, **kwargs)

# --- DATABASE LOGIC ---
def load_db():
    if not os.path.exists(DB_FILE):
        initial_data = {
            "users": [{"id": "1", "username": "admin", "password": "admin123", "is_admin": True, "server_ids": []}],
            "nodes": [],
            "servers": [],
            "settings": {"default_memory": 1024, "default_cpu": 100, "default_disk": 10240, "next_port": 8081}
        }
        save_db(initial_data)
    with open(DB_FILE, "r") as f:
        data = json.load(f)
        for user in data.get("users", []):
            if "server_ids" not in user:
                user["server_ids"] = [user.pop("server_id")] if user.get("server_id") else []
        return data

def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

# --- ROUTES ---
@app.before_request
def make_session_permanent():
    session.permanent = True

@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    db = load_db()
    if request.method == "POST":
        action = request.form.get("action")
        
        if action == "login":
            username = request.form.get("username")
            password = request.form.get("password")
            
            for user in db["users"]:
                if user["username"] == username and user["password"] == password:
                    session["user_id"] = user["id"]
                    session["username"] = user["username"]
                    session["is_admin"] = user["is_admin"]
                    flash("Logged in successfully.", "success")
                    return redirect(url_for("dashboard"))
            
            flash("Invalid username or password.", "danger")
            
        elif action == "register":
            username = request.form.get("reg_username")
            password = request.form.get("reg_password")
            node_id = request.form.get("node_id")
            
            if any(u["username"] == username for u in db["users"]):
                flash("Username already exists.", "danger")
                return redirect(url_for("login"))
            
            if not node_id and db["nodes"]:
                flash("Please select a valid node.", "danger")
                return redirect(url_for("login"))

            user_id = str(len(db["users"]) + 1)
            server_ids = []

            if db["nodes"]:
                assigned_port = db["settings"].get("next_port", 8081)
                db["settings"]["next_port"] = assigned_port + 1
                server_id = f"srv-{user_id}-{assigned_port}"
                server_ids.append(server_id)

                server_folder = os.path.join(SERVERS_DIR, server_id)
                os.makedirs(server_folder, exist_ok=True)
                main_py_path = os.path.join(server_folder, "main.py")
                if not os.path.exists(main_py_path):
                    with open(main_py_path, "w") as f:
                        f.write("import os\n"
                                "from http.server import HTTPServer, BaseHTTPRequestHandler\n\n"
                                "class HelloHandler(BaseHTTPRequestHandler):\n"
                                "    def do_GET(self):\n"
                                "        self.send_response(200)\n"
                                "        self.send_header('Content-type', 'text/html')\n"
                                "        self.end_headers()\n"
                                "        mem = os.environ.get('SERVER_MEMORY', 'Unknown')\n"
                                "        cpu = os.environ.get('SERVER_CPU', 'Unknown')\n"
                                "        disk = os.environ.get('SERVER_DISK', 'Unknown')\n"
                                "        html = f'<h1>hello python</h1><ul><li>Memory Limit: {mem}</li><li>CPU Limit: {cpu}</li><li>Disk Limit: {disk}</li></ul>'\n"
                                "        self.wfile.write(html.encode())\n\n"
                                "httpd = HTTPServer(('0.0.0.0', 8080), HelloHandler)\n"
                                "print('Server started on port 8080...')\n"
                                "httpd.serve_forever()\n")

                settings = db["settings"]
                new_server = {
                    "id": server_id,
                    "name": f"{username}'s Server",
                    "node_id": node_id,
                    "memory": settings["default_memory"],
                    "cpu": settings["default_cpu"],
                    "disk": settings["default_disk"],
                    "port": assigned_port,
                    "docker_image": "python:3.13",
                    "startup_command": "python main.py",
                    "status": "Offline",
                    "owner_id": user_id
                }
                db["servers"].append(new_server)

            new_user = {
                "id": user_id,
                "username": username,
                "password": password,
                "is_admin": False,
                "server_ids": server_ids
            }
            db["users"].append(new_user)
            save_db(db)
            
            flash("Account & unique server created successfully! You can now log in.", "success")
            return redirect(url_for("login"))
            
    return render_page(LOGIN_HTML, nodes=db["nodes"])

@app.route("/register")
def register():
    return redirect(url_for("login"))

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    db = load_db()
    user = next((u for u in db["users"] if u["id"] == session["user_id"]), None)
    servers = []
    if user and "server_ids" in user:
        servers = [s for s in db["servers"] if s["id"] in user["server_ids"]]
        
    return render_page(DASHBOARD_HTML, user=user, servers=servers)

@app.route("/server/create", methods=["POST"])
def create_server():
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    db = load_db()
    user = next((u for u in db["users"] if u["id"] == session["user_id"]), None)
    if not user:
        return redirect(url_for("dashboard"))
    
    if not db["nodes"]:
        flash("No nodes available to deploy a server. Ask an admin to create a node.", "danger")
        return redirect(url_for("dashboard"))

    assigned_port = db["settings"].get("next_port", 8081)
    db["settings"]["next_port"] = assigned_port + 1

    server_index = len(db["servers"]) + 1
    server_id = f"srv-{user['id']}-{server_index}-{assigned_port}"

    server_folder = os.path.join(SERVERS_DIR, server_id)
    os.makedirs(server_folder, exist_ok=True)
    main_py_path = os.path.join(server_folder, "main.py")
    if not os.path.exists(main_py_path):
        with open(main_py_path, "w") as f:
            f.write("import os\n"
                    "from http.server import HTTPServer, BaseHTTPRequestHandler\n\n"
                    "class HelloHandler(BaseHTTPRequestHandler):\n"
                    "    def do_GET(self):\n"
                    "        self.send_response(200)\n"
                    "        self.send_header('Content-type', 'text/html')\n"
                    "        self.end_headers()\n"
                    "        mem = os.environ.get('SERVER_MEMORY', 'Unknown')\n"
                    "        cpu = os.environ.get('SERVER_CPU', 'Unknown')\n"
                    "        disk = os.environ.get('SERVER_DISK', 'Unknown')\n"
                    "        html = f'<h1>hello python</h1><ul><li>Memory Limit: {mem}</li><li>CPU Limit: {cpu}</li><li>Disk Limit: {disk}</li></ul>'\n"
                    "        self.wfile.write(html.encode())\n\n"
                    "httpd = HTTPServer(('0.0.0.0', 8080), HelloHandler)\n"
                    "print('Server started on port 8080...')\n"
                    "httpd.serve_forever()\n")

    settings = db["settings"]
    new_server = {
        "id": server_id,
        "name": f"{user['username']}'s Server {len(user.get('server_ids', [])) + 1}",
        "node_id": db["nodes"][0]["id"],
        "memory": settings["default_memory"],
        "cpu": settings["default_cpu"],
        "disk": settings["default_disk"],
        "port": assigned_port,
        "docker_image": "python:3.13",
        "startup_command": "python main.py",
        "status": "Offline",
        "owner_id": user["id"]
    }
    db["servers"].append(new_server)
    if "server_ids" not in user:
        user["server_ids"] = []
    user["server_ids"].append(server_id)
    save_db(db)

    flash("New server created successfully!", "success")
    return redirect(url_for("dashboard"))

@app.route("/server/<server_id>/stats")
def server_stats(server_id):
    if "user_id" not in session:
        return jsonify({"online": False})
    if not docker_client:
        return jsonify({"online": False})
    
    try:
        container = docker_client.containers.get(server_id)
        stats = container.stats(stream=False)
        
        cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - stats['precpu_stats']['cpu_usage']['total_usage']
        system_delta = stats['cpu_stats']['system_cpu_usage'] - stats['precpu_stats']['system_cpu_usage']
        number_cpus = stats['cpu_stats'].get('online_cpus', 1)
        
        cpu_percent = 0.0
        if system_delta > 0 and cpu_delta > 0:
            cpu_percent = round((cpu_delta / system_delta) * number_cpus * 100.0, 2)
            
        mem_usage = stats['memory_stats']['usage']
        if 'stats' in stats['memory_stats']:
            mem_usage -= stats['memory_stats']['stats'].get('cache', 0)
        mem_mb = round(mem_usage / (1024 * 1024), 2)
        
        return jsonify({
            "online": True,
            "cpu_percent": cpu_percent,
            "memory_usage": mem_mb
        })
    except Exception:
        return jsonify({"online": False})

@app.route("/server/<server_id>/api/logs")
def server_logs_api(server_id):
    if "user_id" not in session:
        return "Unauthorized", 401
    if not docker_client:
        return "Docker service unavailable."
    try:
        container = docker_client.containers.get(server_id)
        logs = container.logs(tail=150).decode("utf-8", errors="ignore")
        return logs if logs else "Container is running, but no log output produced yet."
    except Exception:
        return "Container is offline. Click 'Start Container' to launch."

@app.route("/server/<server_id>/console")
def server_console(server_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    db = load_db()
    server = next((s for s in db["servers"] if s["id"] == server_id), None)
    if not server or (server["owner_id"] != session["user_id"] and not session.get("is_admin")):
        return redirect(url_for("dashboard"))
    return render_page(SERVER_MANAGEMENT_HTML, server=server, tab="console")

@app.route("/server/<server_id>/files")
def server_files(server_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    db = load_db()
    server = next((s for s in db["servers"] if s["id"] == server_id), None)
    if not server or (server["owner_id"] != session["user_id"] and not session.get("is_admin")):
        return redirect(url_for("dashboard"))

    base_path = os.path.join(SERVERS_DIR, server_id)
    subpath = request.args.get("subpath", "")
    
    target_dir = os.path.abspath(os.path.join(base_path, subpath))
    if not target_dir.startswith(base_path):
        target_dir = base_path
        subpath = ""

    folders = []
    files = []
    
    if os.path.exists(target_dir):
        for entry in sorted(os.listdir(target_dir)):
            full_entry_path = os.path.join(target_dir, entry)
            rel_path = os.path.relpath(full_entry_path, base_path)
            if os.path.isdir(full_entry_path):
                folders.append({"name": entry, "path": rel_path})
            else:
                files.append({"name": entry, "path": rel_path})

    parent_subpath = os.path.dirname(subpath) if subpath else ""

    return render_page(SERVER_MANAGEMENT_HTML, server=server, tab="files", folders=folders, files=files, subpath=subpath, parent_subpath=parent_subpath)

@app.route("/server/<server_id>/files/create_file", methods=["POST"])
def create_file(server_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    db = load_db()
    server = next((s for s in db["servers"] if s["id"] == server_id), None)
    if not server or (server["owner_id"] != session["user_id"] and not session.get("is_admin")):
        return redirect(url_for("dashboard"))

    subpath = request.form.get("current_subpath", "")
    filename = request.form.get("filename", "").strip()
    
    if filename:
        base_path = os.path.join(SERVERS_DIR, server_id)
        target_file = os.path.abspath(os.path.join(base_path, subpath, filename))
        if target_file.startswith(base_path):
            with open(target_file, "w") as f:
                f.write("")
            flash("File created successfully.", "success")
            return redirect(url_for('edit_file', server_id=server_id, filepath=os.path.relpath(target_file, base_path)))

    return redirect(url_for('server_files', server_id=server_id, subpath=subpath))

@app.route("/server/<server_id>/files/create_folder", methods=["POST"])
def create_folder(server_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    db = load_db()
    server = next((s for s in db["servers"] if s["id"] == server_id), None)
    if not server or (server["owner_id"] != session["user_id"] and not session.get("is_admin")):
        return redirect(url_for("dashboard"))

    subpath = request.form.get("current_subpath", "")
    foldername = request.form.get("foldername", "").strip()
    
    if foldername:
        base_path = os.path.join(SERVERS_DIR, server_id)
        target_dir = os.path.abspath(os.path.join(base_path, subpath, foldername))
        if target_dir.startswith(base_path):
            os.makedirs(target_dir, exist_ok=True)
            flash("Folder created successfully.", "success")

    return redirect(url_for('server_files', server_id=server_id, subpath=subpath))

@app.route("/server/<server_id>/files/rename", methods=["POST"])
def rename_file(server_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    db = load_db()
    server = next((s for s in db["servers"] if s["id"] == server_id), None)
    if not server or (server["owner_id"] != session["user_id"] and not session.get("is_admin")):
        return redirect(url_for("dashboard"))

    subpath = request.form.get("current_subpath", "")
    old_filepath = request.form.get("old_filepath", "")
    new_name = request.form.get("new_name", "").strip()

    base_path = os.path.join(SERVERS_DIR, server_id)
    old_full_path = os.path.abspath(os.path.join(base_path, old_filepath))

    if old_full_path.startswith(base_path) and old_full_path != base_path and new_name:
        parent_dir = os.path.dirname(old_full_path)
        new_full_path = os.path.abspath(os.path.join(parent_dir, new_name))
        if new_full_path.startswith(base_path):
            os.rename(old_full_path, new_full_path)
            flash("Renamed successfully.", "success")

    return redirect(url_for('server_files', server_id=server_id, subpath=subpath))

@app.route("/server/<server_id>/files/upload", methods=["POST"])
def upload_files(server_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    db = load_db()
    server = next((s for s in db["servers"] if s["id"] == server_id), None)
    if not server or (server["owner_id"] != session["user_id"] and not session.get("is_admin")):
        return redirect(url_for("dashboard"))

    subpath = request.form.get("current_subpath", "")
    base_path = os.path.join(SERVERS_DIR, server_id)
    target_dir = os.path.abspath(os.path.join(base_path, subpath))
    
    if target_dir.startswith(base_path):
        uploaded_files = request.files.getlist("files")
        for file in uploaded_files:
            if file.filename:
                file.save(os.path.join(target_dir, file.filename))
        flash("Files uploaded successfully.", "success")

    return redirect(url_for('server_files', server_id=server_id, subpath=subpath))

@app.route("/server/<server_id>/files/delete", methods=["POST"])
def delete_file(server_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    db = load_db()
    server = next((s for s in db["servers"] if s["id"] == server_id), None)
    if not server or (server["owner_id"] != session["user_id"] and not session.get("is_admin")):
        return redirect(url_for("dashboard"))

    subpath = request.form.get("current_subpath", "")
    filepath = request.form.get("filepath", "")
    base_path = os.path.join(SERVERS_DIR, server_id)
    target_path = os.path.abspath(os.path.join(base_path, filepath))

    if target_path.startswith(base_path) and target_path != base_path:
        if os.path.isdir(target_path):
            shutil.rmtree(target_path)
        elif os.path.isfile(target_path):
            os.remove(target_path)
        flash("Deleted successfully.", "success")

    return redirect(url_for('server_files', server_id=server_id, subpath=subpath))

@app.route("/server/<server_id>/files/edit", methods=["GET", "POST"])
def edit_file(server_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    db = load_db()
    server = next((s for s in db["servers"] if s["id"] == server_id), None)
    if not server or (server["owner_id"] != session["user_id"] and not session.get("is_admin")):
        return redirect(url_for("dashboard"))

    base_path = os.path.join(SERVERS_DIR, server_id)

    if request.method == "POST":
        filepath = request.form.get("filepath", "")
        content = request.form.get("file_content", "")
        target_file = os.path.abspath(os.path.join(base_path, filepath))
        if target_file.startswith(base_path):
            with open(target_file, "w") as f:
                f.write(content)
            flash("File updated successfully.", "success")
        return redirect(url_for('server_files', server_id=server_id))

    filepath = request.args.get("filepath", "")
    target_file = os.path.abspath(os.path.join(base_path, filepath))
    file_content = ""
    
    if target_file.startswith(base_path) and os.path.exists(target_file) and os.path.isfile(target_file):
        with open(target_file, "r") as f:
            file_content = f.read()

    return render_page(SERVER_MANAGEMENT_HTML, server=server, tab="edit_file", filepath=filepath, file_content=file_content)

@app.route("/server/<server_id>/startup", methods=["GET", "POST"])
def server_startup(server_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    db = load_db()
    server = next((s for s in db["servers"] if s["id"] == server_id), None)
    if not server or (server["owner_id"] != session["user_id"] and not session.get("is_admin")):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        server["docker_image"] = request.form.get("docker_image", "python:3.13")
        server["startup_command"] = request.form.get("startup_command", "python main.py")
        save_db(db)
        flash("Startup configuration updated.", "success")
        return redirect(url_for('server_startup', server_id=server_id))

    return render_page(SERVER_MANAGEMENT_HTML, server=server, tab="startup")

@app.route("/server/<server_id>/action/<action>")
def server_action(server_id, action):
    if "user_id" not in session:
        return redirect(url_for("login"))
        
    db = load_db()
    server = next((s for s in db["servers"] if s["id"] == server_id), None)
    
    if server and (server["owner_id"] == session["user_id"] or session.get("is_admin")):
        if not docker_client:
            flash("Docker daemon is not running or accessible.", "danger")
            return redirect(url_for("server_console", server_id=server_id))

        try:
            try:
                container = docker_client.containers.get(server_id)
                container.stop()
                container.remove()
            except Exception:
                pass

            if action in ["start", "restart"]:
                server_folder = os.path.join(SERVERS_DIR, server_id)
                req_path = os.path.join(server_folder, "requirements.txt")
                
                if os.path.exists(req_path):
                    actual_command = f"sh -c 'if [ -f requirements.txt ]; then pip install --user --no-cache-dir -r requirements.txt; fi && {server['startup_command']}'"
                else:
                    actual_command = server["startup_command"]

                container_env = {
                    "HOME": "/app",
                    "SERVER_MEMORY": f"{server['memory']} MB",
                    "SERVER_CPU": f"{server['cpu']}%",
                    "SERVER_DISK": f"{server['disk']} MB"
                }

                docker_client.containers.run(
                    image=server["docker_image"],
                    command=actual_command,
                    detach=True,
                    name=server_id,
                    ports={f"8080/tcp": server["port"]},
                    volumes={server_folder: {"bind": "/app", "mode": "rw"}},
                    environment=container_env,
                    working_dir="/app",
                    mem_limit=f"{server['memory']}m"
                )
                server["status"] = "Online"
                flash(f"Container started! Check console logs below.", "success")
            elif action == "stop":
                server["status"] = "Offline"
                flash("Container stopped successfully.", "success")

            save_db(db)
        except Exception as e:
            flash(f"Docker Error: {str(e)}", "danger")
            
    return redirect(url_for("server_console", server_id=server_id))

@app.route("/admin", methods=["GET", "POST"])
def admin_panel():
    if not session.get("is_admin"):
        flash("Unauthorized access.", "danger")
        return redirect(url_for("dashboard"))
        
    db = load_db()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add_node":
            node_name = request.form.get("node_name")
            node_ip = request.form.get("node_ip")
            if node_name and node_ip:
                new_node = {
                    "id": str(len(db["nodes"]) + 1),
                    "name": node_name,
                    "ip": node_ip
                }
                db["nodes"].append(new_node)
                save_db(db)
                flash("Node added successfully.", "success")
        elif action == "update_settings":
            db["settings"]["default_memory"] = int(request.form.get("default_memory", 1024))
            db["settings"]["default_cpu"] = int(request.form.get("default_cpu", 100))
            db["settings"]["default_disk"] = int(request.form.get("default_disk", 10240))
            save_db(db)
            flash("Default allocation settings updated.", "success")
            
        return redirect(url_for("admin_panel"))
        
    return render_page(ADMIN_HTML, db=db)

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("login"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
