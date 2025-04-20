import scrapy
from web_scraper.items import WebPageItem
from bs4 import BeautifulSoup
from datetime import datetime 
from pytz import timezone

def clean_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    
    for img in soup.find_all('img'):
        img.decompose()
    
    social_domains = ['weibo.com', 'github.com', 'zhihu.com', 'twitter.com']
    for a in soup.find_all('a', href=True):
        if any(domain in a['href'] for domain in social_domains):
            a.decompose()
    
    for nav in soup.select('div#gsi-chapter-prev-next'):
        nav.decompose()
    
    for svg in soup.find_all('svg'):
        svg.decompose()
    
    cleaned_text = '\n'.join(
        line.strip() for line in soup.get_text().split('\n') 
        if line.strip()
    )
    return cleaned_text


class LiaoxuefengSpider(scrapy.Spider):
    name = "liaoxuefeng"
    allowed_domains = ["liaoxuefeng.com"]
    start_urls = ["https://liaoxuefeng.com"]

    custom_settings = {
        'DEPTH_LIMIT': 0,
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
    }

    def parse(self, response):
        if '/blogs' in response.url or '.zip' in response.url:
            self.logger.debug(f"Skipping {response.url}")
            return
        article_title = response.css("title::text").get()
        content = clean_html(response.text)

        item = WebPageItem()
        item['title'] = article_title
        item['url'] = response.url
        item['content'] = content
        item['timestamp'] = datetime.now(timezone("Asia/Chongqing")).strftime("%Y-%m-%d %H:%M:%S")
        item['source'] = 'liaoxuefeng.com'

        yield item

        links = response.css("a::attr(href)").getall()
        for link in links:
            if '/blogs' not in link:
                yield response.follow(link, callback = self.parse)


