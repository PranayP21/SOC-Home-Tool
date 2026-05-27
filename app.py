import os
import re
import time
import socket
import subprocess
import smtplib
import imaplib
import email
from email.header import decode_header
from email.message import EmailMessage
from datetime import datetime, timedelta, timezone

import psutil
import yaml
import requests
from PIL import Image, ImageDraw, ImageFont

from waveshare_epd import epd2in13_V4 as epd_driver


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.path.join(BASE_DIR, "data")
ALERTS_DIR = os.path.join(BASE_DIR, "alerts")
LOGS_DIR = os.path.join(BASE_DIR, "logs")

KNOWN_DEVICES_FILE = os.path.join(DATA_DIR, "known_devices.txt")
SEEN_ACCOUNT_ALERTS_FILE = os.path.join(DATA_DIR, "seen_account_alerts.txt")
ACCOUNT_CACHE_FILE = os.path.join(DATA_DIR, "account_alert_cache.yaml")
CALENDAR_CACHE_FILE = os.path.join(DATA_DIR, "calendar_cache.yaml")
WEATHER_CACHE_FILE = os.path.join(DATA_DIR, "weather_cache.yaml")


def ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(ALERTS_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)

    for path in [KNOWN_DEVICES_FILE, SEEN_ACCOUNT_ALERTS_FILE]:
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                f.write("")


def log(message):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{now}] {message}"
    print(line)

    try:
        with open(os.path.join(LOGS_DIR, "app.log"), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def load_yaml_file(filename, default=None):
    path = os.path.join(BASE_DIR, filename)

    if not os.path.exists(path):
        return default

    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or default
    except Exception as e:
        log(f"Failed to load {filename}: {e}")
        return default


def save_yaml_path(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f)
    except Exception as e:
        log(f"Failed to save YAML {path}: {e}")


def load_config():
    return load_yaml_file("config.yaml", {})


def load_email_config():
    return load_yaml_file("email_config.yaml", {})


def load_account_monitor_config():
    return load_yaml_file("account_monitor.yaml", {})


def load_personal_dashboard_config():
    return load_yaml_file("personal_dashboard.yaml", {})


def alert_state_file(alert_key):
    safe_name = alert_key.replace(" ", "_").replace("/", "_").replace("\\", "_").lower()
    return os.path.join(ALERTS_DIR, f"{safe_name}.txt")


def can_send_alert(alert_key, cooldown_minutes):
    path = alert_state_file(alert_key)

    if not os.path.exists(path):
        return True

    try:
        with open(path, "r", encoding="utf-8") as f:
            last_sent = float(f.read().strip())

        elapsed_minutes = (time.time() - last_sent) / 60
        return elapsed_minutes >= cooldown_minutes
    except Exception:
        return True


def mark_alert_sent(alert_key):
    ensure_dirs()
    with open(alert_state_file(alert_key), "w", encoding="utf-8") as f:
        f.write(str(time.time()))


def send_email_alert(subject, body, alert_key="general"):
    email_config = load_email_config()
    settings = email_config.get("email", {})

    if not settings.get("enabled", False):
        log("Email alerts disabled.")
        return False

    try:
        cooldown_minutes = int(settings.get("cooldown_minutes", 30))

        if not can_send_alert(alert_key, cooldown_minutes):
            log(f"Alert cooldown active for: {alert_key}")
            return False

        sender_email = settings["sender_email"]
        sender_password = settings["sender_password"]
        recipient_email = settings["recipient_email"]
        smtp_server = settings.get("smtp_server", "smtp.gmail.com")
        smtp_port = int(settings.get("smtp_port", 587))

        if "your_" in sender_email.lower() or "your_" in sender_password.lower() or "your_" in recipient_email.lower():
            log("Email config has placeholder values. Skipping alert.")
            return False

        msg = EmailMessage()
        msg["From"] = sender_email
        msg["To"] = recipient_email
        msg["Subject"] = subject
        msg.set_content(body)

        with smtplib.SMTP(smtp_server, smtp_port, timeout=20) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)

        mark_alert_sent(alert_key)
        log(f"Email alert sent: {subject}")
        return True
    except Exception as e:
        log(f"Failed to send email alert: {e}")
        return False


def ping_host(host):
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", "2", host],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode == 0
    except Exception:
        return False


def dns_ok(domain):
    try:
        socket.gethostbyname(domain)
        return True
    except Exception:
        return False


def get_pi_temp():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r", encoding="utf-8") as f:
            temp_raw = int(f.read().strip())
        return round(temp_raw / 1000, 1)
    except Exception:
        return "N/A"


def get_uptime():
    seconds = int(time.time() - psutil.boot_time())
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    return f"{days}d {hours}h"


def get_wifi_strength():
    try:
        result = subprocess.check_output(["iwconfig"], stderr=subprocess.DEVNULL, timeout=5).decode()
        for line in result.splitlines():
            if "Signal level" in line:
                return line.split("Signal level=")[1].split(" ")[0]
    except Exception:
        pass
    return "N/A"


def read_tasks(limit=2):
    config = load_config()
    task_file = os.path.join(BASE_DIR, config.get("tasks", {}).get("file", "tasks.txt"))

    if not os.path.exists(task_file):
        return []

    with open(task_file, "r", encoding="utf-8") as f:
        tasks = [line.strip() for line in f.readlines() if line.strip()]

    return tasks[:limit]


def load_known_devices():
    ensure_dirs()
    known = set()
    with open(KNOWN_DEVICES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip().lower()
            if line and not line.startswith("#"):
                known.add(line.split()[0])
    return known


def save_known_device(mac, ip="unknown", vendor="unknown"):
    ensure_dirs()
    with open(KNOWN_DEVICES_FILE, "a", encoding="utf-8") as f:
        f.write(f"{mac.lower()} {ip} {vendor}\n")


def scan_devices():
    config = load_config()
    device_config = config.get("device_scan", {})

    if not device_config.get("enabled", False):
        return []

    interface = device_config.get("interface", "wlan0")

    try:
        result = subprocess.check_output(
            ["sudo", "-n", "/usr/bin/arp-scan", f"--interface={interface}", "--localnet"],
            stderr=subprocess.DEVNULL,
            timeout=45,
        ).decode(errors="ignore")
    except Exception as e:
        log(f"Device scan failed: {e}")
        return []

    devices = []
    for line in result.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            ip = parts[0]
            mac = parts[1].lower()
            if re.match(r"^\d+\.\d+\.\d+\.\d+$", ip) and ":" in mac:
                vendor = " ".join(parts[2:]) if len(parts) > 2 else "Unknown"
                devices.append({"ip": ip, "mac": mac, "vendor": vendor})
    return devices


def detect_unknown_devices():
    devices = scan_devices()
    known = load_known_devices()

    if len(known) == 0 and len(devices) > 0:
        log("First device scan: learning current devices as trusted.")
        for device in devices:
            save_known_device(device["mac"], device["ip"], device["vendor"])
        return []

    unknown = []
    for device in devices:
        if device["mac"] not in known:
            unknown.append(device)
            save_known_device(device["mac"], device["ip"], device["vendor"])
    return unknown


def send_unknown_device_alert(unknown_devices):
    if not unknown_devices:
        return

    lines = [f"- IP: {d['ip']} | MAC: {d['mac']} | Vendor: {d['vendor']}" for d in unknown_devices]
    body = f"""
Mini SOC has detected new device(s) on your network.

New device count: {len(unknown_devices)}

Devices:
{chr(10).join(lines)}

Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Recommended checks:
- Confirm whether this is one of your own devices.
- Check your router connected devices list.
- If unknown, consider changing your Wi-Fi password.
- Review router admin access and Wi-Fi security.
"""

    send_email_alert(
        subject=f"Mini SOC Alert - {len(unknown_devices)} Unknown Network Device(s)",
        body=body,
        alert_key="unknown_network_device",
    )


def decode_email_header(value):
    if not value:
        return ""
    decoded_parts = decode_header(value)
    result = ""
    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            try:
                result += part.decode(encoding or "utf-8", errors="ignore")
            except Exception:
                result += part.decode("utf-8", errors="ignore")
        else:
            result += part
    return result


def load_seen_account_alerts():
    ensure_dirs()
    seen = set()
    with open(SEEN_ACCOUNT_ALERTS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                seen.add(line)
    return seen


def save_seen_account_alert(message_key):
    ensure_dirs()
    with open(SEEN_ACCOUNT_ALERTS_FILE, "a", encoding="utf-8") as f:
        f.write(f"{message_key}\n")


def email_matches_keywords(subject, sender, keywords):
    combined = f"{subject} {sender}".lower()
    return any(keyword.lower() in combined for keyword in keywords)


def load_account_cache():
    ensure_dirs()
    if not os.path.exists(ACCOUNT_CACHE_FILE):
        cache = {"last_scan_time": 0, "last_alert_count": 0, "last_alerts": []}
        save_yaml_path(ACCOUNT_CACHE_FILE, cache)
        return cache

    try:
        with open(ACCOUNT_CACHE_FILE, "r", encoding="utf-8") as f:
            cache = yaml.safe_load(f) or {}
        return {
            "last_scan_time": cache.get("last_scan_time", 0),
            "last_alert_count": cache.get("last_alert_count", 0),
            "last_alerts": cache.get("last_alerts", []),
        }
    except Exception:
        return {"last_scan_time": 0, "last_alert_count": 0, "last_alerts": []}


def save_account_cache(cache):
    save_yaml_path(ACCOUNT_CACHE_FILE, cache)


def scan_account_mailbox(mailbox, keywords, search_days, timeout_seconds):
    alerts = []
    name = mailbox.get("name", "Mailbox")
    imap_server = mailbox["imap_server"]
    imap_port = int(mailbox.get("imap_port", 993))
    mailbox_email = mailbox["mailbox_email"]
    mailbox_password = mailbox["mailbox_password"]

    if "your_" in mailbox_email.lower() or "your_" in mailbox_password.lower() or "app_password" in mailbox_password.lower():
        log(f"Skipping {name}: placeholder value still present.")
        return alerts

    try:
        mail = imaplib.IMAP4_SSL(imap_server, imap_port, timeout=timeout_seconds)
        mail.login(mailbox_email, mailbox_password)
        mail.select("INBOX")
        since_date = (datetime.now() - timedelta(days=search_days)).strftime("%d-%b-%Y")
        status, data = mail.search(None, f'(SINCE "{since_date}")')

        if status != "OK":
            log(f"{name}: IMAP search failed.")
            mail.logout()
            return alerts

        message_ids = data[0].split()
        for msg_id in message_ids[-30:]:
            status, msg_data = mail.fetch(msg_id, "(RFC822)")
            if status != "OK":
                continue

            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)
            subject = decode_email_header(msg.get("Subject", ""))
            sender = decode_email_header(msg.get("From", ""))
            date = decode_email_header(msg.get("Date", ""))
            message_id = msg.get("Message-ID", f"{name}-{msg_id.decode(errors='ignore')}")
            unique_key = f"{name}|{message_id}"

            if email_matches_keywords(subject, sender, keywords):
                alerts.append({"mailbox": name, "from": sender, "subject": subject, "date": date, "key": unique_key})

        mail.logout()
    except Exception as e:
        log(f"Account monitor failed for {name}: {e}")
    return alerts


def scan_account_alerts_cached():
    account_config = load_account_monitor_config()
    settings = account_config.get("account_monitor", {})

    if not settings.get("enabled", False):
        return [], False

    cache = load_account_cache()
    interval = int(settings.get("scan_interval_minutes", 30))
    last_scan = float(cache.get("last_scan_time", 0))
    elapsed = (time.time() - last_scan) / 60

    if elapsed < interval:
        log("Account monitor: using cached result.")
        return cache.get("last_alerts", []), True

    log("Account monitor: scan due, checking mailboxes.")
    mailboxes = settings.get("mailboxes", [])
    keywords = settings.get("suspicious_keywords", [])
    search_days = int(settings.get("search_days", 2))
    timeout_seconds = int(settings.get("imap_timeout_seconds", 15))
    seen = load_seen_account_alerts()
    new_alerts = []

    for mailbox in mailboxes:
        for alert in scan_account_mailbox(mailbox, keywords, search_days, timeout_seconds):
            if alert["key"] not in seen:
                new_alerts.append(alert)
                save_seen_account_alert(alert["key"])

    cache = {"last_scan_time": time.time(), "last_alert_count": len(new_alerts), "last_alerts": new_alerts}
    save_account_cache(cache)
    return new_alerts, False


def send_account_alert_summary(account_alerts):
    if not account_alerts:
        return

    lines = []
    for alert in account_alerts:
        lines.append(
            f"- Mailbox: {alert['mailbox']}\n"
            f"  From: {alert['from']}\n"
            f"  Subject: {alert['subject']}\n"
            f"  Date: {alert['date']}\n"
        )

    body = f"""
Mini SOC has detected account security related email(s).

New account alert count: {len(account_alerts)}

Alerts:
{chr(10).join(lines)}

Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Recommended checks:
- Do not click links directly from suspicious emails.
- Open the service website manually.
- Review recent sign-in activity.
- Check MFA, recovery email, and connected apps.
"""

    send_email_alert(
        subject=f"Mini SOC Alert - {len(account_alerts)} Account Security Email(s)",
        body=body,
        alert_key="account_security_email",
    )


def load_weather_cache():
    if not os.path.exists(WEATHER_CACHE_FILE):
        cache = {"last_scan_time": 0, "weather": {}}
        save_yaml_path(WEATHER_CACHE_FILE, cache)
        return cache
    try:
        with open(WEATHER_CACHE_FILE, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {"last_scan_time": 0, "weather": {}}
    except Exception:
        return {"last_scan_time": 0, "weather": {}}


def get_weather():
    personal = load_personal_dashboard_config()
    weather_cfg = personal.get("personal_dashboard", {}).get("weather", {})

    if not weather_cfg.get("enabled", False):
        return {"summary": "Weather off", "detail": ""}

    cache = load_weather_cache()
    cache_minutes = int(weather_cfg.get("cache_minutes", 30))
    elapsed = (time.time() - float(cache.get("last_scan_time", 0))) / 60

    if elapsed < cache_minutes and cache.get("weather"):
        return cache["weather"]

    try:
        lat = weather_cfg.get("latitude", 51.5072)
        lon = weather_cfg.get("longitude", -0.1276)
        location = weather_cfg.get("location_name", "Local")
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        current = data.get("current_weather", {})
        temp = current.get("temperature", "N/A")
        wind = current.get("windspeed", "N/A")
        weather = {"summary": f"{location}: {temp}C", "detail": f"Wind {wind} km/h"}
        save_yaml_path(WEATHER_CACHE_FILE, {"last_scan_time": time.time(), "weather": weather})
        return weather
    except Exception as e:
        log(f"Weather failed: {e}")
        return cache.get("weather", {"summary": "Weather N/A", "detail": ""})


def unfold_ics_lines(text):
    lines = text.splitlines()
    unfolded = []
    for line in lines:
        if line.startswith(" ") or line.startswith("\t"):
            if unfolded:
                unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
    return unfolded


def parse_ics_datetime(value):
    value = value.strip()
    try:
        if value.endswith("Z"):
            return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).astimezone().replace(tzinfo=None)
        if "T" in value:
            return datetime.strptime(value[:15], "%Y%m%dT%H%M%S")
        return datetime.strptime(value[:8], "%Y%m%d")
    except Exception:
        return None


def clean_ics_text(value):
    return value.replace("\\n", " ").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\").strip()


def load_calendar_cache():
    if not os.path.exists(CALENDAR_CACHE_FILE):
        cache = {"last_scan_time": 0, "events": []}
        save_yaml_path(CALENDAR_CACHE_FILE, cache)
        return cache
    try:
        with open(CALENDAR_CACHE_FILE, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {"last_scan_time": 0, "events": []}
    except Exception:
        return {"last_scan_time": 0, "events": []}


def fetch_calendar_events():
    personal = load_personal_dashboard_config()
    cal_cfg = personal.get("personal_dashboard", {}).get("calendar", {})

    if not cal_cfg.get("enabled", False):
        return []

    ics_url = cal_cfg.get("ics_url", "")
    if not ics_url or "PASTE_" in ics_url:
        return []

    cache = load_calendar_cache()
    cache_minutes = int(cal_cfg.get("cache_minutes", 30))
    elapsed = (time.time() - float(cache.get("last_scan_time", 0))) / 60

    if elapsed < cache_minutes:
        return cache.get("events", [])

    try:
        response = requests.get(ics_url, timeout=15)
        response.raise_for_status()
        lines = unfold_ics_lines(response.text)
        events = []
        in_event = False
        current = {}

        for line in lines:
            if line == "BEGIN:VEVENT":
                in_event = True
                current = {}
            elif line == "END:VEVENT":
                in_event = False
                summary = current.get("SUMMARY", "Event")
                dtstart = current.get("DTSTART")
                if dtstart:
                    start = parse_ics_datetime(dtstart)
                    if start:
                        events.append({"summary": clean_ics_text(summary), "start": start.isoformat()})
                current = {}
            elif in_event and ":" in line:
                key, value = line.split(":", 1)
                current[key.split(";")[0]] = value

        now = datetime.now()
        end = now + timedelta(days=int(cal_cfg.get("days_ahead", 7)))
        max_events = int(cal_cfg.get("max_events", 3))
        upcoming = [event for event in events if now <= datetime.fromisoformat(event["start"]) <= end]
        upcoming.sort(key=lambda x: x["start"])
        upcoming = upcoming[:max_events]
        save_yaml_path(CALENDAR_CACHE_FILE, {"last_scan_time": time.time(), "events": upcoming})
        return upcoming
    except Exception as e:
        log(f"Calendar fetch failed: {e}")
        return cache.get("events", [])


def risk_level(internet, router, dns, unknown_count, account_alert_count):
    if not internet and not router:
        return "HIGH"
    if unknown_count > 0 or account_alert_count > 0:
        return "MED"
    if not internet or not dns or not router:
        return "MED"
    return "LOW"


def create_canvas():
    image = Image.new("1", (250, 122), 255)
    draw = ImageDraw.Draw(image)
    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
        font_body = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
    except OSError:
        font_title = ImageFont.load_default()
        font_body = ImageFont.load_default()
        font_small = ImageFont.load_default()
    return image, draw, font_title, font_body, font_small


def draw_footer(draw, font_small):
    now = datetime.now().strftime("%H:%M")
    draw.text((185, 108), f"Upd {now}", font=font_small, fill=0)


def display_image(epd, image):
    epd.display(epd.getbuffer(image))
    epd.sleep()


def render_error_page(message):
    image, draw, font_title, font_body, font_small = create_canvas()
    draw.text((5, 2), "ERROR", font=font_title, fill=0)
    draw.line((5, 20, 245, 20), fill=0)
    draw.text((5, 30), message[:32], font=font_body, fill=0)
    draw.text((5, 50), "Check logs/service", font=font_body, fill=0)
    draw_footer(draw, font_small)
    return image


def render_mini_soc():
    config = load_config()
    network_cfg = config.get("network", {})
    router_ip = network_cfg.get("router_ip", "192.168.0.1")
    dns_domain = network_cfg.get("dns_test_domain", "google.com")
    internet_test_ip = network_cfg.get("internet_test_ip", "1.1.1.1")

    internet = ping_host(internet_test_ip)
    router = ping_host(router_ip)
    dns = dns_ok(dns_domain)

    unknown_devices = detect_unknown_devices()
    unknown_count = len(unknown_devices)
    if unknown_count > 0:
        send_unknown_device_alert(unknown_devices)

    account_alerts, from_cache = scan_account_alerts_cached()
    account_alert_count = len(account_alerts)
    if account_alert_count > 0 and not from_cache:
        send_account_alert_summary(account_alerts)

    risk = risk_level(internet, router, dns, unknown_count, account_alert_count)
    if risk in ["MED", "HIGH"] and unknown_count == 0 and account_alert_count == 0:
        body = f"""
Mini SOC has detected a potential issue.

Risk Level: {risk}
Internet: {'Online' if internet else 'Offline'}
Router: {'OK' if router else 'Down'}
DNS: {'OK' if dns else 'Issue'}
Pi Temp: {get_pi_temp()}C
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        send_email_alert(subject=f"Mini SOC Alert - Risk Level {risk}", body=body, alert_key=f"mini_soc_{risk}")

    image, draw, font_title, font_body, font_small = create_canvas()
    draw.text((5, 2), "MINI SOC", font=font_title, fill=0)
    draw.line((5, 20, 245, 20), fill=0)
    draw.text((5, 25), f"Internet: {'Online' if internet else 'Offline'}", font=font_body, fill=0)
    draw.text((5, 42), f"Router: {'OK' if router else 'Down'}", font=font_body, fill=0)
    draw.text((5, 59), f"DNS: {'OK' if dns else 'Issue'}", font=font_body, fill=0)
    draw.text((5, 76), f"New Dev: {unknown_count}  Acct: {account_alert_count}", font=font_body, fill=0)
    draw.rectangle((150, 30, 240, 76), outline=0)
    draw.text((160, 36), "RISK", font=font_body, fill=0)
    draw.text((165, 55), risk, font=font_title, fill=0)
    draw_footer(draw, font_small)
    return image


def render_home_status():
    config = load_config()
    network_cfg = config.get("network", {})
    internet = ping_host(network_cfg.get("internet_test_ip", "1.1.1.1"))
    router = ping_host(network_cfg.get("router_ip", "192.168.0.1"))
    dns = dns_ok(network_cfg.get("dns_test_domain", "google.com"))
    wifi = get_wifi_strength()
    uptime = get_uptime()
    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory().percent
    temp = get_pi_temp()

    image, draw, font_title, font_body, font_small = create_canvas()
    draw.text((5, 2), "HOME STATUS", font=font_title, fill=0)
    draw.line((5, 20, 245, 20), fill=0)
    draw.text((5, 25), f"Internet: {'Online' if internet else 'Offline'}", font=font_body, fill=0)
    draw.text((5, 42), f"Router: {'OK' if router else 'Down'}", font=font_body, fill=0)
    draw.text((5, 59), f"DNS: {'OK' if dns else 'Issue'}", font=font_body, fill=0)
    draw.text((5, 76), f"Wi-Fi: {wifi}", font=font_body, fill=0)
    draw.text((140, 25), f"CPU: {cpu}%", font=font_body, fill=0)
    draw.text((140, 42), f"RAM: {ram}%", font=font_body, fill=0)
    draw.text((140, 59), f"Temp: {temp}C", font=font_body, fill=0)
    draw.text((140, 76), f"Up: {uptime}", font=font_body, fill=0)
    draw_footer(draw, font_small)
    return image


def render_personal():
    tasks = read_tasks(limit=2)
    weather = get_weather()
    events = fetch_calendar_events()
    image, draw, font_title, font_body, font_small = create_canvas()
    today = datetime.now().strftime("%a %d %b")
    now = datetime.now().strftime("%H:%M")
    draw.text((5, 2), "PERSONAL", font=font_title, fill=0)
    draw.line((5, 20, 245, 20), fill=0)
    draw.text((5, 24), f"{today} {now}", font=font_body, fill=0)
    draw.text((5, 41), weather.get("summary", "Weather N/A")[:30], font=font_body, fill=0)
    y = 58
    if events:
        event = events[0]
        try:
            start = datetime.fromisoformat(event["start"])
            event_text = f"{start.strftime('%H:%M')} {event['summary']}"
        except Exception:
            event_text = event.get("summary", "Event")
        draw.text((5, y), f"Next: {event_text[:28]}", font=font_small, fill=0)
        y += 14
    else:
        draw.text((5, y), "Calendar: Not set/no events", font=font_small, fill=0)
        y += 14
    if tasks:
        for task in tasks:
            draw.text((5, y), f"- {task[:32]}", font=font_small, fill=0)
            y += 13
    else:
        draw.text((5, y), "No tasks", font=font_small, fill=0)
    draw_footer(draw, font_small)
    return image


def main():
    ensure_dirs()
    config = load_config()
    pages = config.get("dashboard", {}).get("pages", ["mini_soc", "home_status", "personal"])
    rotation_seconds = int(config.get("dashboard", {}).get("rotation_seconds", 180))
    renderers = {"mini_soc": render_mini_soc, "home_status": render_home_status, "personal": render_personal}
    epd = epd_driver.EPD()
    page_index = 0
    log("Pi E-Ink Command Centre started.")

    while True:
        page_name = pages[page_index]
        log(f"Rendering page: {page_name}")
        try:
            image = renderers.get(page_name, render_mini_soc)()
        except Exception as e:
            log(f"Page render failed for {page_name}: {e}")
            image = render_error_page(str(e))
        try:
            epd.init()
            epd.Clear(0xFF)
            display_image(epd, image)
        except Exception as e:
            log(f"Display update failed: {e}")
        page_index = (page_index + 1) % len(pages)
        time.sleep(rotation_seconds)


if __name__ == "__main__":
    main()
