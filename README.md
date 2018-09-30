# WebScraper with ajax support.

___usage___

url = "http://www.ur_url.com"
scrape = Scraper(url, ajax=True)
data = scrape.get_page_source()
for soup in data:
    for link in scrape.scrape_videos(soup):
        link.download()
