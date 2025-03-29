import scrapy
from web_scraper.items import WebPageItem
from datetime import datetime
from bs4 import BeautifulSoup

def extract_content_and_titles(html, is_index=False):
    """
    Extracts content and section titles from the given HTML, handling both index and content pages.

    Args:
        html (str): The HTML content as a string.
        is_index (bool): True if the page is the index page, False otherwise.

    Returns:
        tuple: (content_str, section_titles) - Extracted content in markdown and list of titles.
    """
    soup = BeautifulSoup(html, 'html.parser')
    section_titles = []
    content= ""

    if is_index:
    # Index page extraction
        intro_div = soup.find_all('div', class_='content-intro')
        for intro in intro_div:
            content += intro.get_text(strip=True)
    else:

        content_div = soup.find('div', class_ = ['content-intro', 'view-box'])
        try:
            sections = content_div.find_all("h2")
            section_titles = [text for titles in sections if (text := titles.get_text(strip=True))]
        except:
            pass

        content += content_div.get_text(strip=True)
        
    return content, section_titles

class W3cschoolsSpider(scrapy.Spider):
    name = "w3cschools"
    allowed_domains = ["w3cschool.cn"]
    start_urls = [
                # "https://www.w3cschool.cn/python3/"
                #    "https://www.w3cschool.cn/deepseekdocs/"
                #   "https://www.w3cschool.cn/pytorch/", 
                "https://www.w3cschool.cn/tensorflow_python/"
                #   "https://www.w3cschool.cn/artificial_intelligence/", 
                # "https://www.w3cschool.cn/mysql/"
                #   ,"https://www.w3cschool.cn/redis/"
                  ]
    
    custom_settings = {
        'DEPTH_LIMIT': 0,
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
        'FILES_STORE': 'webpages',  # Directory to save pages
        'HTTPCACHE_ENABLED': True,
        'CONCURRENT_REQUESTS': 5,  # Limit to 5 concurrent requests
        'PLAYWRIGHT_MAX_PAGES_PER_CONTEXT': 10,  # Limit pages per context
    }

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                meta={
                    "playwright": True,
                    "playwright_include_page": True,
                    # "playwright_context": "browser_context",
                    # "playwright_page_goto_kwargs": {
                    #     "wait_until": "load",
                    #     "timeout": 6000
                    # },
                    "playwright_page_init_coroutine": self.setup_block_media,  # 👈 Add this
                    "errback": self.errback,
                    'DOWNLOAD_DELAY': 1,  # Wait 2 seconds between requests
                    'RANDOMIZE_DOWNLOAD_DELAY': True,  # Randomize the delay
                    'RETRY_TIMES': 2,  # Retry only 2 times
                    'RETRY_HTTP_CODES': [500, 503, 504, 408],  # Exclude 502
                    'CONCURRENT_REQUESTS': 10,  # Limit to 5 at a time
                },
                callback=self.parse
            )

    async def parse(self, response):
        self.logger.info(f"Status {response.status} for {response.url}")
        if response.status != 200:
            self.logger.warning(f"Non-200 response: {response.text[:200]}")

        article_title = response.css("title::text").get()
        
        # Determine if this is the index page
        is_index = response.url in self.start_urls
        content, section_titles = extract_content_and_titles(response.text, is_index)
        item = WebPageItem()
        item['url'] = response.url
        item['content'] = content
        item['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        item['title'] = article_title
        item['section_titles'] = section_titles
        yield item

        # Close the Playwright page to free resources
        page = response.meta.get("playwright_page")
        if page:
            await page.close()
        
        self.logger.info(f"Processed {response.url}, queue size: {len(self.crawler.engine.slot.scheduler)}")

        links = response.css(".dd-content a::attr(href)").getall()
        for link in links:
            absolute_url = response.urljoin(link)
            if any(sub in absolute_url for sub in ('play/', 'minicourse/')) or absolute_url == response.url or absolute_url in self.start_urls:
                continue
            yield response.follow(
                link,
                callback=self.parse,
                meta={
                    "playwright": True,
                    "playwright_include_page": True,
                    # "playwright_context": "browser_context",
                    # "playwright_page_goto_kwargs": {
                    #     "wait_until": "load",
                    #     "timeout": 6000
                    # },
                    "playwright_page_init_coroutine": self.setup_block_media,  # 👈 Add this
                    "errback": self.errback,
                    'DOWNLOAD_DELAY': 1,  # Wait 2 seconds between requests
                    'RANDOMIZE_DOWNLOAD_DELAY': True,  # Randomize the delay
                    'RETRY_TIMES': 2,  # Retry only 2 times
                    'RETRY_HTTP_CODES': [500, 503, 504, 408],  # Exclude 502
                    'CONCURRENT_REQUESTS': 10,  # Limit to 5 at a time
                },
            )

    async def errback(self, failure):
        self.logger.error(f"Request failed: {failure.request.url}")
        page = failure.request.meta.get("playwright_page")
        if page:
            await page.close()
    
    async def block_media(self, route):
    # Block non-essential resources
        blocked_types = {"image", "stylesheet", "font", "media"}
        if route.request.resource_type in blocked_types:
            await route.abort()
        else:
            await route.continue_()
	    
    async def setup_block_media(self, page):
    # Attach the blocking handler to all routes
        await page.route("**/*", self.block_media)