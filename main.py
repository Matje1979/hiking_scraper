import os
import asyncio
import requests
from dotenv import load_dotenv
from schemas import NewHikesList
from config import CONFIG_DATA
from paginator import PaginationContext
from hiking_scraper import scraper as hiking_scraper
from urllib.parse import quote, urlparse, urlunparse


def encode_url(url):
    parts = urlparse(url)
    encoded_path = quote(parts.path)
    return urlunparse((parts.scheme, parts.netloc, encoded_path, parts.params, parts.query, parts.fragment))
    

async def main():
    load_dotenv()
    hikes = NewHikesList()

    for item in CONFIG_DATA:

        # if item['hiking_club_id'] not in [6]: #for testing
        #     continue
        # import pdb; pdb.set_trace()
        if item.get('multipage') == True:
            p_context = PaginationContext(item)

            try:
                result = await p_context.paginate()
                if result:
                    hikes.hikes.extend(result)
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
                    res = session.get(encode_url(item['url']), headers=headers)
                else:
                    res = session.get(item['url'], headers=headers)
                if res.status_code != 200:
                    try:
                        headers = {
                            "User-Agent": "curl/8.5.0",
                            "Accept": "*/*",
                            "Accept-Encoding": "identity",
                            "Connection": "close",
                        }
                        res = session.get(item['url'], headers=headers)
                    except Exception as e:
                        print(f"Error fetching {item['url']}: {res.status_code}")
                        continue
                if "charset=utf-8" in res.headers.get("Content-Type", "").lower():
                    html_input = res.content.decode("utf-8", errors="replace")
                else:
                    html_input = res.content

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
    print("Finished scraping!")
    
    API_URL = os.getenv("MAIN_APP_API_URL")
    API_KEY = os.getenv("API_KEY")

    if not API_URL or not API_KEY:
        print("Error: MAIN_APP_API_URL or API_KEY not set in environment.")
        return

    print(f"Sending {len(hikes.hikes)} hikes to {API_URL}...")
    try:
        response = requests.post(
            API_URL,
            json=hikes.model_dump(),
            headers={"api-key": API_KEY, "x-api-key": API_KEY, "Authorization": f"Bearer {API_KEY}"},
            params={"api_key": API_KEY}
        )
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text}")
    except Exception as e:
        print(f"Error sending data to API: {e}")

if __name__ == "__main__":
    asyncio.run(main())