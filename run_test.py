import asyncio
from config import CONFIG_DATA
from hiking_scraper import scraper

async def main():
    for item in CONFIG_DATA:
        if item.get('hiking_club_name') == 'PSK Balkan':
            print(f"Testing {item['hiking_club_name']}")
            # just mock it or run it?
            # Better to just see the main script output
