import scrapy
from web_scraper.items import WebPageItem
from datetime import datetime
from bs4 import BeautifulSoup
from pytz import timezone

def extract_content_text(html):
    soup = BeautifulSoup(html, 'html.parser')
    main_content = soup.find('div', id='main')
    
    if not main_content:
        return ""
    
    # Remove unwanted elements
    for element in main_content.select('#mainLeaderboard, #midcontentadcontainer, #user-profile-bottom-wrapper, script, style'):
        element.decompose()
    
    # Get all text content with proper spacing
    text_content = []
    
    for element in main_content.find_all(text=True):
        if element.parent.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'li', 'td', 'th']:
            text = element.strip()
            if text:
                text_content.append(text)
    
    # Combine and clean text
    full_text = '\n'.join(text_content)
    
    # Remove excessive empty lines
    full_text = '\n'.join([line.strip() for line in full_text.split('\n') if line.strip()])
    
    return full_text

class W3schoolsSpider(scrapy.Spider):
    name = "w3schools"
    allowed_domains = ["w3schools.com"]
    start_urls = [
                    "https://www.w3schools.com/ai/default.asp",
                    "https://www.w3schools.com/mysql/default.asp",
                    "https://www.w3schools.com/datascience/default.asp", 
                    "https://www.w3schools.com/gen_ai/index.php",
                    "https://www.w3schools.com/python/default.asp",
                    "https://www.w3schools.com/js/default.asp",
                    "https://www.w3schools.com/css/default.asp",
                    "https://www.w3schools.com/css/default.asp",
                    "https://www.w3schools.com/c/index.php",
                    "https://www.w3schools.com/java/default.asp",
                    "https://www.w3schools.com/php/default.asp",
                    "https://www.w3schools.com/howto/default.asp",
                    "https://www.w3schools.com/bootstrap5/index.php",
                    "https://www.w3schools.com/react/default.asp",
                    "https://www.w3schools.com/python/numpy/default.asp",
                    "https://www.w3schools.com/django/index.php",
                    "https://www.w3schools.com/xml/default.asp",
                    "https://www.w3schools.com/python/numpy/default.asp",
                    "https://www.w3schools.com/python/pandas/default.asp",
                    "https://www.w3schools.com/git/default.asp",
                    "https://www.w3schools.com/postgresql/index.php",
                    "https://www.w3schools.com/programming/index.php",
                    "https://www.w3schools.com/python/scipy/index.php",
                    "https://www.w3schools.com/mongodb/index.php",
                    "https://www.w3schools.com/bootstrap/default.asp",
                    "https://www.w3schools.com/bootstrap4/default.asp",
                    "https://www.w3schools.com/jquery/default.asp",
                  ]

    custom_settings = {
        'DEPTH_LIMIT': 0,
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
    }

    def parse(self, response):

        article_title = response.css("h1 ::text").getall()
        article_title = ' '.join(article_title)
        if '/' in article_title:
            article_title = article_title.replace("/", "_")

        content = extract_content_text(response.text)

        item = WebPageItem()
        item['url'] = response.url
        item['content'] = content
        item['timestamp'] = datetime.now(timezone("Asia/Chongqing")).strftime("%Y-%m-%d %H:%M:%S")
        item['title'] = article_title
        
        yield item

        url = response.url.split("/")[-1]
        left_menu = response.css("div#leftmenuinnerinner")
        if left_menu:
            links = left_menu.css('a::attr(href)').getall()
            if not links:
                self.logger.info("No links found in the left menu.")
            for link in links:
                if link == url:
                    continue
                # self.log(f'Link to another page: {link}')
                yield response.follow(link, callback=self.parse)
        else:
            self.logger.info("No left menu found.")
