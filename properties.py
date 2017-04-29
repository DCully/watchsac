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
