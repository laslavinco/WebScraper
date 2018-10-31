
Simple Usage:


    url = "http://www.ur_url.com"
    scrape = Scraper(url, ajax=True)
    data = scrape.get_page_source()
    for soup in data:
        for link in scrape.scrape_videos(soup):
            link.download()

Advanced Usage:

    url = "http://www.ur_url.com"
    scrape = Scraper(url, ajax=True)
    data = scrape.get_page_source(use_search_string="Next") # it will look for "Next" button on page and click it
    for soup in data:
        for link in scrape.scrape_videos(soup):
            link.download()

If you want to scrape recusrively:

    url = "http://www.ur_url.com"
    scrape = Scraper(url)
    data = scrape.get_page_source()
    for i in data:
        for link in scrape.scrape_links(i, "a", "href"):
            new_url = Scraper(link)
            page_src = new_url.get_page_source()
            for src in page_src:
                for image in new_url.scrape_images(src):
                    image.download()


