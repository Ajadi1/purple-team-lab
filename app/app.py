from flask import Flask, request, render_template, redirect, session
import sqlite3, logging, os, subprocess

app = Flask(__name__)
app.secret_key = "dev-secret-not-for-prod"

BASE = os.path.dirname(__file__)
LOG_DIR = os.path.join(BASE, "logs")
UPLOAD_DIR = os.path.join(BASE, "uploads")
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

BLOCKLIST_FILE = os.path.join(LOG_DIR, "blocklist.txt")

logging.basicConfig(
    filename=os.path.join(LOG_DIR, "app.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

DB = os.path.join(BASE, "users.db")


def get_client_ip():
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.headers.get("X-Real-IP", request.remote_addr)


def is_blocked(ip):
    try:
        with open(BLOCKLIST_FILE) as f:
            return ip in {line.strip() for line in f if line.strip()}
    except FileNotFoundError:
        return False


@app.before_request
def enforce_blocklist():
    ip = get_client_ip()
    if is_blocked(ip):
        logging.warning(f"BLOCKED_REQUEST ip={ip} path={request.path!r}")
        return "Forbidden: your address has been blocked by automated response.", 403


def get_role(username):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT role FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else "user"


@app.route("/")
def index():
    return redirect("/login")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        ip = get_client_ip()

        conn = sqlite3.connect(DB)
        cur = conn.cursor()
        query = f"SELECT * FROM users WHERE username = '{username}' AND password = '{password}'"
        logging.info(f"LOGIN_ATTEMPT ip={ip} username={username!r} query={query!r}")
        try:
            cur.execute(query)
            row = cur.fetchone()
        except Exception as e:
            logging.error(f"LOGIN_ERROR ip={ip} error={e}")
            row = None
        conn.close()

        if row:
            session["user"] = username
            logging.info(f"LOGIN_SUCCESS ip={ip} username={username!r}")
            return redirect("/dashboard")
        logging.warning(f"LOGIN_FAILED ip={ip} username={username!r}")
        return render_template("login.html", error="Invalid credentials")

    return render_template("login.html", error=None)


@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/login")
    user = session["user"]
    return render_template("dashboard.html", user=user, role=get_role(user),
                           upload_msg=None, ping_output=None)


@app.route("/upload", methods=["POST"])
def upload():
    if "user" not in session:
        return redirect("/login")
    user = session["user"]
    ip = get_client_ip()
    f = request.files.get("file")
    if f and f.filename:
        dest = os.path.join(UPLOAD_DIR, f.filename)
        f.save(dest)
        logging.warning(f"FILE_UPLOAD ip={ip} user={user!r} filename={f.filename!r}")
        msg = f"Uploaded {f.filename}"
    else:
        msg = "No file selected"
    return render_template("dashboard.html", user=user, role=get_role(user),
                           upload_msg=msg, ping_output=None)


@app.route("/ping", methods=["POST"])
def ping():
    if "user" not in session:
        return redirect("/login")
    user = session["user"]
    ip = get_client_ip()
    host = request.form.get("host", "")
    cmd = f"ping -c 2 {host}"
    logging.warning(f"PING_EXEC ip={ip} user={user!r} cmd={cmd!r}")
    try:
        output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, timeout=10).decode()
    except Exception as e:
        output = f"Error: {e}"
    return render_template("dashboard.html", user=user, role=get_role(user),
                           upload_msg=None, ping_output=output)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)