#!/usr/bin/env python3
"""Brute-force auto-responder.

Tails the application log, and when a single source IP produces too many
failed logins within a short window, adds it to the blocklist file that the
app reads to enforce a ban (HTTP 403 on all subsequent requests).
"""
import time, os, re, collections

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "app", "logs", "app.log")
BLOCKLIST = os.path.join(HERE, "app", "logs", "blocklist.txt")

THRESHOLD = 5      # number of failed logins...
WINDOW = 10        # ...within this many seconds triggers a ban

fails = collections.defaultdict(collections.deque)
banned = set()

# Load any bans that already exist so we don't duplicate
if os.path.exists(BLOCKLIST):
    with open(BLOCKLIST) as f:
        banned = {ln.strip() for ln in f if ln.strip()}

FAILED = re.compile(r"LOGIN_FAILED ip=([0-9.]+)")

def ban(ip):
    banned.add(ip)
    with open(BLOCKLIST, "a") as f:
        f.write(ip + "\n")
    print(f"[RESPONSE] {time.strftime('%H:%M:%S')} *** BANNED {ip} *** "
          f"({THRESHOLD}+ failed logins in {WINDOW}s)")

print(f"[*] Auto-responder started. Watching {LOG}")
print(f"[*] Detection rule: >= {THRESHOLD} failed logins from one IP within {WINDOW}s -> ban")
print(f"[*] Bans written to {BLOCKLIST}\n")

with open(LOG) as f:
    f.seek(0, 2)  # jump to end; only watch new lines
    while True:
        line = f.readline()
        if not line:
            time.sleep(0.3)
            continue
        m = FAILED.search(line)
        if not m:
            continue
        ip = m.group(1)
        if ip in banned:
            continue
        now = time.time()
        dq = fails[ip]
        dq.append(now)
        while dq and now - dq[0] > WINDOW:   # drop events outside the window
            dq.popleft()
        if len(dq) >= THRESHOLD:
            ban(ip)