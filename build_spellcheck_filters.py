from datetime import datetime, timedelta
from model import Model
import sqlite3
import os
import logging
import properties
from nltk.tokenize import sent_tokenize
from nltk.corpus import stopwords
import inbloom
import binascii
import count_min_sketch
import cPickle as pickle

"""
I'm trying to use the last several days' worth of product data to intelligently correct
user inputted search terms. To do this efficiently in the web service, this script:

1) finds the K most frequent 1,2, or 3-word phrases from the history
2) Builds a Bloom filter that the web service can use to see if the inputted phrase is (probably) spelled correctly
3) Builds a Count-Min sketch that the web service can use to see how frequently that phrase has appeared recently

NOTE: removed CM-sketch - not scaling well, need a different approach
"""

DAYS_BACK_TO_LOAD_DEALS = 14
UP_TO_K_MOST_FREQUENT_PHRASES = 1000000
TEMP_SQLITE_BLOOM_BUILDER_FILE_PATH = properties.SEARCH_TERMS_SUGGESTION_TEMP_DB_FILE_PATH
SPELLCHECK_FILTERS_OUTPUT_DIR = properties.SEARCH_TERMS_SUGGESTION_BLOOM_FILTER_OUTPUT_DIR
OUTPUTTED_BLOOM_FILTER_FILE_NAME = "spellcheck_bloom_filter.p"
OUTPUTTED_CM_SKETCH_FILE_NAME = "spellcheck_cm_sketch.p"
MIN_PHRASE_LENGTH = 6
MAX_PHRASE_LENGTH = 50  # check DB field sizes if changing this
STOP_WORDS = set(stopwords.words('english'))

__db_conn = None


def set_up_temp_db():
    global __db_conn
    logging.debug("Creating temp DB at %s" % TEMP_SQLITE_BLOOM_BUILDER_FILE_PATH)
    __db_conn = sqlite3.connect(TEMP_SQLITE_BLOOM_BUILDER_FILE_PATH)
    cursor = __db_conn.cursor()
    cursor.execute("create table exact_phrases (phrase varchar(64) unique, frequency int)")
    cursor.execute("create table nearby_phrases (phrase varchar(64) unique)")
    __db_conn.commit()


def load_recent_deals():
    model = Model()
    deals = model.load_all_steals_since(datetime.utcnow() - timedelta(days=DAYS_BACK_TO_LOAD_DEALS))
    return deals


def get_all_phrases_for(deal):
    """ Uses various tools to distill key phrases from a deal. """

    # first, we get all the sentences split up
    text = deal.product_name.replace("Up to 70% Off", "").replace(" - ", " ").strip() + ". " + deal.product_description
    sentences = sent_tokenize(text)
    sentences = [sentence.lower() for sentence in sentences]

    # then we get the one word tokens from each sentence
    one_word_phrases_list_of_lists = []
    for sentence in sentences:
        this_sentence_one_word_phrases = sentence[:-1].split(' ')  # slicing off the period
        one_word_phrases_list_of_lists.append(this_sentence_one_word_phrases)

    # then we pull out all two-word phrases
    two_word_phrases_list_of_lists = []
    for one_word_phrases in one_word_phrases_list_of_lists:
        two_word_phrases = []
        for i in range(len(one_word_phrases) - 1):
            two_word_phrase = one_word_phrases[i] + " " + one_word_phrases[i + 1]
            two_word_phrases.append(two_word_phrase)
        two_word_phrases_list_of_lists.append(two_word_phrases)

    # then we pull out all three-word phrases
    three_word_phrases_list_of_lists = []
    for one_word_phrases in one_word_phrases_list_of_lists:
        three_word_phrases = []
        for i in range(len(one_word_phrases) - 2):
            three_word_phrase = one_word_phrases[i] + " " + one_word_phrases[i + 1] + " " + one_word_phrases[i + 2]
            three_word_phrases.append(three_word_phrase)
        three_word_phrases_list_of_lists.append(three_word_phrases)

    # lastly, dedup and return
    results = set()
    for list_of_lists in [one_word_phrases_list_of_lists, two_word_phrases_list_of_lists, three_word_phrases_list_of_lists]:
        for each_list in list_of_lists:
            for entry in each_list:
                results.add(entry)
    return results


def update_count_for(phrase):
    cursor = __db_conn.cursor()
    cursor.execute("select frequency from exact_phrases where phrase = ? limit 1", (phrase,))
    rs = cursor.fetchall()
    if len(rs) < 1:
        cursor.execute("insert into exact_phrases (phrase, frequency) values (?, 1)", (phrase,))
    else:
        current_frequency = rs[0][0]
        updated_frequency = current_frequency + 1
        cursor.execute("update exact_phrases set frequency = ? where phrase = ?", (updated_frequency, phrase))
    __db_conn.commit()


def load_total_phrase_count():
    cursor = __db_conn.cursor()
    cursor.execute("select count(phrase) from exact_phrases")
    rs = cursor.fetchall()
    return rs[0][0]


def load_up_to_k_phrases_with_frequencies(k):
    # NOTE: this will not load words or phrases which only appeared once or twice
    cursor = __db_conn.cursor()
    cursor.execute("select phrase, frequency from exact_phrases order by frequency desc limit ?", (k,))
    rs = cursor.fetchall()
    for r in rs:
        yield r[0], r[1]


def delete_temp_db():
    os.remove(TEMP_SQLITE_BLOOM_BUILDER_FILE_PATH)


def build_filters():
    logging.info("set up our temp DB")
    set_up_temp_db()

    logging.info("Figuring out all of the phrases we have in our corpus")
    deals_count = 0
    for deal in load_recent_deals():
        deals_count += 1
        try:
            phrases = get_all_phrases_for(deal)
            for phrase in phrases:
                if len(phrase) < MIN_PHRASE_LENGTH:
                    continue
                update_count_for(phrase)
        except Exception as e:
            logging.exception(e)
        if deals_count % 50 == 0:
            logging.info("Processed %d deals so far" % deals_count)
    logging.info("There were %d deals" % deals_count)

    total_phrase_count = load_total_phrase_count()
    logging.info("There were %d phrases - K ceiling is %d" % (total_phrase_count, UP_TO_K_MOST_FREQUENT_PHRASES))

    logging.info("Building bloom filter and CM sketch")
    bloom_filter = inbloom.Filter(
        entries=UP_TO_K_MOST_FREQUENT_PHRASES,
        error=0.0001
    )
    # cm_sketch = count_min_sketch.CountMinSketch(
    #     w=10,
    #     d=2
    # )
    for phrase, frequency in load_up_to_k_phrases_with_frequencies(UP_TO_K_MOST_FREQUENT_PHRASES):
        logging.debug("Loaded phrase: %s, which had frequency %d" % (phrase, frequency))
        bloom_filter.add(phrase)
        # cm_sketch[phrase] += 1
    logging.info("Bloom filter and sketch built OK")

    return bloom_filter, None


def save_bloom_filter(bloom_filter):
    hex_data = binascii.hexlify(inbloom.dump(bloom_filter))
    with open(SPELLCHECK_FILTERS_OUTPUT_DIR + OUTPUTTED_BLOOM_FILTER_FILE_NAME, "wb") as f:
        f.write(hex_data)
    logging.info("Bloom filter saved to disk.")


def load_bloom_filter():
    with open(SPELLCHECK_FILTERS_OUTPUT_DIR + OUTPUTTED_BLOOM_FILTER_FILE_NAME, "rb") as f:
        data = f.read()
        return inbloom.load(binascii.unhexlify(data))


# def save_cm_sketch(cm_sketch):
#     with open(SPELLCHECK_FILTERS_OUTPUT_DIR + OUTPUTTED_CM_SKETCH_FILE_NAME, "wb") as f:
#         pickle.dump(cm_sketch, f)
#     logging.info("CM Sketch saved to disk.")
#

# def load_cm_sketch():
#     with open(SPELLCHECK_FILTERS_OUTPUT_DIR + OUTPUTTED_CM_SKETCH_FILE_NAME, "rb") as f:
#         return pickle.load(f)


def delete_saved_filters():
    os.remove(SPELLCHECK_FILTERS_OUTPUT_DIR + OUTPUTTED_BLOOM_FILTER_FILE_NAME)
    #os.remove(SPELLCHECK_FILTERS_OUTPUT_DIR + OUTPUTTED_CM_SKETCH_FILE_NAME)


def main():
    logging.basicConfig(format='%(asctime)s  -  %(message)s', level=logging.INFO)
    exit_code = 0
    try:
        bloom_filter, cm_sketch = build_filters()
        save_bloom_filter(bloom_filter)
    except Exception as e:
        logging.exception(e)
        exit_code = 1
    finally:
        delete_temp_db()
    return exit_code


if __name__ == "__main__":
    exit(main())
