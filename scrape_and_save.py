from bs4 import BeautifulSoup
from selenium import webdriver
import requests
import logging
from model import Model

"""
This process scrapes the current steal off of Steep and Cheap and stuffs it into the deals table in local MySQL.
"""

logging.basicConfig(filename='scrape_and_save.log', level=logging.DEBUG)


def scrape_current_steal_url():
    # using selenium here to render javascript automatically (using phantomjs for headlessness)
    logging.info("Scraping the current steal URL...")
    driver = None
    try:
        driver = webdriver.PhantomJS(executable_path="/usr/local/bin/phantomjs")
        driver.get("http://www.steepandcheap.com")
        html = driver.page_source.encode('utf-8')
        for line in html.splitlines():
            if "Current Steal" in line:
                soup = BeautifulSoup(line, "html.parser")
                for aref in soup.find_all('a', {"data-id": 5}):
                    result = "http://www.steepandcheap.com" + aref["href"]
                    logging.info("Successfully scraped current steal URL: " + result)
                    return result
    except Exception as e:
        logging.error("An exception occurred scraping the current steal URL: ")
        logging.error(e)
        return None
    finally:
        if driver is not None:
            logging.info("Shutting down selenium driver")
            driver.close()
            driver.quit()
            logging.info("Selenium shutdown successful")


def parse_current_steal_product_name_and_description(url):
    logging.info("Fetching and parsing current steal name and description...")
    try:
        logging.info("Fetching the page...")
        resp = requests.get(url)
        soup = BeautifulSoup(resp.text.encode('utf-8'), "html.parser")
        logging.info("Parsing out the page title as the product name...")
        title = soup.title.string.split("|")[0].encode('utf-8')
        logging.info("Parsing out the product description...")
        product_description = ""
        for div in soup.find_all('div', {'class': 'prod-desc'}):
            product_description += div.text
        for ul in soup.find_all('ul', {'class': 'product-bulletpoints'}):
            for li in ul.find_all('li'):
                product_description += " " + li.text + ". "
        product_description = product_description.encode('utf-8').replace('\n', "")
        return title, product_description
    except Exception as e:
        logging.error("An exception occurred fetching/parsing current steal name and description: ")
        logging.error(e)
        return None


def main():
    # returns 0 on success, 1 on failure
    url = scrape_current_steal_url()
    if url is not None:
        title, prod_desc = parse_current_steal_product_name_and_description(scrape_current_steal_url())
        if title is not None and prod_desc is not None:
            model = Model()
            model.save_current_steal(title, prod_desc)
            logging.info("Save went ok, returning 0 in main")
            return 0
    return 1


if __name__ == "__main__":
    exit(main())
