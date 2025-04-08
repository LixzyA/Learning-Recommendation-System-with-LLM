import scrapy
from web_scraper.items import WebPageItem
from datetime import datetime
from bs4 import BeautifulSoup

def extract_content(html: str):
    """
    Extracts content from the given HTML, handling content pages.

    Args:
        html(str) : The HTML content as a string
    Returns:
        content(str): The clean content of the HTML

    """
    soup = BeautifulSoup(html, 'html.parser')
    content_div = soup.find('div', class_='devsite-article-body')
    if not content_div:
        return ''
    
    # Remove the empty div with id 'top' if present
    top_div = content_div.find('div', id='top')
    if top_div:
        top_div.decompose()

    table_wrapper = content_div.find("div", _class = "devsite-table-wrapper")
    if table_wrapper:
        table_wrapper.decompose()
    
    # Extract text content (without HTML tags)
    text_content = content_div.get_text(separator='\n', strip=True)
    return text_content

class TensorflowSpider(scrapy.Spider):
    name = "tensorflow"
    allowed_domains = ["tensorflow.org"]
    start_urls = [
                # "https://www.tensorflow.org/api_docs/python/tf"
                #  ,"https://www.tensorflow.org/api_docs/cc"
                #   "https://www.tensorflow.org/tutorials",
                #   "https://www.tensorflow.org/guide",
                #   "https://www.tensorflow.org/tfx/tutorials",
                #   "https://www.tensorflow.org/tfx/guide"
                  "https://www.tensorflow.org/tutorials?hl=zh-cn",
                  "https://www.tensorflow.org/guide?hl=zh-cn",
                  "https://www.tensorflow.org/tfx/tutorials?hl=zh-cn",
                  "https://www.tensorflow.org/tfx/guide?hl=zh-cn"
                  ]
    
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
                    'chinese': False,
                },
                callback=self.parse
            )

    def parse(self, response):
        if response.meta.get('is_start_url'):
            if any(sub in response.url for sub in ("python", "tfx", "guide", "tutorials")) :
                links = response.css("ul[menu='_book']>li.devsite-nav-item a::attr(href)").getall()
            elif "/cc" in response.url: #C++
                links = response.css("td>a::attr(href)").getall()
            
            if response.meta.get("chinese"):
                links = [f'{link}?hl=zh-cn' for link in links]
            
            
            for link in links:
                yield response.follow(
                link,
                callback=self.parse)
        
        else:
            self.logger.info(f"Processed {response.url}, queue size: {len(self.crawler.engine.slot.scheduler)}")
            
            article_title = response.css("title::text").get()
            content = extract_content(response.text)
            item = WebPageItem()
            item['url'] = response.url
            item['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            item['content'] = extract_content(response.text)
            item['title'] = article_title

            yield item