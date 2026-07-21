import requests
from bs4 import BeautifulSoup

url = "https://explore-serbia.rs/ture/"
html = requests.get(url).text
soup = BeautifulSoup(html, "html.parser")
events = soup.select('.atlist__item__content')
print(f"Found {len(events)} events.")
if len(events) > 0:
    text = events[0].get_text(separator=' ', strip=True)
    print("Sample text:")
    print(text[:200])
    link_tags = events[0].find_all('a', href=True)
    print("Links:")
    for tag in link_tags:
        print(tag['href'])
