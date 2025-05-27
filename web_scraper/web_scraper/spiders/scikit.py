import scrapy
from web_scraper.items import WebPageItem
from bs4 import BeautifulSoup
import re
from datetime import datetime 

def clean_html_content(html_content):
    """
    Extracts and cleans text content from HTML, removing images, hyperlink markers, 
    and unnecessary whitespace.
    """
    # Parse HTML content
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Remove header navigation links (e.g., the '#' symbols)
    for link in soup.find_all('a', class_='headerlink'):
        link.decompose()
        
    # Remove images and their parent links (if links only contain images)
    for img in soup.find_all('img'):
        img.decompose()
    for link in soup.find_all('a'):
        if len(link.contents) == 0 and not link.text.strip():
            link.decompose()
    
    # Extract text and clean formatting
    text = soup.get_text(separator='\n', strip=False)
    
    # Clean excessive whitespace and newlines
    text = re.sub(r'\n{3,}', '\n\n', text)  # Replace 3+ newlines with two
    text = re.sub(r'[ \t]{2,}', ' ', text)  # Replace multiple spaces/tabs with one
    return text.strip()

class ScikitSpider(scrapy.Spider):
    name = "scikit"
    allowed_domains = ["scikit-learn.org"]
    start_urls = ["https://scikit-learn.org/stable/user_guide.html"]
    custom_settings = {
        'DEPTH_LIMIT': 0,
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
        'HTTPCACHE_ENABLED': True
    }

    def parse(self, response):
        if response.url in self.start_urls:
            links = response.css("div.toctree-wrapper a::attr(href)").getall()
            for link in links:
                self.log(f'Link to another page: {link}')
                # if "https://scikit-learn.org/stable" not in link:
                #     link = "https://scikit-learn.org/stable/" + link
                yield response.follow(link, callback= self.parse)
        else:
            article_title = response.css("title::text").get()
            content = clean_html_content(response.text)

            item = WebPageItem()
            item['url'] = response.url
            item['content'] = content
            item['timestamp'] = datetime.now("Asia/Chongqing").strftime("%Y-%m-%d %H:%M:%S")
            item['title'] = article_title

            self.logger.info(f"Processed {response.url}, queue size: {len(self.crawler.engine.slot.scheduler)}")

            yield item



        
