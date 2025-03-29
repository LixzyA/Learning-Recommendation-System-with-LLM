# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy

class WebPageItem(scrapy.Item):
    url = scrapy.Field()
    content = scrapy.Field()
    timestamp = scrapy.Field()
    title = scrapy.Field()
    source= scrapy.Field()
    section_titles = scrapy.Field()

    def __repr__(self):
        # Exclude 'content' from the logged output
        filtered_data = {k: v for k, v in self.items() if k != 'content'}
        # return super(WebPageItem, self).__repr__(filtered_data)
        return f"<{self.__class__.__name__} {filtered_data!r}>"
