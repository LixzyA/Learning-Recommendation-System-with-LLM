import scrapy
from web_scraper.items import WebPageItem
from datetime import datetime
from bs4 import BeautifulSoup
from pytz import timezone

def extract_content(html, is_index=False):
    """
    Extracts content and section titles from the given HTML, handling both index and content pages.

    Args:
        html (str): The HTML content as a string.
        is_index (bool): True if the page is the index page, False otherwise.

    Returns:
        str: Extracted content in markdown, or empty string if no content found.
    """
    soup = BeautifulSoup(html, 'html.parser')
    content = ""

    if is_index:
        # Index page extraction: Concatenate all matching intros
        intro_divs = soup.find_all('div', class_='content-intro')
        for intro in intro_divs:
            if intro:  # Check if element exists (defensive)
                content += intro.get_text(strip=True)
    else:
        # Non-index: Try 'content-intro' first, fall back to 'view-box'
        content_div = soup.find('div', class_='content-intro') or soup.find('div', class_='view-box')
        if content_div:
            content = content_div.get_text(strip=True)

    return content  # Returns "" if nothing found

class W3cschoolsSpider(scrapy.Spider):
    name = "w3cschools"
    allowed_domains = ["w3cschool.cn"]
    start_urls = [
                "https://www.w3cschool.cn/python3/",
                "https://www.w3cschool.cn/deepseekdocs/" ,
                "https://www.w3cschool.cn/pytorch/", 
                "https://www.w3cschool.cn/tensorflow_python/",
                "https://www.w3cschool.cn/artificial_intelligence/", 
                "https://www.w3cschool.cn/mysql/",
                "https://www.w3cschool.cn/redis/",
                "https://www.w3cschool.cn/c/",
                "https://www.w3cschool.cn/linux/",
                "https://www.w3cschool.cn/java/",
                "https://www.w3cschool.cn/weixinapp/",
                "https://www.w3cschool.cn/sql/",
                "https://www.w3cschool.cn/javascript/",
                "https://www.w3cschool.cn/cpp/",
                "https://www.w3cschool.cn/sass/",
                "https://www.w3cschool.cn/jquery/",
                "https://www.w3cschool.cn/react/",
                "https://www.w3cschool.cn/go/",
                "https://www.w3cschool.cn/r/",
                "https://www.w3cschool.cn/ruby/",
                "https://www.w3cschool.cn/php/",
                "https://www.w3cschool.cn/neo4j/",
                "https://www.w3cschool.cn/spark/",
                "https://www.w3cschool.cn/docker/",
                "https://www.w3cschool.cn/kubernetes/"
                  ]
    
    custom_settings = {
        'DEPTH_LIMIT': 0,
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
    }

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                meta={
                    # "playwright": True,
                    # "playwright_include_page": True,
                    # "playwright_page_init_coroutine": self.setup_block_media,
                    "errback": self.errback,
                    'RETRY_TIMES': 3,  # Retry only 2 times
                    "RETRY_HTTP_CODES" : [500, 502, 503, 504, 408, 429]  # Include 429 for rate limiting
                },
                callback=self.parse
            )

    async def parse(self, response):
        page = response.meta.get("playwright_page")
        try:
            self.logger.info(f"Status {response.status} for {response.url}")
            if response.status != 200:
                self.logger.warning(f"Non-200 response: {response.text[:200]}")
                return

            article_title = response.css("title::text").get()
            
            # Determine if this is the index page
            is_index = response.url in self.start_urls
            content = extract_content(response.text, is_index)
            item = WebPageItem()
            item['url'] = response.url
            item['content'] = content
            item['timestamp'] = datetime.now(timezone("Asia/Chongqing")).strftime("%Y-%m-%d %H:%M:%S")
            item['title'] = article_title
            yield item

        finally:
            # # Close the Playwright page to free resources
            if page:
                await page.close()
                self.logger.info(f"Closed Playwright page for {response.url}") # Add info log
        
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
                    # "playwright": True,
                    # "playwright_include_page": True,
                    # "playwright_page_init_coroutine": self.setup_block_media,
                    "errback": self.errback,
                    'RETRY_TIMES': 3,  # Retry only 2 times
                    "RETRY_HTTP_CODES" : [500, 502, 503, 504, 408, 429]  # Include 429 for rate limiting
                },
            )

    async def errback(self, failure):
        page = failure.request.meta.get("playwright_page")
        try:
            self.logger.error(f"Request failed: {failure.request.url} - {failure.value}") # Log error value
        finally:
            if page:
                await page.close()
                self.logger.info(f"Closed Playwright page on error for {failure.request.url}") # Add info log
    
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