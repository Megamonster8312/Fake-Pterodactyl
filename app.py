import os
import json
from flask import Flask, render_template_string, request, redirect, url_for, session, flash, jsonify
from datetime import timedelta

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "super_secret_standalone_key")
app.permanent_session_lifetime = timedelta(days=30)

# Cookie isolation settings
app.config['SESSION_COOKIE_NAME'] = 'standalone_panel_session'
app.config['SESSION_COOKIE_PATH'] = '/'

DB_FILE = "data.json"

# --- EMBEDDED HTML TEMPLATES & CSS ---

BASE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Standalone Cloud Panel</title>
    <style>
        body { background-color: #1e1e2f; color: #cfd8dc; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 0; }
        .navbar { background-color: #151522; display: flex; justify-content: space-between; padding: 15px 30px; border-bottom: 1px solid #2a2a40; }
        .nav-brand { font-weight: bold; font-size: 1.2rem; color: #3b82f6; text-transform: uppercase; }
        .nav-links a { color: #94a3b8; text-decoration: none; margin-left: 20px; }
        .nav-links a:hover { color: #ffffff; }
        .container { max-width: 1050px; margin: 40px auto; padding: 0 20px; }
        .auth-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 25px; }
        .auth-card, .admin-card, .server-card { background-color: #252538; padding: 25px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); margin-bottom: 20px; }
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; margin-bottom: 5px; color: #94a3b8; }
        .form-group input, .form-group select, .form-group textarea { width: 100%; padding: 10px; background-color: #1e1e2f; border: 1px solid #33334d; border-radius: 4px; color: white; box-sizing: border-box; font-family: monospace; }
        .btn { padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; text-decoration: none; display: inline-block; text-align: center; }
        .btn-primary { background-color: #2563eb; color: white; width: 100%; box-sizing: border-box; }
        .btn-primary:hover { background-color: #1d4ed8; }
        .btn-success { background-color: #16a34a; color: white; }
        .server-info { display: flex; justify-content: space-between; align-items: center; }
        .server-specs { margin: 15px 0; display: flex; gap: 20px; color: #94a3b8; font-size: 0.9rem; flex-wrap: wrap; }
        .badge { padding: 4px 8px; border-radius: 4px; font-size: 0.85rem; }
        .status-online { background-color: #14532d; color: #4ade80; }
        .alert { padding: 12px; border-radius: 4px; margin-bottom: 20px; }
        .alert-success { background-color: #14532d; color: #4ade80; }
        .alert-danger { background-color: #7f1d1d; color: #f87171; }
        .alert-info { background-color: #1e3a8a; color: #93c5fd; }
    </style>
</head>
<body>
    <nav class="navbar">
        <div class="nav-brand">Standalone Cloud Panel</div>
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
            <button type="submit" class="btn btn-primary" style="background-color: #16a34a;">Register Account</button>
        </form>
    </div>
</div>
"""

DASHBOARD_HTML = """
<div class="dashboard-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px;">
    <div>
        <h1>Welcome, {{ user.username }}</h1>
        <p>Manage your standalone instances and workspace below.</p>
    </div>
    <form method="POST" action="{{ url_for('create_server') }}">
        <button type="submit" class="btn btn-success">+ Create New Instance</button>
    </form>
</div>

{% if servers %}
    {% for server in servers %}
    <div class="server-card">
        <div class="server-info">
            <h3>{{ server.name }}</h3>
            <span class="badge status-online">Running Standalone</span>
        </div>
        <div class="server-specs">
            <span>Instance ID: <strong>{{ server.id }}</strong></span>
            <span>Created: <strong>Active Cloud Node</strong></span>
        </div>
    </div>
    {% endfor %}
{% else %}
<div class="alert alert-info">
    You do not have any instances created yet. Click the button above to spin one up instantly!
</div>
{% endif %}
"""

ADMIN_HTML = """
<h2>Admin Area - Standalone System</h2>
<div class="admin-card">
    <h3>System Status</h3>
    <p>Database Engine: <code>Local JSON Store (data.json)</code></p>
    <p>Hosting Mode: <code>Render Cloud 24/7</code></p>
</div>
"""

def render_page(template_content, **kwargs):
    full_html = BASE_HTML.replace("CONTENT_PLACEHOLDER", template_content)
    return render_template_string(full_html, **kwargs)

def load_db():
    if not os.path.exists(DB_FILE):
        initial_data = {
            "users": [{"id": "1", "username": "admin", "password": "admin123", "is_admin": True, "servers": []}],
        }
        save_db(initial_data)
    with open(DB_FILE, "r") as f:
        return json.load(f)

def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

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
            if any(u["username"] == username for u in db["users"]):
                flash("Username already exists.", "danger")
                return redirect(url_for("login"))
            
            new_user = {
                "id": str(len(db["users"]) + 1),
                "username": username,
                "password": password,
                "is_admin": False,
                "servers": []
            }
            db["users"].append(new_user)
            save_db(db)
            flash("Account created successfully! You can now log in.", "success")
            return redirect(url_for("login"))
    return render_page(LOGIN_HTML)

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))
    db = load_db()
    user = next((u for u in db["users"] if u["id"] == session["user_id"]), None)
    return render_page(DASHBOARD_HTML, user=user, servers=user.get("servers", []))

@app.route("/server/create", methods=["POST"])
def create_server():
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    db = load_db()
    user = next((u for u in db["users"] if u["id"] == session["user_id"]), None)
    
    new_server = {
        "id": str(len(user.get("servers", [])) + 1000),
        "name": f"{user['username']}'s Cloud Instance"
    }
    user["servers"].append(new_server)
    save_db(db)
    flash("New cloud instance created successfully!", "success")
    
    return redirect(url_for("dashboard"))

@app.route("/admin")
def admin_panel():
    if not session.get("is_admin"):
        flash("Unauthorized access.", "danger")
        return redirect(url_for("dashboard"))
    return render_page(ADMIN_HTML)

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged in successfully.", "info")
    return redirect(url_for("login"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
