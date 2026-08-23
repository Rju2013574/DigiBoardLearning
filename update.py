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

# ==========================================================
# CONFIGURATION ($0 Cost - Standard Python)
# ==========================================================
CURRENT_VERSION = "1.0.0"
GITHUB_REPO = "YOUR_GITHUB_USERNAME/YOUR_REPO_NAME"  # e.g. "raghav/digiboard"
CHECK_INTERVAL_SECONDS = 86400  # Check for updates every 24 hours

# Gmail Credentials for Alerts
SENDER_EMAIL = "no.reply_Digiboardlearning@gmail.com"        # Your sending Gmail
SENDER_APP_PASSWORD = "3267562787269626"          # 16-digit Google App Password

PRIMARY_RECIPIENT = "juraghav@gmail.com"
CC_RECIPIENTS = [
    "dundiadda2021@gmail.com",                              # Add team member emails here
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
    
    subject = f"🚨 [SYSTEM CRITICAL ALERT] Failure Report - {error_title}"
    body = f"""Hello Raghav Jatavallabha Ujjwal!

Here is some failure look into it:

--------------------------------------------------
SYSTEM FAILURE REPORT
--------------------------------------------------
Timestamp: {timestamp}
Error Summary: {error_title}

Detailed Diagnostic Logs:
{error_report_details}
--------------------------------------------------

Please review and deploy a hotfix or software patch if required.

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
        server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
        server.sendmail(SENDER_EMAIL, all_recipients, msg.as_string())
        server.quit()
        
        print(f"[Alert System] Critical failure email successfully sent to {PRIMARY_RECIPIENT} and team.")
    except Exception as e:
        print(f"[Alert System] Failed to send alert email: {e}")

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
