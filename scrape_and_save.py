from bs4 import BeautifulSoup
import requests
import logging
from model import Model
import json
import os, signal

"""
This process scrapes the current steal off of Steep and Cheap and stuffs it into the deals table in local MySQL.
"""

logging.basicConfig(filename='scrape_and_save.log', level=logging.DEBUG)


def get_current_steal_url():
    url = None
    try:
        resp = requests.get("https://www.steepandcheap.com/data/odat.json")
        assert resp.status_code == 200, "did not get a 200 back from odat.json url"
        jobj = json.loads(resp.text)
        url = "https://www.steepandcheap.com" + jobj["url"]
        logging.info("current steal url: %s" % url)
    except Exception as e:
        print e.message
        logging.exception(e)
    finally:
        return url


def scrape_current_steal_product_name_and_description(url):
    logging.info("Fetching and parsing current steal name and description...")
    try:
        logging.info("Fetching the page at: %s" % str(url))
        resp = requests.get(url)
        soup = BeautifulSoup(resp.text.encode('utf-8'), "html.parser")
        logging.info("Parsing out the page title as the product name...")
        title = soup.title.string.split("|")[0].encode('ascii', 'ignore')
        logging.info("Parsing out the product description...")
        product_description = ""
        for div in soup.find_all('div', {'class': 'prod-desc'}):
            product_description += div.text
        for ul in soup.find_all('ul', {'class': 'product-bulletpoints'}):
            for li in ul.find_all('li'):
                product_description += " " + li.text + ". "
        product_description = product_description.encode('ascii', 'ignore').replace('\n', "")
        return title, product_description
    except Exception as e:
        logging.error("An exception occurred fetching/parsing current steal name and description: ")
        logging.error(e)
        return None


def main():
    url = get_current_steal_url()
    if url is not None:
        title, prod_desc = scrape_current_steal_product_name_and_description(url)
        if title is not None and prod_desc is not None:
            model = Model()
            model.save_current_steal(title, prod_desc)
            logging.info("Save went ok, killing myself now")
    os.kill(os.getpid(), signal.SIGKILL)


if __name__ == "__main__":
    main()
