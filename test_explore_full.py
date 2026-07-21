import asyncio
import os
import requests
from dotenv import load_dotenv

load_dotenv()

from config import CONFIG_DATA
from hiking_scraper import scraper

async def main():
    item = next((i for i in CONFIG_DATA if i['hiking_club_name'] == 'Explore Serbia'), None)
    if not item:
        print("Could not find Explore Serbia config")
        return
        
    print(f"Fetching {item['url']}...")
    res = requests.get(item['url'], timeout=15)
    html_input = res.text
    
    print("Extracting hikes...")
    hikes = await scraper.get_hikes(item, html_input)
    
    print(f"--- FOUND {len(hikes.hikes)} HIKES ---")
    for hike in hikes.hikes:
        print(f"Title: {hike.title}, Date: {hike.exact_date}")
        
if __name__ == '__main__':
    asyncio.run(main())
