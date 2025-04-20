import scrapy
from web_scraper.items import WebPageItem
from bs4 import BeautifulSoup
from datetime import datetime 
from pytz import timezone

def clean_article(html):
    soup = BeautifulSoup(html, 'html.parser')
    article = soup.find('article', class_='content')
    
    if not article:
        return None
    
    # Remove unwanted sections
    for element in article.select('''
        script, style, p>a,
        .three_dot_dropdown, 
        .last_updated_parent, 
        .article-title, 
        .three_dot_dropdown_content,
        .article-pgnavi,
        .more-info,
        .improved,
        #video-tab-content,
        #AP_G4GR_6,
        .article_bottom_text,
        .article_bottom_text ~ *
    '''):
        element.decompose()
    
    # Remove all elements after article_bottom_text
    bottom_text = article.find('div', class_='article_bottom_text')
    if bottom_text:
        for element in bottom_text.find_all_next():
            element.decompose()
    
    # Get clean text content
    text_content = []
    for element in article.find_all(['p', 'li', 'pre', 'h3', 'h2', 'h1']):
        text = element.get_text(strip=True)
        if text:
            text_content.append(text)
    
    # Combine and clean text
    clean_text = '\n'.join(text_content)
    
    # Remove empty lines and excessive whitespace
    clean_text = '\n'.join([line.strip() for line in clean_text.split('\n') if line.strip()])
    
    return clean_text

class geeksforgeeks(scrapy.Spider):
    name = 'geeksforgeeks'
    allowed_domains = ['geeksforgeeks.org']
    start_urls = [
                'https://www.geeksforgeeks.org/introduction-to-redis-server/', 
                'https://www.geeksforgeeks.org/machine-learning/',
                'https://www.geeksforgeeks.org/artificial-intelligence/', 
                'https://www.geeksforgeeks.org/python-programming-language-tutorial/',
                'https://www.geeksforgeeks.org/data-science-with-python-tutorial/',
                'https://www.geeksforgeeks.org/devops-tutorial/',
                'https://www.geeksforgeeks.org/dsa-tutorial-learn-data-structures-and-algorithms/',
                'https://www.geeksforgeeks.org/ai-ml-ds/',
                'https://www.geeksforgeeks.org/web-development/',
                'https://www.geeksforgeeks.org/system-design-tutorial/'
                  ]
    
    custom_settings = {
        'DEPTH_LIMIT': 5,
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
    }

    def parse(self, response):
        article_title = response.css("div.article-title>h1::text").get()
        content = clean_article(response.text)
        if content == None:
            self.logger.debug(f"Skipping {response.url} - Missing required data")
            return

        item = WebPageItem()
        item['title'] = article_title
        item['url'] = response.url
        item['content'] = content
        item['timestamp'] = datetime.now(timezone("Asia/Chongqing")).strftime("%Y-%m-%d %H:%M:%S")
        item['source'] = 'geeksforgeeks.org'
        
        yield item

        # Get the article selector
        article_selector = response.css("article.content")
        # Only follow links if article exists
        if article_selector:
            # Extract links FROM THE ARTICLE CONTENT
            for link in article_selector.css('a::attr(href)').getall():
                if '#' in link:
                # Link is to a position on the current page, skip it
                    continue

                # Otherwise, it's a link to another page
                self.log(f'Link to another page: {link}')
                yield response.follow(link, callback=self.parse)
                    
        