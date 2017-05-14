from bs4 import BeautifulSoup
import requests
import logging
from model import Model, CurrentSteal
import json
import os, signal

"""
This process scrapes the current steal off of Steep and Cheap and stuffs it into the deals table in local MySQL.
"""

logging.basicConfig(filename='scrape_and_save.log', level=logging.DEBUG)


def get_current_steal_data():
    url = None
    sale_price = None
    brand_name = None
    try:
        resp = requests.get("https://www.steepandcheap.com/data/odat.json")
        assert resp.status_code == 200, "did not get a 200 back from odat.json url"
        jobj = json.loads(resp.text)
        url = "https://www.steepandcheap.com" + jobj["url"]
        sale_price = jobj["salePrice"]
        brand_name = jobj["brandName"]
        logging.info("current steal data: %s - %s - %s" % (brand_name, sale_price, url))
    except Exception as e:
        print e.message
        logging.exception(e)
    finally:
        return brand_name, sale_price, url


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
    brand_name, sale_price, url = get_current_steal_data()
    if url is not None:
        title, prod_desc = scrape_current_steal_product_name_and_description(url)
        if title is not None and prod_desc is not None:
            model = Model()
            current_steal = model.load_current_steal()
            if str(current_steal.product_name) != str(title):
                # we've already captured this iteration of the deal - don't save it again
                logging.info("This deal is new - save it")
                model.save_current_steal(CurrentSteal(None, title, prod_desc, brand_name, sale_price, url))
            logging.info("Save went ok, killing myself now")
    os.kill(os.getpid(), signal.SIGKILL)


if __name__ == "__main__":
    main()
