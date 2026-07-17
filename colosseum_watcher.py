

import time
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from dotenv import load_dotenv
import os
import logging
import random

# ====================== PODESAVANJA ======================

URL = "https://ticketing.colosseo.it/en/eventi/full-experience-sotterranei-e-arena/"


TARGET_DATE_TEXT = "20"

TARGET_MONTH_YEAR = "August 2026"

load_dotenv()
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_APP_PASSWORD = os.getenv("SENDER_KEY") 
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

#  MINIMUM I MAXIMUM intervala izmedju provera dostupnosti karte
CHECK_INTERVAL_MIN = 10 * 60  # 10 min
CHECK_INTERVAL_MAX = 35 * 60  # 35 min

# ===========================================================

# ========================Logging basic config========================

logging.basicConfig(
    filename="colosseum_watcher.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ========================Funkcija koja salje email========================



def send_email_alert(message: str):
    msg = MIMEText(message)
    msg["Subject"] = "🎟️ Colosseum karte DOSTUPNE!"
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())

    print(f"[{datetime.now()}] Email poslat!")

# ========================Funkcija koja cita mesec i godinu iz kalendara========================
def get_calendar_month_year(page):
    
    month_locator = page.locator(".ui-datepicker-month").first
    year_locator = page.locator(".ui-datepicker-year").first

    if month_locator.count() == 0 or year_locator.count() == 0:
        return None

    month_text = month_locator.inner_text().strip()
    year_text = year_locator.inner_text().strip()

    if not month_text or not year_text:
        return None

    return f"{month_text} {year_text}"  # normalan razmak, garantovano


def navigate_to_month(page, target_month_year: str, max_clicks: int = 24):
 
    for _ in range(max_clicks):
        current_title = get_calendar_month_year(page)
        if current_title is None:
            page.wait_for_timeout(2000)
            continue

        if current_title == target_month_year:
            return True

        next_arrow = page.locator(".ui-datepicker-next").first
        if next_arrow.count() == 0:
            return False

        next_arrow.click()
        page.wait_for_timeout(1000)  # da se kalendar osvezi

    return False

# ========================Logging funkcija========================

def check_tickets_log(tickets_available: bool):
    if tickets_available:
        logging.info("Karte su dostupne na sajtu")
            
    else:logging.info("Karte nisu dostupne na sajtu")
            
    

# ========================Provera dostupnosti========================
def check_availability(page) -> bool:
    
    if not navigate_to_month(page, TARGET_MONTH_YEAR):
        print(f"[{datetime.now()}] Upozorenje: nisam mogao da pronadjem mesec '{TARGET_MONTH_YEAR}' u kalendaru.")
        return False

    cells = page.locator("td:has(span), td:has(a)")
    count = cells.count()

    for i in range(count):
        cell = cells.nth(i)
        text = cell.inner_text().strip()

        if text == TARGET_DATE_TEXT:
            class_attr = cell.get_attribute("class") or ""
            is_disabled = "ui-state-disabled" in class_attr

            if is_disabled:
                status = "closing_day (jos nije pusteno u prodaju)" if "closing_day" in class_attr \
                    else "soldout_day (rasprodato)" if "soldout_day" in class_attr \
                    else "disabled"
                print(f"[{datetime.now()}] Datum {TARGET_DATE_TEXT}: {status}")
                return False
            else:
                print(f"[{datetime.now()}] Datum {TARGET_DATE_TEXT}: DOSTUPNO!")
                return True

    print(f"[{datetime.now()}] Nisam pronasao dan '{TARGET_DATE_TEXT}' u prikazanom mesecu.")
    return False

# ========================Funkcija koja pokrece watcher========================

print("Watcher started")
def run_watcher():
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir="./chrome_profile",
            headless=False
        )
        print("Browser launched")
        stealth = Stealth()
        page = context.new_page()
        stealth.apply_stealth_sync(page)

        

        print(f"[{datetime.now()}] Pokrecem watcher za datum:  {TARGET_DATE_TEXT} {TARGET_MONTH_YEAR}")

        while True:
            try:
                page.goto(URL, timeout=60000)

                # Sacekaj da prodje anti-bot "Checking your browser..." provera
                page.wait_for_timeout(5000)
                page.wait_for_load_state("networkidle", timeout=30000)
                
                available = check_availability(page)
                
                check_tickets_log(available)

                
                print("Page loaded")

                if not available:
                    print(f"[{datetime.now()}] DOSTUPNO! Saljem email...")
                    send_email_alert(
                        f"Karte za {TARGET_DATE_TEXT} {TARGET_MONTH_YEAR} su dostupne na sajtu!\n\n{URL}\n\n"
                        f"Pozuri da kupis!"
                    )
                    break  # prekini nakon uspesnog alarma (ili ukloni break da nastavi da proverava)
                else:
                    print(f"[{datetime.now()}] Jos uvek nedostupno. Cekam...")

            except Exception as e:
                print(f"[{datetime.now()}] Greska prilikom provere: {e}")
                logging.exception(f"Greska prilikom provere: {e}")

            sleep_time = random.uniform(CHECK_INTERVAL_MIN, CHECK_INTERVAL_MAX)
            time.sleep(sleep_time)

        context.close()


if __name__ == "__main__":
    run_watcher()