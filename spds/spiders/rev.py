from codecs import ignore_errors

import scrapy

import os
import shutil
import re
import threading
import json

base_url = "https://otzovik.com/reviews/online_fashion_shop_wildberries_ru/"
DATA_DIR = os.environ.get("INTERMEDIATE_DATASET_DIR", "intermediate_dataset")
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR, exist_ok=True)
downloaded_reviews = {x.split(".")[0] for x in os.listdir(DATA_DIR)}


class review_spider(scrapy.Spider):
    name = "review_spider"
    start_urls = [base_url]

    def parse(self, response):
        total_pages = int(
            response.css("a[class*='last']::attr(href)").get().split("/")[-2]
        )
        for page in range(1, total_pages + 1):
            url = f"https://otzovik.com/reviews/online_fashion_shop_wildberries_ru/{page}/"
            yield scrapy.Request(
                url,
                callback=self.parse_page,
            )

    def parse_page(self, response: scrapy.http.Response):
        review_bases = response.xpath("//div[@itemprop='review']")
        for review in review_bases:
            full_review_url = review.css("a.review-title::attr(href)").get()
            if full_review_url:
                yield scrapy.Request(
                    f"https://otzovik.com{full_review_url}", callback=self.parse_review
                )

    def parse_review(self, response: scrapy.http.Response):
        stars_raw = response.css(
            "html > body > div:nth-of-type(2) > div > div > div > div > div:nth-of-type(4) > div:nth-of-type(1) > div:nth-of-type(1) > div:nth-of-type(2) > div:nth-of-type(1) > div:nth-of-type(1) > span"
        ).get()
        stars = re.findall(r">(.*?)</", stars_raw)[0]
        title_raw = response.css("span[class='summary']").get()
        title = re.findall(r">(.*?)</", title_raw)[0]
        review_plus_raw = response.css("div[class='review-plus']").get()
        review_plus = re.findall(r"а:</b>(.*?)</div", review_plus_raw)[0]
        review_minus_raw = response.css("div[class='review-minus']").get()
        review_minus = re.findall(r"и:</b>(.*?)</div", review_minus_raw)[0]
        review_descr_raw = response.css("div[itemprop='description']").get()
        review_descr = ""
        writing = False
        while review_descr_raw != "":
            if review_descr_raw.startswith('tion">'):
                writing = True
                review_descr_raw = review_descr_raw[6:]
            elif review_descr_raw.startswith("<br>"):
                review_descr += "\n"
                review_descr_raw = review_descr_raw[4:]
            elif review_descr_raw.startswith("</script>\n</div></div>"):
                writing = True
                review_descr_raw = review_descr_raw[21:]
            elif review_descr_raw.startswith("</p>"):
                writing = True
                review_descr_raw = review_descr_raw[4:]
            elif review_descr_raw.startswith("<"):
                writing = False
                review_descr_raw = review_descr_raw[1:]
            elif writing:
                review_descr += review_descr_raw[0]
                review_descr_raw = review_descr_raw[1:]
            else:
                review_descr_raw = review_descr_raw[1:]
        table_props_raw = response.css("table > tr")
        table_prop_keys = []
        table_prop_values = []
        for prop in table_props_raw:
            table_prop_keys.append(prop.css("td:nth-of-type(1)::text").get())
            table_prop_values.append(prop.css("td:nth-of-type(2)::text").get())
        table_props = dict(zip(table_prop_keys, table_prop_values))
        try:
            year_usage = table_props["Год пользования услугами"]
        except:
            year_usage = ""
        try:
            recommendation = table_props["Рекомендую друзьям"]
        except:
            recommendation = ""
        time_usage_raw = response.css("span[class='owning-time']").get()
        if time_usage_raw:
            time_usage = re.findall(r">(.*?)</", time_usage_raw)[0]
        else:
            time_usage = ""
        try:
            price = table_props["Стоимость"]
        except:
            price = ""
        date_posted_raw = response.css("span[class^='review-postdate'] span").get()
        date_posted = re.findall(r">(.*?)</", date_posted_raw)[0]
        likes_raw = response.css("span[class*='review-yes'] span").get()
        likes = re.findall(r">(.*?)</", likes_raw)[0]
        comments_raw = response.css(
            "a[class='review-btn review-comments tooltip-top'] span"
        ).get()
        comments = re.findall(r">(.*?)</", comments_raw)[0]
        review = {}
        review["title"] = title
        review["stars"] = stars
        review["review_plus"] = review_plus
        review["review_minus"] = review_minus
        review["review_descr"] = review_descr
        review["year_usage"] = year_usage
        review["recommendation"] = recommendation
        review["time_usage"] = time_usage
        review["price"] = price
        review["date_posted"] = date_posted
        review["likes"] = likes
        review["comments"] = comments
        if not downloaded_reviews.__contains__(
            response.url.split("/")[-1].split(".")[0]
        ):
            print(review)
            with open(
                os.path.join(DATA_DIR, f"{response.url.split('/')[-1].split('.')[0]}.json"),
                "w",
            ) as f:
                f.write(json.dumps(review, ensure_ascii=False, indent=2))
            downloaded_reviews.add(response.url.split("/")[-1].split(".")[0])
