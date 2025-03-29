# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html



# class HtmlSavePipeline:
#     def process_item(self, item, spider):

#         # Get title from item (adapt to your field name)
#         raw_title = item.get('title', 'untitled')
        
#         # Create unique identifier from URL (prevens title duplicates)
#         url_hash = hashlib.md5(item['url'].encode()).hexdigest()[:8]  # 8-char hash
        
#         # Slugify the title
#         clean_title = slugify(raw_title)

#         # Get domain for organization
#         domain = urlparse(item['url']).netloc.replace('www.', '').split('.')[0]

#         # Final filename format: domain_hash_title.html
#         filename = f"{domain}_{url_hash}_{clean_title}.html"

#         # Create directory structure
#         path = os.path.join('webpages', os.path.dirname(filename))
#         os.makedirs(path, exist_ok=True)
        
#         # Save HTML
#         with open(os.path.join('webpages', filename), 'w', encoding='utf-8') as f:
#             f.write(item['html'])
        
#         return item

# class AssetPipeline(FilesPipeline):
#     def file_path(self, request, response=None, info=None, *, item=None):
#         # Organize assets by type and original path
#         return f"assets/{request.url.split('://')[1]}"
    


