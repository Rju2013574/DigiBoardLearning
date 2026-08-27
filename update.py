import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import urllib.request
import urllib.parse
import json
import threading
import time
import sys
import traceback
import os

# ==========================================================
# CONFIGURATION ($0 Cost - Standard Python)
# ==========================================================
CURRENT_VERSION = "1.0.0"
GITHUB_REPO = "rju2013574"
CHECK_INTERVAL_SECONDS = 86400  # Check for updates every 24 hours

# Gmail Credentials for Alerts
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "dundiadda2021@gmail.com")
# Replace with a valid 16-character Google App Password from your Google Account
SENDER_APP_PASSWORD = os.environ.get("SENDER_APP_PASSWORD", "3267562787269626")

PRIMARY_RECIPIENT = "juraghav@gmail.com"
CC_RECIPIENTS = [
    "dundiadda2021@gmail.com",
    "nagaraj.js@gmail.com"
]

# ==========================================================
# 1. EMAIL ALERT ENGINE
# ==========================================================
def send_critical_email_alert(error_title, error_report_details):
    """
    Sends an automated failure report email to Raghav with team members CC'd.
    """
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S IST")
    all_recipients = [PRIMARY_RECIPIENT] + CC_RECIPIENTS
    
    subject = f"🚨 [SYSTEM ALERT] DigiBoard Report - {error_title}"
    body = f"""Hello Raghav Jatavallabha Ujjwal!

Here is the requested notification / failure report:

--------------------------------------------------
SYSTEM REPORT DETAILS
--------------------------------------------------
Timestamp: {timestamp}
Summary: {error_title}

Diagnostic Details:
{error_report_details}
--------------------------------------------------

- DigiBoard Automated Telemetry Engine
"""

    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = PRIMARY_RECIPIENT
        msg['Cc'] = ", ".join(CC_RECIPIENTS)
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        # Connect to Gmail SMTP Server (Standard Library)
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_APP_PASSWORD.replace(" ", ""))
        server.sendmail(SENDER_EMAIL, all_recipients, msg.as_string())
        server.quit()
        
        print(f"[Alert System] Email successfully sent to {PRIMARY_RECIPIENT} and team.")
        return True
    except Exception as e:
        print(f"[Alert System] Failed to send email: {e}")
        return False

def trigger_manual_alert(event_name, event_details):
    """Call this function from app.py to send an email on button clicks or events."""
    threading.Thread(
        target=send_critical_email_alert,
        args=(event_name, event_details),
        daemon=True
    ).start()

def handle_uncaught_exception(exctype, value, tb):
    """Global hook to trap system crashes and auto-email Raghav and team."""
    error_summary = str(value)
    detailed_trace = "".join(traceback.format_exception(exctype, value, tb))
    
    send_critical_email_alert(error_summary, detailed_trace)
    sys.__excepthook__(exctype, value, tb)

# Attach global crash handler automatically
sys.excepthook = handle_uncaught_exception

# ==========================================================
# 2. AUTOMATIC BACKGROUND UPDATE GENERATOR
# ==========================================================
def check_for_updates():
    """
    Checks GitHub Releases via REST API for newer versions.
    """
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    req = urllib.request.Request(url, headers={"User-Agent": "DigiBoard-Updater"})
    
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            latest_version = data.get("tag_name", "").lstrip("v")
            
            if latest_version and latest_version != CURRENT_VERSION:
                print(f"[Updater] New update release available: v{latest_version}. Current: v{CURRENT_VERSION}")
            else:
                print(f"[Updater] System running latest release (v{CURRENT_VERSION}).")
    except Exception as e:
        print(f"[Updater] Version check skipped/failed: {e}")

def start_background_updater():
    """
    Launches update checking loop in an isolated background thread.
    """
    def loop():
        while True:
            check_for_updates()
            time.sleep(CHECK_INTERVAL_SECONDS)
            
    thread = threading.Thread(target=loop, daemon=True)
    thread.start()
    print("[Updater] Background interval update engine active.")

if __name__ == "__main__":
    print("Testing update.py email dispatcher...")
    send_critical_email_alert("Test Subject", "Test email content from update.py runner.")
