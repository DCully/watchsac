import ConfigParser


config = ConfigParser.RawConfigParser()
config.read('/opt/watchsac.cfg')

# Twilio config
TWILIO_ACCOUNT_SID = config.get("Twilio", "TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = config.get("Twilio", "TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = config.get("Twilio", "TWILIO_PHONE_NUMBER")

# MySQL config
MYSQL_HOST = config.get("MySQL", "MYSQL_HOST")
MYSQL_USER = config.get("MySQL", "MYSQL_USER")
MYSQL_PASSWORD = config.get("MySQL", "MYSQL_PASSWORD")
MYSQL_DB_NAME = config.get("MySQL", "MYSQL_DB_NAME")

# client side app dir
CLIENT_APP_DIR = config.get("webapp", "CLIENT_APP_DIR")

# search terms suggestion
SEARCH_TERMS_SUGGESTION_TEMP_DB_FILE_PATH = config.get("etc", "SEARCH_TERMS_SUGGESTION_TEMP_DB_FILE_PATH")
SEARCH_TERMS_SUGGESTION_BLOOM_FILTER_OUTPUT_DIR = config.get("etc", "SEARCH_TERMS_SUGGESTION_BLOOM_FILTER_OUTPUT_DIR")
