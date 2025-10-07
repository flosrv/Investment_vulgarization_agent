from app.utils.utils import find_config

config = find_config(creds="mongo_creds.json")
MONGODB_URL = config.get("emeralds_business_url")
print(MONGODB_URL)