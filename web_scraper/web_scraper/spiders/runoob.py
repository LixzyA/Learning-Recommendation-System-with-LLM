import scrapy
from web_scraper.items import WebPageItem
from bs4 import BeautifulSoup
from datetime import datetime 
from pytz import timezone

def extract_content(html):
    soup = BeautifulSoup(html, 'html.parser')
    content_div = soup.find('div', {'class': 'article-intro', 'id': 'content'})
    
    for img in content_div.find_all('img'):
        img.decompose()
    
    for trybtn in content_div.find_all('a', {'class': 'tryitbtn'}):
        trybtn.decompose()
    
    for br in content_div.find_all('br'):
        br.decompose()
    
    for tag in content_div.find_all(style=True):
        del tag['style']
    
    return str(content_div.get_text()).strip()

class RunoobSpider(scrapy.Spider):
    name = "runoob"
    allowed_domains = ["runoob.com"]
    start_urls = [
        "https://www.runoob.com/css3/css3-tutorial.html",
        "https://www.runoob.com/tailwindcss/tailwindcss-tutorial.html",
        "https://www.runoob.com/bootstrap5/bootstrap5-tutorial.html",
        "https://www.runoob.com/bootstrap4/bootstrap4-tutorial.html",
        "https://www.runoob.com/html/html5-intro.html",
        "https://www.runoob.com/jquery/jquery-tutorial.html",
        "https://www.runoob.com/react/react-tutorial.html",
        "https://www.runoob.com/nodejs/nodejs-tutorial.html",
        "https://www.runoob.com/python3/python3-tutorial.html",
        "https://www.runoob.com/linux/linux-tutorial.html",
        "https://www.runoob.com/docker/docker-tutorial.html",
        "https://www.runoob.com/django/django-tutorial.html",
        "https://www.runoob.com/mongodb/mongodb-tutorial.html",
        "https://www.runoob.com/redis/redis-tutorial.html",
        "https://www.runoob.com/postgresql/postgresql-tutorial.html",
        "https://www.runoob.com/http/http-tutorial.html",
        "https://www.runoob.com/ollama/ollama-tutorial.html",
        "https://www.runoob.com/data-structures/data-structures-tutorial.html"

        ]
    custom_settings = {
        'DEPTH_LIMIT': 5,
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
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

        article_title = response.css("title::text").get()
        content = extract_content(response.text)
        if content == None:
            self.logger.debug(f"Skipping {response.url} - Missing required data")
            return
        
        item = WebPageItem()
        item['title'] = article_title
        item['url'] = response.url
        item['content'] = content
        item['timestamp'] = datetime.now(timezone("Asia/Chongqing")).strftime("%Y-%m-%d %H:%M:%S")
        item['source'] = 'runoob.com'

        yield item

        if response.meta.get("is_start_url"):
            links = response.css("div#leftcolumn>a::attr(href)").getall()
            for link in links:
                yield response.follow(link, callback = self.parse)  


        

