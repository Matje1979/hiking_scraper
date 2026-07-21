
from bs4 import BeautifulSoup
from datetime import datetime
import json
from datetime import datetime
from openai import AsyncOpenAI
from openai import OpenAI
from schemas import NewHike, NewHikesList
from transliterate import translit
from datetime import date
import re
import os

def js_array_to_python(js_array: str):
    # Remove trailing commas
    js_array = re.sub(r',\s*([\]}])', r'\1', js_array)

    # Quote unquoted keys (important!)
    js_array = re.sub(r'(\w+)\s*:', r'"\1":', js_array)

    # Fix leading-zero numbers
    js_array = re.sub(r':\s*0+(\d+)', r': \1', js_array)

    return json.loads(js_array)


class HikingScraper:
    def __init__(self):
        self.deepseek_client = AsyncOpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com"
        )
        # self.openai_client = OpenAI(
        #         api_key=os.getenv("OPENAI_SECRET_KEY")
        #     )
        
    async def get_ai_response(self, system_prompt, html_input):
        response = await self.deepseek_client.chat.completions.create(
            model="deepseek-v4-flash",  # Use the appropriate GPT model
            messages=[
                {
                    "role": "system", 
                    "content": "You are an assistant that extracts structured data from text."
                },
                {"role": "user", "content": system_prompt},
                {"role": "user", "content": html_input},
            ],
            response_format={
                "type": "json_object"
            },
            temperature=0,  # Set to 0 for deterministic output
            max_tokens=4000,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0,
        )

        # Extract and parse the response
        finish_reason = response.choices[0].finish_reason
        raw = response.choices[0].message.content
        if finish_reason == "length":
            print(f"Warning: LLM response was truncated (hit max_tokens)")
        if not raw or not raw.strip():
            print(f"LLM returned empty response. Finish reason: {response.choices[0].finish_reason}")
            return {"events": []}
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            # LLMs sometimes produce JS-style JSON — try to fix common issues
            cleaned = raw
            # 1. Remove trailing commas: {"a": 1,} → {"a": 1}
            cleaned = re.sub(r',\s*([\]}])', r'\1', cleaned)
            # 2. Replace single quotes with double quotes: {'a': 'b'} → {"a": "b"}
            cleaned = cleaned.replace("'", '"')
            # 3. Remove JS-style comments: // ... or /* ... */
            cleaned = re.sub(r'//.*?$', '', cleaned, flags=re.MULTILINE)
            cleaned = re.sub(r'/\*.*?\*/', '', cleaned, flags=re.DOTALL)
            try:
                result = json.loads(cleaned)
            except json.JSONDecodeError:
                print(f"Failed to parse LLM response even after cleaning:\n{raw}")
                raise
        
        return result
    
    async def extract_event_list_info(self, html_input: str, country: str = "Unknown"):
        # Define the system prompt to instruct the model
        system_prompt = f"""
            You are an assistant that extracts structured information from hiking event announcements.

            The input may be:
            - HTML text
            - OR a JavaScript snippet containing a variable (e.g. `const tours = [...]`)
            where each object in the array represents a separate hiking event.

            Your task is to extract structured information and return it in VALID JSON format.

            For each hiking event, extract the following fields:

            - event_name:
            The name/title of the hiking event.
            Do NOT include dates or times in the event name.

            - start_date:
            The event start date in YYYY-MM-DD format.
            If the year is missing, assume 2026.
            Note: This announcement is from a club based in {country}. 
            Please use the standard date formatting conventions for that country 
            when interpreting ambiguous dates like 05/07.

            - end_date:
            The event end date in YYYY-MM-DD format.
            If missing, assume it is the same as the start date.

            - link:
            The URL leading to the event's details page.

            - guide_name:
            The name of the guide or coordinator leading the hike.
            If multiple guides are listed, return the first one.

            - hiking_club:
            The name of the hiking club or organization, if available.

            - length:
            The total hiking distance (if mentioned).

            - height:
            The elevation gain of the hike
            (may appear as "uspon" or "visinska razlika u usponu" in Serbian).

            - price:
            The participation cost of the event.

            Rules:

            - If any information, except event name, is missing, set its value to null.
            - If event name is missing, return the first 5 words of the announcement as event name.
            - If the event date lacks a year, default it to 2026.
            - If the link contains only the relative path to the event's details page, do not try to figure out the full path.
            - If the announcement describes a repeating event with same title and other info but different dates, return a list of JSON objects, where each object has the above-defined format.
            - Ensure the output is valid JSON with correctly formatted values.
            - Do not include event start and end date and times in the event name.
        """

        result = await self.get_ai_response(system_prompt, html_input)

        return result


    async def extract_basic_event_info(self, html_input: str, country: str = "Unknown"):
        # Define the system prompt to instruct the model

        system_prompt = f"""
        You are an assistant that extracts structured information 
        from hiking event announcements.
        Extract the following details and return them in valid JSON format:

        - event_name: The name of the hiking event.
        - start_date: The event's start date in YYYY-MM-DD format. 
        If the year is not mentioned clearly, assume the year is 2026.
        Note: This announcement is from a club based in {country}. 
        Please use the standard date formatting conventions for that country 
        when interpreting ambiguous dates like 05/07.
        - end_date: The event's end date in YYYY-MM-DD format. 
        If not provided, assume it is the same as the start date.
        - link: The URL leading to the event's details page.
        IMPORTANT: A link (<a> tag) that wraps the name of a person (guide/coordinator)
        is a link to that person's profile, NOT the event details page — do NOT use it
        as the event link. The event link is typically the one wrapping the event title
        or a "details" / "more info" call-to-action.
        - guide_name: The name of the guide (or coordinator if there is no guide)
        leading the hike.
        - hiking_club: The name of the hiking club organizing the event (if available).
        - length: The distance that the group will traverse during the event.
          Always return as a string, e.g. "17 km" or "17" — never as a bare number.
        - height: The elevation gain during the event
          ('uspon' or 'visinska razlika u usponu' in Serbian).
          Always return as a string, e.g. "800 m" or "800" — never as a bare number.
        - price: The cost of the participation in the event.
          Always return as a string, e.g. "500 RSD" or "500" — never as a bare number.

        Rules:

        If any information, except event name, is missing, set its value to null.
        If event name is missing return the first 5 words of the announcement as event name.
        If the event date lacks a year, default it to the current year.
        If the link contains only the relative path to the event's details page,
        do not try to figure out the full path, just return the relative path.
        If the announcement describes multiple events with the same title but different dates, 
        return a dictionary with key "events" and value the list of json objects,
        where each object has the above defined format.
        If the announcement describes a single event, return a dictionary with key "events"
        and value a list containing a single json object with the above defined format.
        Ensure the output is valid JSON with correctly formatted values.
        Do not inlcude event start and end date and times in the event name.
        """

        result = await self.get_ai_response(system_prompt, html_input)

        # Normalize: ensure we always return {"events": [list of dicts]}
        # regardless of what shape the LLM actually produced.
        if isinstance(result, list):
            # LLM returned a bare list like [{...}, {...}]
            result = {"events": result}
        elif isinstance(result, dict) and "events" not in result:
            # LLM returned a flat dict like {"event_name": ..., "start_date": ...}
            result = {"events": [result]}

        return result


    def format_event(self, basic_event_dict, item):
        hiking_club_id = item['hiking_club_id']
        event_dict = basic_event_dict
        if (
            not event_dict.get('link')
        ):
            return None
        if not event_dict.get('start_date', None):
            return None

        if event_dict['event_name']:
            title = translit(event_dict['event_name'], "sr", reversed=True).upper()
        else:
            title = event_dict['event_name']

        club = item['hiking_club_name']

        if event_dict.get('link'):
            if 'http' not in event_dict.get('link'):
                link_to_detail_page = item['base_url'] + event_dict.get('link') # case when link is relative
            else:
                link_to_detail_page = event_dict.get('link')
        else:
            link_to_detail_page = item['url'] # default link to the club's events page

        description = ""
        try:
            start_date = datetime.strptime(event_dict['start_date'], '%Y-%m-%d')
            if event_dict['end_date']:
                end_date = datetime.strptime(event_dict['end_date'], '%Y-%m-%d')
            else:
                end_date = start_date
        except:
            return
        if item["hiking_club_id"] in [36, 148, 132]:
            if start_date.month < date.today().month:
                start_date = start_date.replace(year=date.today().year + 1)
                end_date = end_date.replace(year=date.today().year + 1)
            elif start_date.month > end_date.month:
                end_date = end_date.replace(year=date.today().year + 1)
            exact_date = start_date
        else:
            exact_date = event_dict['start_date']

        diff_delta = end_date - start_date
        diff = diff_delta.days
        
        guide = event_dict.get('guide_name', '') or ""

        if not guide:
            guide = ''
        if club == 'PD Krug':
            guide = 'Milan Vojnović i Jasmina Vojnović'

        length = str(event_dict.get('length') or "")
        height = str(event_dict.get('elevation_gain') or "")
        time_length = ''
        price = str(event_dict.get('price') or "")

        action = NewHike(
            title=title,
            hiking_club_id=hiking_club_id,
            link_to_detail_page=link_to_detail_page,
            description=description,
            diff=diff, # end date - start date
            guide=guide,
            length=length,
            height=height,
            time_length=time_length,
            price=str(price),
            exact_date=exact_date,
            location_id=item['location_id']
        )

        return action


    async def extract_event_details(self, html_input: str):
        # Define the system prompt to instruct the model
        system_prompt = """
        You are an assistant that extracts specific information from hiking event announcements.
        Extract the following details in JSON format:
        - guide: The name of the guide.
        - price: The price for participation in the event.
        - length: The length of the trail that will be hiked.
        - elevation_gain: the total number of meters that hikers will ascend 
        during the hike (visinska razlika u usponu in Serbian).
        - duration: The duration of the hike.
        If any information is missing, set its value to empty string.
        """
        # try:
        # Call the Deepseek API
        response = await self.deepseek_client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": html_input}
            ],
            response_format={"type": "json_object"}
        )

        # Extract the raw response
        raw_response = response.choices[0].message.content

        # Parse the JSON string into a Python dictionary
        result_dict = json.loads(raw_response)
        return result_dict


    @staticmethod
    def _clean_event_input(event, link_skip_patterns=None, max_text_length=None, css_exclude=None):
        """Extract clean text + link from a BeautifulSoup element.

        Sending raw HTML to the LLM can cause malformed JSON when attributes
        contain unescaped quotes. Instead, we extract just the text content
        and the link href — which is all the model needs.
        """
        if hasattr(event, 'get_text'):
            # Work on a copy so we don't mutate the original tree
            from copy import copy
            event = copy(event)
            # Strip noisy tags that add JS/CSS junk
            for tag in event.find_all(['script', 'style', 'noscript']):
                tag.decompose()
            # Strip config-specified sections (e.g. hidden/clipped description containers)
            if css_exclude:
                for selector in css_exclude:
                    for tag in event.select(selector):
                        tag.decompose()

            text = event.get_text(separator=' ', strip=True)
            if max_text_length:
                text = text[:max_text_length]
            link_tags = event.find_all('a', href=True)
            # If the selected element itself is an <a> tag, include it too
            if event.name == 'a' and event.get('href'):
                link_tags = [event] + link_tags

            # Deduplicate by href and optionally skip patterns
            seen_hrefs = set()
            filtered_links = []
            for tag in link_tags:
                href = tag['href']
                if href in seen_hrefs:
                    continue
                if link_skip_patterns and any(p in href for p in link_skip_patterns):
                    continue
                seen_hrefs.add(href)
                filtered_links.append(tag)

            if filtered_links:
                links_description = '\n'.join(
                    f'  Link {i+1}: href="{tag["href"]}" text="{tag.get_text(strip=True)}"'
                    for i, tag in enumerate(filtered_links)
                )
                return (
                    f"Event text: {text}\n"
                    f"Links found in this event block:\n{links_description}"
                )
            return f"Event text: {text}\nEvent link: (none found)"
        # JS-extracted events or plain strings — pass through as-is
        return str(event)

    @staticmethod
    def _extract_brace_matched_json(source: str, start_pos: int) -> dict:
        """Extract a brace-matched JSON object from a string starting at start_pos."""
        obj_start = source.index('{', start_pos)
        depth, i = 0, obj_start
        while i < len(source):
            if source[i] == '{':
                depth += 1
            elif source[i] == '}':
                depth -= 1
                if depth == 0:
                    break
            i += 1
        return json.loads(source[obj_start:i + 1])

    @staticmethod
    def _map_embedded_event(event_data: dict, field_map: dict, item: dict) -> dict:
        """Map fields from an embedded JSON event to the standard event_dict format.

        field_map maps our standard keys to the source's keys, e.g.:
            {'event_name': 'title', 'start_date': 'start', ...}
        Any unmapped field falls back to the standard key name.
        """
        def _get(standard_key, default=None):
            source_key = field_map.get(standard_key, standard_key)
            return event_data.get(source_key, default)

        start_raw = _get('start_date') or ''
        end_raw = _get('end_date') or start_raw

        return {
            'event_name': _get('event_name'),
            'start_date': start_raw[:10],
            'end_date': end_raw[:10],
            'link': _get('link'),
            'guide_name': _get('guide_name'),
            'hiking_club': item['hiking_club_name'],
            'length': _get('length'),
            'height': _get('height'),
            'price': _get('price'),
        }

    async def get_hikes(self, item, page_source):
        actions_list = NewHikesList()
        strategy = item.get('extraction_strategy', 'css')

        if strategy == 'js_var':
            # Events live in a JS variable (e.g. `const tours = [...]`)
            # Each object is extracted and sent to the LLM for parsing.
            page_source_str = page_source if isinstance(page_source, str) else page_source.decode('utf-8', errors='replace')
            match = re.search(item['js_var_pattern'], page_source_str)
            if not match:
                raise ValueError(f"JS variable not found for {item['hiking_club_name']}")
            array_text = match.group(1)
            events = re.findall(r'\{[\s\S]*?\}', array_text)

        elif strategy == 'embedded_json':
            # Structured JSON embedded in a JS variable — parse directly, no LLM needed.
            page_source_str = page_source if isinstance(page_source, str) else page_source.decode('utf-8', errors='replace')
            var_match = re.search(item['js_var_pattern'], page_source_str)
            if not var_match:
                raise ValueError(f"Embedded JSON var not found for {item['hiking_club_name']}")

            parsed_data = self._extract_brace_matched_json(page_source_str, var_match.start())
            events_key = item.get('js_events_path', '')
            raw_events = parsed_data.get(events_key, []) if events_key else (
                parsed_data if isinstance(parsed_data, list) else [parsed_data]
            )
            field_map = item.get('js_field_map', {})

            print(f"{item['hiking_club_name']}: found {len(raw_events)} events in embedded JSON")

            for event_data in raw_events:
                event_dict = self._map_embedded_event(event_data, field_map, item)
                try:
                    action = self.format_event(event_dict, item)
                except Exception as e:
                    print(f"Error formatting event '{event_dict.get('event_name')}': {e}")
                    continue
                if action:
                    actions_list.hikes.append(action)

            print("actions_list: ", actions_list)
            return actions_list

        else:  # css (default)
            soup = BeautifulSoup(page_source, "html.parser")
            # import pdb; pdb.set_trace()
            # print(soup.select('*:has(> .event-link)'))
            events = soup.select(item['event_css'])
            print(events)

        # For css and js_var strategies, each event goes through the LLM
        for event in events:
            clean_input = self._clean_event_input(
                event, item.get('link_skip_patterns'),
                item.get('max_text_length'), item.get('css_exclude')
            )
            try:
                basic_event_dict = await self.extract_basic_event_info(clean_input, item.get('country', 'Unknown'))
            except Exception as e:
                print(f"Error extracting event info, skipping event: {e}")
                continue
            print(basic_event_dict)
            print()
            # extract_basic_event_info always returns {"events": [list of dicts]}
            for event_dict in basic_event_dict.get('events', []):
                try:
                    action = self.format_event(event_dict, item)
                except Exception as e:
                    event_name = event_dict.get('event_name', 'Unknown event')
                    print(f"Error formatting event '{event_name}', skipping: {e}")
                    continue
                if not action:
                    continue
                print("action: ", action)
                actions_list.hikes.append(action)
        print("actions_list: ", actions_list)

        return actions_list


# Shared singleton — import this instead of instantiating HikingScraper() directly.
scraper = HikingScraper()