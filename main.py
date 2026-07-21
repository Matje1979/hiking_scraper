import os
from dotenv import load_dotenv

# Load environment variables FIRST before importing any modules that might instantiate clients
load_dotenv()

import asyncio
import requests
from schemas import NewHikesList
from config import CONFIG_DATA
from paginator import PaginationContext
from hiking_scraper import scraper as hiking_scraper
from urllib.parse import quote, urlparse, urlunparse

from urllib.parse import quote, urlparse, urlunparse
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_timeout_email(club_name, url):
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    sender_email = os.getenv("SMTP_USERNAME")
    sender_password = os.getenv("SMTP_PASSWORD")
    recipient_email = "damircicic@gmail.com"

    if not sender_email or not sender_password:
        print(f"Warning: SMTP credentials not set. Could not send timeout email for {club_name}.")
        return

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = f"Scraper Timeout Alert: {club_name}"
    
    body = f"The scraper encountered a timeout while trying to fetch the website for {club_name}.\nURL: {url}\n\nPlease check if the website is down or blocking requests."
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        print(f"Timeout notification email sent for {club_name}.")
    except Exception as e:
        print(f"Failed to send email for {club_name}: {e}")

def encode_url(url):
    parts = urlparse(url)
    encoded_path = quote(parts.path)
    return urlunparse((parts.scheme, parts.netloc, encoded_path, parts.params, parts.query, parts.fragment))
    

async def main():
    API_URL = os.getenv("MAIN_APP_API_URL")
    API_KEY = os.getenv("API_KEY")

    if not API_URL or not API_KEY:
        print("Error: MAIN_APP_API_URL or API_KEY not set in environment.")
        return

    for item in CONFIG_DATA:
        if not item.get('hiking_club_id') == 30:
            continue
        hikes = NewHikesList()

        # if item['hiking_club_id'] not in [6]: #for testing
        #     continue
        # import pdb; pdb.set_trace()
        if item.get('multipage') == True:
            p_context = PaginationContext(item)

            try:
                result = await p_context.paginate()
                if result:
                    hikes.hikes.extend(result)
            except requests.exceptions.Timeout:
                print(f"Timeout during pagination for {item.get('hiking_club_name', 'unknown')}")
                send_timeout_email(item.get('hiking_club_name', 'unknown'), item['url'])
                continue
            except Exception as e:
                print(f"Error during pagination for {item.get('hiking_club_name', 'unknown')}: {e}")
                continue
        else:
            session = requests.session()
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Referer": "https://www.google.com/"
            }
            try:
                if item.get('hiking_club_name') == 'PD Josif Pančić':
                    res = session.get(encode_url(item['url']), headers=headers, timeout=15)
                else:
                    res = session.get(item['url'], headers=headers, timeout=15)
                if res.status_code != 200:
                    try:
                        headers = {
                            "User-Agent": "curl/8.5.0",
                            "Accept": "*/*",
                            "Accept-Encoding": "identity",
                            "Connection": "close",
                        }
                        res = session.get(item['url'], headers=headers, timeout=15)
                    except Exception as e:
                        print(f"Error fetching {item['url']}: {res.status_code}")
                        continue
                if "charset=utf-8" in res.headers.get("Content-Type", "").lower():
                    html_input = res.content.decode("utf-8", errors="replace")
                else:
                    html_input = res.content

            except requests.exceptions.Timeout:
                print(f"Timeout fetching {item['url']}")
                send_timeout_email(item.get('hiking_club_name', 'unknown'), item['url'])
                continue
            except Exception as e:
                print(f"Error fetching {item['url']}: {e}")
                continue
            try:
                result = await hiking_scraper.get_hikes(item, html_input)
                if result:
                    hikes.hikes.extend(result.hikes)
            except Exception as e:
                print(f"Error processing {item.get('hiking_club_name', 'unknown')}: {e}")
                continue
        if not hikes.hikes:
            print(f"No hikes found for {item.get('hiking_club_name', 'unknown')}. Skipping API request.")
            continue

        print(f"Finished scraping {item.get('hiking_club_name', 'unknown')}!")
        print(f"Sending {len(hikes.hikes)} hikes to {API_URL}...")
        try:
            response = requests.post(
                API_URL,
                json=hikes.model_dump(mode='json'),
                headers={"api-key": API_KEY, "x-api-key": API_KEY, "Authorization": f"Bearer {API_KEY}"},
                params={"api_key": API_KEY},
                timeout=15
            )
            print(f"Response status: {response.status_code}")
            print(f"Response body: {response.text}")
        except Exception as e:
            print(f"Error sending data to API: {e}")

if __name__ == "__main__":
    asyncio.run(main())