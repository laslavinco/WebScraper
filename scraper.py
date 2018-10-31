# -*- coding: utf-8 -*-
import sys
import os
import re
import time
import gzip
import shutil
import httplib
import urllib2
import logging
import StringIO
import urlparse
import requests
import multiprocessing
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.firefox.options import Options

options = Options()
options.add_argument('--headless')

FORMAT = " %(module)s %(filename)s %(lineno)d %(message)s"
# logging.basicConfig(filename='scraper.log', level=logging.INFO, format=FORMAT)
logging.basicConfig(level=logging.INFO, format=FORMAT)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
    'Accept-Encoding': 'none',
    'Accept-Language': 'en-US,en;q=0.8',
    'Connection': 'keep-alive'}

IMAGES = ('.JPG', '.JPEG' '.TIFF', '.GIF', '.BMP', '.PNG')
VIDEOS = ('.MP4', '.WEBM', '.MOV', '.3GP', '.FLV', '.GIF', '.AVI', '.SWF', '.ASF', '.MPEG', '.MPG', '.WMV', '.TS', '.M3U8', '.WEBM')


def timit(func):
    def call(*args, **kwargs):
        start_time = time.time()
        results = func(*args, **kwargs)
        logging.info(msg=(func.__name__, "time taken:", time.time() - start_time))
        return results

    call.__name__ = func.__name__
    return call


def class_timit(cls):
    for name, method in cls.__dict__.iteritems():
        if hasattr(method, '__call__'):
            setattr(cls, name, timit(method))

    return cls


@class_timit
class Downloader(object):
    def __init__(self):
        self._current_download_dir = "home/desktop/" if sys.platform not in ('win32') else "C:/temp/Downloads/"
        if not os.path.exists(self._current_download_dir):
            os.makedirs(self._current_download_dir)

    # todo: add threading support and option.

    def set_download_directory(self, download_path):
        if not os.path.exists(download_path):
            os.makedirs(download_path)
        self._current_download_dir = download_path

    def get_download_directory(self):
        if not self._current_download_dir:
            self.set_download_directory("C:/temp/")
        return self._current_download_dir

    def get_download_time(self):
        pass

    def download(self, overwrite=False, download_path=None):
        if not download_path:
            download_path = self.get_download_directory()
        url = self.url
        logging.info("Downloading %s .. at %s " % (url, download_path))
        if self.url_info is None:
            logging.error("URL {} is None skipping to next URL".format(self.url))
        logging.info(self.url_info)
        size = int(self.url_info['size'])
        raw_name = self.url_info['name']
        extension = self.url_info['extension']
        file_name = raw_name.replace('"', '') + extension
        file_path = download_path + file_name

        if size < 6000:
            logging.error('Media too small to download.')
            return

        if not overwrite and os.path.isfile(file_path):
            logging.info("The media already exists..")
            return

        if not self.is_video():
            self._download_static_item(file_path)
        else:
            self._download_buffer_item(file_path)

    def _download_static_item(self, file_path):
        req = urllib2.Request(self.url, None, HEADERS)
        try:
            with open(file_path, 'wb') as writer:

                writer.write(urllib2.urlopen(req).read())
                return True

        except Exception as error:
            logging.error(error)
            return False

    def _download_buffer_item(self, file_path):
        request = requests.get(self.url, stream=True)
        with open(file_path, 'wb') as writer:
            shutil.copyfileobj(request.raw, writer)


@class_timit
class URL(Downloader):
    def __init__(self, url):
        super(URL, self).__init__()
        if type(url) == URL:
            url = str(url.default_url)
        url = urllib2.unquote(url)
        self.default_url = url
        self.parsed_url = urlparse.urlparse(url.__str__())
        parsed_info = '{uri.scheme}://{uri.netloc}/'.format(uri=self.parsed_url)
        self.domain_name = parsed_info
        self.url = self._add_http(url.__str__())
        self.url_dict = {}
        self.url_info = {}
        logging.info(self.__repr__())
        self._validate_url()
        

    def __repr__(self):
        return "<URL %s> object" % self.url

    def __str__(self):
        return self.default_url

    def get_stripped_url(self):
        if self.default_url.count('https://') > 0:
            return self.default_url.split('https://')[-1]
        elif self.default_url.count('http://') > 0:
            return self.default_url.split('http://')[-1]
        else:
            return self.default_url

    def get_url_info(self):
        try:
            _request = urllib2.Request(self.url, headers=HEADERS)
            url_request = urllib2.urlopen(_request)
        except Exception as error:
            logging.info(error)
            logging.error(error)
            return None

        _extension = url_request.headers.get("Content-Type", "part")
        if ";" in _extension:
            search = re.search('[a-zA-Z0-9].*;', _extension)
            if not search:
                logging.info('Error finding extension for file {file}'.format(file=self.url))
                logging.error('Error finding extension for file {file}'.format(file=self.url))
                return None
            extension = '.'+search.group().split(';')[0].split('/')[-1]
        else:
            extension = "."+_extension.split('/')[-1]
        base_name = os.path.splitext(os.path.basename(self.url))[0] + extension

        name = url_request.headers.get("Etag", base_name)
        size = url_request.headers.get("Content-Length", "0")

        url_info = {"name": name, "extension": extension, "size": size}
        return url_info

    @staticmethod
    def check_image_exists(site_name, image_path):
        logging.info(site_name)
        conn = httplib.HTTPConnection(site_name)
        conn.request('HEAD', image_path)
        response = conn.getresponse()
        conn.close()
        return response.status == 200

    def _validate_url(self):
        if not self.url_info:
            self.url_info = self.get_url_info()
            if self.url_info is None:
                raise RuntimeError("Url {} is invalid".format(self.url))


    def scrape_url(self):
        request = urllib2.Request(self.default_url, None, HEADERS)
        url_data = urllib2.urlopen(request)

        if not url_data:
            raise RuntimeError("Cannot read the page")

        url_data = url_data.read()
        self.url_dict = urlparse.parse_qs(url_data)
        return url_data

    def is_image(self):
        is_image = True if [i for i in IMAGES if i.lower() in self.url_info['extension'].lower()] else False
        return is_image

    def is_video(self):
        is_video = True if [i for i in VIDEOS if i.lower() in self.url_info['extension'].lower()] else False
        return is_video

    @staticmethod
    def is_url(url):
        try:
            parsed_url = urlparse.urlparse(url)
            # request = urllib2.urlopen(url)
            return bool(parsed_url.scheme)
        except:
            return False

    def _add_http(self, url):
        if not url.startswith("http"):
            if self.domain_name not in url:
                url = self.domain_name + url
            else:
                url = "https://" + url
        return url


@class_timit
class Scraper(URL):
    def __init__(self, link, ajax=False, scroll_offset=1000, sleeper=3):
        super(Scraper, self).__init__(link)
        self.ajax = ajax
        if self.ajax:
            # self.app = webdriver.Firefox(options=options)
            self.app = webdriver.PhantomJS()
            self.app.get(self.url)
        self.image_tags = ['img', 'a', 'iframe']
        self.video_tags = ['video', 'videopv', 'a', 'iframe']
        self.getters = ['src', 'data-src', 'poster', 'href', 'source', 'data-original']
        self.links = []
        self.scroll_offset = scroll_offset
        self.sleeper = sleeper

    def _scroll_page(self):
        sources = []
        _position_history = []
        while True:
            self.app.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)
            scroll_height = self.app.execute_script("return document.body.scrollHeight;")
            current_height = self.app.execute_script("return window.pageYOffset;")
            time.sleep(self.sleeper)
            source = self.app.page_source
            logging.info((scroll_height, current_height))
            _position_history.append(current_height)
            if source:
                sources.append(source)
            logging.info(_position_history)
            if _position_history.count(current_height) > 2:
                break
        return sources

    def _move_pages(self, search_string):
        page_source = []

        try:
            click_button = self.app.find_element_by_link_text(search_string)
        except Exception as error:
            logging.error(error)
            return page_source

        while click_button:
            click_button.click()

            try:
                click_button = self.app.find_element_by_link_text(search_string)
            except Exception as error:
                logging.error(error)
                return page_source
            source = self.app.page_source
            if source and source not in page_source:
                page_source.append(source)

        return page_source

    def get_page_source(self, use_search_string=None):
        if self.ajax:
            if not use_search_string:
                page_data = self._scroll_page()
            else:
                page_data = self._move_pages(use_search_string)
            self.app.close()
        else:
            page_data = [self.scrape_url()]

        for data in page_data:
            soup = self.create_soup(data)
            if not soup:
                continue
            yield(soup)
        

    @staticmethod
    def create_soup(page_source):

        _soup_data = BeautifulSoup(page_source, "html.parser")
        if 'html' not in _soup_data.encode('utf-8'):
            page_data = StringIO.StringIO(page_source)
            zipped_data = gzip.GzipFile(fileobj=page_data)
            _soup_data = BeautifulSoup(zipped_data, "html.parser")

        return _soup_data

    def scrape_images(self, _soup_data):
        for tag in self.image_tags:
            images = self.get_urls(_soup_data, tag)
            for image in images:
                if not image or not image.is_image():
                    continue
                self.links.append(image)
        return self.links

    def scrape_videos(self, soup_data):
        for tag in self.video_tags:
            videos = self.get_urls(soup_data, tag)
            for video in videos:
                if not video or not video.is_video():
                    continue
                self.links.append(video)
        return self.links

    def scrape_links(self, soup_data, finder, getter):
        for tag in soup_data.find_all(finder):
            _link = tag.get(getter)
            if _link:
                try:
                    _link = URL(_link)
                except:
                    continue
                yield(_link)

    def validate_url(self, url_data):

        if url_data.count('http') > 1:
            return False

        if not self.is_url(url_data):
            return False

        if os.path.splitext(url_data)[-1] == '':
            return False

        return True

    def get_urls(self, soup_data, tag, skip_validation=False):
        _links = []
        for line in soup_data.find_all(tag):
            for get_type in self.getters:
                url_data = line.get(get_type)

                if not url_data:
                    continue

                if not url_data.startswith('http') or url_data.startswith('/'):
                    url_data = self.domain_name + url_data[1:]

                if not skip_validation:
                    if not self.validate_url(url_data):
                        continue

                try:
                    url_data = URL(url_data)
                except Exception as error:
                    logging.info(error)
                    continue

                if url_data not in _links:
                    _links.append(url_data)
                    self.links.append(url_data)
        return _links

    def scrape_urls(self):
        self.scrape_url()
        pass


"""
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


"""
