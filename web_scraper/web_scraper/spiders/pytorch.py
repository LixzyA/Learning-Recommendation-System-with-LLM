import scrapy
from scrapy import Selector
from web_scraper.items import WebPageItem
from datetime import datetime
from bs4 import BeautifulSoup

def clean_pytorch_article(html_content: str) -> str:
    """Extracts cleaned content from PyTorch tutorial HTML."""
    soup = BeautifulSoup(html_content, "html.parser")
    article = soup.find("article", class_="pytorch-article")
    
    if not article:
        return ""
    
    # Remove download note box
    if (download_note := article.find("div", class_="sphx-glr-download-link-note")):
        download_note.decompose()
    
    # Remove navigation links bar
    if (nav_bar := article.find("p", class_="sphx-glr-example-title")):
        nav_bar.decompose()
    
    # Remove script execution timestamps and footer
    for element in article.find_all(class_=["sphx-glr-timing", "sphx-glr-footer"]):
        element.decompose()
    
    # Clean preserved code blocks
    for pre in article.find_all("pre"):
        pre.string = pre.get_text().strip()  # Remove HTML entities but keep code formatting
    
    # Get final text with structured newlines
    return article.get_text(separator="\n", strip=False).strip()

class PytorchSpider(scrapy.Spider):
    name = "pytorch"
    allowed_domains = ["pytorch.org", "pytorch.ac.cn"]
    start_urls = [
        "https://pytorch.org/tutorials/index.html",
        "https://pytorch.ac.cn/tutorials/",
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
                },
                callback=self.parse
            )

    def parse(self, response):
        
        if response.meta.get("is_start_url"):
            if any(link in response.url for link in ("pytorch.org", "pytorch.ac.cn")):
                links = response.css("li.toctree-l1 > a::attr(href), li.toctree-l2 > a::attr(href)").getall()

            for link in links:
                yield response.follow(link, callback = self.parse)            

        else: # Not in start urls
            article_title = response.css("title::text").get()
            content = clean_pytorch_article(response.text)

            item = WebPageItem()
            item['title'] = article_title
            item['content'] = content
            item['url'] = response.url
            item['timestamp'] = datetime.now("Asia/Chongqing").strftime("%Y-%m-%d %H:%M:%S")

            yield item
        
