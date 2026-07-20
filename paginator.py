
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
import requests
import time
from selenium.webdriver.chrome.options import Options
from abc import ABC, abstractmethod
from selenium.webdriver.common.by import By
import time
from hiking_scraper import scraper as _scraper


class AbstractPaginator(ABC):
    """Abstract base class for pagination strategies."""

    def __init__(self, item, *args, **kwargs):
        """
        Initialize the strategy with an item config dict.
        :param args: Additional positional arguments.
        :param kwargs: Additional keyword arguments.
        """
        self.item = item
        self.paginator_selector = item['paginator_selector']
        self.args = args
        self.kwargs = kwargs
        

    @abstractmethod
    async def paginate(self, driver):
        """Execute pagination strategy."""
        pass


class NextButtonPaginator(AbstractPaginator):
    async def paginate(self, driver):
        """Click 'Next' button until it disappears, parsing each page."""
        driver.get(self.item['url']) # go to first page
        result = []

        while True:
            page_source = driver.page_source
            result += await _scraper.get_hikes(self.item, page_source)
            
            next_buttons = driver.find_elements(By.XPATH, f"//a[contains(text(),'Next') or {self.paginator_selector}]")
            if not next_buttons:
                break

            ActionChains(driver).move_to_element(next_buttons[0]).perform()
            time.sleep(2)
            next_buttons[0].click()
            time.sleep(2)  # Wait for page load

        return result


class PageLinksPaginator(AbstractPaginator):
    async def paginate(self, driver):
        """Click numbered pagination links one by one, parsing each page."""

        session = requests.session()
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:60.0) Gecko/20100101 Firefox/60.0 Chrome/51.0.2704.103 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        result_list = []
        page = 1
        page_url = self.item['paginator_selector'] + str(page)
        res = session.get(page_url, headers=headers, timeout=15)
        result = await _scraper.get_hikes(self.item, res.content)

        while result and result.hikes:
            result_list.extend(result.hikes)
            page += 1
            page_url = self.item['paginator_selector'] + str(page)
            res = session.get(page_url, headers=headers, timeout=15)
            result = await _scraper.get_hikes(self.item, res.content)
            
        return result_list


class PaginationContext:
    """Context class to select the best pagination strategy dynamically."""

    def __init__(self, item):
        """
        Detects and selects the best pagination strategy.
        
        :param item: Confguration for website which contains data about pagination.
        """

        self.chromedriver_path = "/usr/local/bin/chromedriver"

        self.link = item['url']

        if not self.chromedriver_path:
            raise ValueError("ChromeDriver not found. Make sure it's installed.")

        self.chrome_options = Options()

        self.chrome_options.add_argument("--window-size=1920,1080")
        self.chrome_options.add_argument('--headless')
        self.chrome_options.add_argument('--no-sandbox')
        self.chrome_options.add_argument("--disable-dev-shm-usage")

        self.driver = ''

        self.item = item
        self.paginator = self.get_paginator(item['paginator_strategy'])

    def get_paginator(self, pagination_strategy, *args, **kwargs):
        """Automatically detect pagination strategy."""

        if pagination_strategy == 'page_links':
            return PageLinksPaginator(self.item)
        elif pagination_strategy == 'next_button':
            return NextButtonPaginator(self.item)
        else:
            return None
    

    async def paginate(self):
        """Run the selected pagination strategy."""
        if self.paginator:
            return await self.paginator.paginate(self.driver)
        else:
            print("No pagination detected.")
