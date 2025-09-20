import scrapy
import scrapy.crawler
import scrapy.utils.project
import spds.spiders.rev

def crawl():

    process = scrapy.crawler.CrawlerProcess(scrapy.utils.project.get_project_settings())
    
    process.crawl(spds.spiders.rev.review_spider)
    process.start()
    
if __name__ == "__main__":
    crawl()