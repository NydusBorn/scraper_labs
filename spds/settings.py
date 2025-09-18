# Scrapy settings for spds project
#
# For simplicity, this file contains only settings considered important or
# commonly used. You can find more settings consulting the documentation:
#
#     https://docs.scrapy.org/en/latest/topics/settings.html
#     https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
#     https://docs.scrapy.org/en/latest/topics/spider-middleware.html
import json

import requests

BOT_NAME = "spds"

SPIDER_MODULES = ["spds.spiders"]
NEWSPIDER_MODULE = "spds.spiders"

ADDONS = {}


# Crawl responsibly by identifying yourself (and your website) on the user-agent
# USER_AGENT = "spds (+http://www.yourdomain.com)"

# Obey robots.txt rules
ROBOTSTXT_OBEY = False

# Concurrency and throttling settings
# CONCURRENT_REQUESTS = 1
# CONCURRENT_REQUESTS_PER_DOMAIN = 1
DOWNLOAD_DELAY = 10

# Disable cookies (enabled by default)
# COOKIES_ENABLED = False

# Disable Telnet Console (enabled by default)
# TELNETCONSOLE_ENABLED = False

# Override the default request headers:
# DEFAULT_REQUEST_HEADERS = {
#     "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0",
#     "sec-ch-ua": '"Chromium";v="140", "Not=A?Brand";v="24", "Microsoft Edge";v="140"',
#     "referer": "https://otzovik.com/review_14966907.html?&capt4a=4331758227365273",
#     "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
#     "accept-encoding": "gzip, deflate, br, zstd",
#     "accept-language": "en-US,en;q=0.9,en-GB;q=0.8,ru;q=0.7",
#     "cache-control": "max-age=0",
#     "priority": "u=0, i",
#     "sec-ch-ua-mobile": "?0",
#     "sec-ch-ua-platform": '"Linux"',
#     "sec-fetch-dest": "document",
#     "sec-fetch-mode": "navigate",
#     "sec-fetch-site": "same-origin",
#     "sec-fetch-user": "?1",
#     "upgrade-insecure-requests": "1",
#     "sec-gpc": "1",
#     "cookies": "refreg=1758227030~https%3A%2F%2Fotzovik.com%2Freview_14966907.html%3F%26capt4a%3D5761758226802204; ssid=1988765208; ownerid=d5d0ff64c6a7cfa1c4680795cea6cd; last_login_fail=83d1caaf7a40e773a57db95fed628907; referal=1; ROBINBOBIN=cb6766e41c9b788abd51e14f81"
# }

# Enable or disable spider middlewares
# See https://docs.scrapy.org/en/latest/topics/spider-middleware.html
# SPIDER_MIDDLEWARES = {
#    "spds.middlewares.SpdsSpiderMiddleware": 543,
# }

# ts_file = open("../L1/proxies.txt").read()
# ROTATING_PROXY_LIST = [x for x in ts_file.split("\n")]
#
# ROTATING_PROXY_PAGE_RETRY_TIMES = 30000
# ROTATING_PROXY_BACKOFF_BASE = 3600
# ROTATING_PROXY_BACKOFF_CAP = 3600
#
# DOWNLOAD_TIMEOUT = 5

# Enable or disable downloader middlewares
# See https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
# DOWNLOADER_MIDDLEWARES = {
#     'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': None,
#     'scrapy.downloadermiddlewares.retry.RetryMiddleware': None,
#     'rotating_proxies.middlewares.RotatingProxyMiddleware': 610,
#     'rotating_proxies.middlewares.BanDetectionMiddleware': 620,
#     'scrapy_ua_rotator.middleware.RandomUserAgentMiddleware': 400,
#     'scrapy_ua_rotator.middleware.RetryUserAgentMiddleware': 550,
# }
#
# USERAGENT_PROVIDERS = [
#     'scrapy_ua_rotator.providers.FakeUserAgentProvider',  # Primary provider using the fake-useragent library
#     'scrapy_ua_rotator.providers.FakerProvider',          # Fallback provider that generates synthetic UAs via Faker
#     'scrapy_ua_rotator.providers.FixedUserAgentProvider', # Final fallback: uses the static USER_AGENT setting
# ]

# Enable or disable extensions
# See https://docs.scrapy.org/en/latest/topics/extensions.html
# EXTENSIONS = {
#    "scrapy.extensions.telnet.TelnetConsole": None,
# }

# Configure item pipelines
# See https://docs.scrapy.org/en/latest/topics/item-pipeline.html
# ITEM_PIPELINES = {
#    "spds.pipelines.SpdsPipeline": 300,
# }

# Enable and configure the AutoThrottle extension (disabled by default)
# See https://docs.scrapy.org/en/latest/topics/autothrottle.html
# AUTOTHROTTLE_ENABLED = True
# The initial download delay
# AUTOTHROTTLE_START_DELAY = 0.2
# The maximum download delay to be set in case of high latencies
# AUTOTHROTTLE_MAX_DELAY = 2
# The average number of requests Scrapy should be sending in parallel to
# each remote server
# AUTOTHROTTLE_TARGET_CONCURRENCY = 5.0
# Enable showing throttling stats for every response received:
# AUTOTHROTTLE_DEBUG = False

# Enable and configure HTTP caching (disabled by default)
# See https://docs.scrapy.org/en/latest/topics/downloader-middleware.html#httpcache-middleware-settings
HTTPCACHE_ENABLED = True
HTTPCACHE_EXPIRATION_SECS = 0
HTTPCACHE_DIR = "httpcache"
HTTPCACHE_IGNORE_HTTP_CODES = []
HTTPCACHE_STORAGE = "scrapy.extensions.httpcache.FilesystemCacheStorage"

# Set settings whose default value is deprecated to a future-proof value
FEED_EXPORT_ENCODING = "utf-8"
