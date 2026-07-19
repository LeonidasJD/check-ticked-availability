
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from dotenv import load_dotenv
import os
import logging


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
                
#=========================Save snapshots========================

def save_debug_snapshot(page, reason: str):
   
    os.makedirs("debug_artifacts", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
 
    screenshot_path = f"debug_artifacts/fail_{timestamp}.png"
    html_path = f"debug_artifacts/fail_{timestamp}.html"
 
    try:
        page.screenshot(path=screenshot_path, full_page=True)
    except Exception as e:
        logging.error(f"Nisam mogao da snimim screenshot: {e}")
 
    try:
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(page.content())
    except Exception as e:
        logging.error(f"Nisam mogao da snimim HTML: {e}")
 
    try:
        current_url = page.url
    except Exception:
        current_url = "nepoznato"
 
    logging.error(f"DEBUG SNAPSHOT ({reason}): {screenshot_path}, {html_path}, url={current_url}")
    print(f"[{datetime.now()}] Snimljen debug snapshot ({reason}): {screenshot_path}, url={current_url}")

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
    save_debug_snapshot(page, "date_cell_not_found")
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

        print(
            f"[{datetime.now()}] Pokrecem watcher za datum: "
            f"{TARGET_DATE_TEXT} {TARGET_MONTH_YEAR}"
        )

        try:
            page.goto(URL, timeout=60000)

            # Sacekaj anti-bot proveru
            page.wait_for_timeout(5000)
            page.wait_for_load_state("networkidle", timeout=30000)

            status_code = page.response.status if page.response else None
            if status_code is not None and status_code >= 400:
                print(f"[{datetime.now()}] UPOZORENJE: HTTP status {status_code} pri ulasku na sajt.")
                save_debug_snapshot(page, f"http_status_{status_code}")

            available = check_availability(page)

            check_tickets_log(available)

            print("Page loaded")

            if available:
                print(f"[{datetime.now()}] DOSTUPNO! Saljem email...")

                send_email_alert(
                    f"Karte za {TARGET_DATE_TEXT} {TARGET_MONTH_YEAR} "
                    f"su dostupne na sajtu!\n\n{URL}\n\n"
                    f"Pozuri da kupis!"
                )

            else:
                print(
                    f"[{datetime.now()}] "
                    f"Jos uvek nedostupno."
                )

        except Exception as e:
            print(
                f"[{datetime.now()}] "
                f"Greska prilikom provere: {e}"
            )

            logging.exception(
                f"Greska prilikom provere: {e}"
            )

        finally:
            context.close()


if __name__ == "__main__":
    run_watcher()