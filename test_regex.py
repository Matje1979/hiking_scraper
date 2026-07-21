import re
import requests

url = "https://www.pdorfej.com/"
resp = requests.get(url)
html = resp.text

match = re.search(r'const tours\s*=\s*\[([\s\S]*?)\];', html)
if match:
    array_text = match.group(1)
    events = re.findall(r'\{[\s\S]*?\}', array_text)
    print(f"Found {len(events)} events")
    if events:
        print("First event:")
        print(events[0])
else:
    print("Match not found")
