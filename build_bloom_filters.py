from datetime import datetime, timedelta
from model import Model
import sqlite3
import os

TOP_K_MOST_FREQUENT_PHRASES = 10000
TEMP_SQLITE_BLOOM_BUILDER_FILE_PATH = "blooms_temp.db"  # TODO - put this in the properties file
BLOOM_FILTER_OUTPUT_DIR = ""
__db_conn = None


def set_up_temp_db():
    global __db_conn
    __db_conn = sqlite3.connect(TEMP_SQLITE_BLOOM_BUILDER_FILE_PATH)
    cursor = __db_conn.cursor()
    cursor.execute("create table exact_phrases (phrase varchar(128), frequency int)")
    __db_conn.commit()


def load_recent_deals():
    model = Model()
    deals = model.load_all_steals_since(datetime.utcnow() - timedelta(days=3))
    return deals


def get_all_phrases_for(deal):
    # TODO - make this more robust (nltk), and also parse out 2 and 3 word phrases
    # TODO also - how to handle too-long phrases? currently, just ignoring if > 126...
    name = deal.product_name
    desc = deal.product_description
    phrases = set()
    for phrase in name.split():
        if len(phrase) > 126:
            continue
        phrases.add(phrase)
    for phrase in desc.replace(",", "").replace(".", "").split():
        if len(phrase) > 126:
            continue
        phrases.add(phrase)
    return phrases


def update_count_for(phrase):
    cursor = __db_conn.cursor()
    cursor.execute("select frequency from exact_phrases where phrase = ?", (phrase,))
    rs = cursor.fetchall()
    print rs


def save_nearby_phrase(phrase):
    pass


def load_top_k_phrases(k):
    return []


def compute_permutations_within_X_edits_of(phrase):
    return []


def load_size_of_X_edit_set():
    return 1


def delete_temp_db():
    os.remove(TEMP_SQLITE_BLOOM_BUILDER_FILE_PATH)


def main():
    # set up our temp DB
    set_up_temp_db()

    # figure out all of the phrases we have in our corpus
    for deal in load_recent_deals():
        phrases = get_all_phrases_for(deal)
        for phrase in phrases:
            update_count_for(phrase)

    # load the top-K phrases back, and compute and save all of their X-edit-away permutations
    for phrase in load_top_k_phrases(TOP_K_MOST_FREQUENT_PHRASES):
        nearby_phrases = compute_permutations_within_X_edits_of(phrase)
        for nearby_phrase in nearby_phrases:
            save_nearby_phrase(nearby_phrase)

    # We already know the set size for the total number of actual phrases in our correctable set, so now we
    # load the total size of the nearby permutations set so we know how big to build the second bloom filter.
    edit_set_total_size = load_size_of_X_edit_set()

    # TODO the rest below - now we can build our two bloom filters for client-side consumption

    # allocate a bloom filter for edit_set_total_size elements at a 3% FPP
    # feed every edit set element into this bloom filter, and serialize it to disk

    # allocate a bloom filter for TOP_K_MOST_FREQUENT_PHRASES at a 3% FPP
    # feed every original set element into this bloom filter, and serialize it to disk

    # delete our temp database file
    delete_temp_db()


if __name__ == "__main__":
    set_up_temp_db()
    update_count_for("not there")
    delete_temp_db()
