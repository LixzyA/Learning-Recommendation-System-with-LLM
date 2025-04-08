import scrapy
from web_scraper.items import WebPageItem
from datetime import datetime
from bs4 import BeautifulSoup
import re

def clean_html(html):
     # Parse the HTML using BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    
    # Find the main content section
    main_div = soup.find('div', {'role': 'main'})
    if not main_div:
        return ""
    
    # Get all text content
    text_content = main_div.get_text(separator='\n', strip=True)
    
    # Clean up excessive whitespace and newlines
    cleaned_content = re.sub(r'\n\s*\n', '\n\n', text_content)
    
    return cleaned_content.strip()

class PytorchExtraSpider(scrapy.Spider):
    name = "pytorch-extra"
    allowed_domains = ["pytorch-cn.readthedocs.io"]
    start_urls = ["https://pytorch-cn.readthedocs.io/zh/latest/"]

    custom_settings = {
        'DEPTH_LIMIT': 0,
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                meta={
                    'is_start_url': True,  # Flag to identify start URLs
                },
                callback=self.parse
            )

    def parse(self, response):

        if response.meta.get("is_start_url"):
            section = response.css("div.section")
            links = section.css("li>a::attr(href)").getall()
            for link in links:
                yield response.follow(link, callback = self.parse)

        article_title = response.css("title::text").get()
        content = clean_html(response.text)

        item = WebPageItem()
        item['title'] = article_title
        item['content'] = content
        item['url'] = response.url
        item['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        yield item

        
        

