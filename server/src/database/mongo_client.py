from pymongo import AsyncMongoClient
from dotenv import load_dotenv
import os

# import voyageai

load_dotenv()

client = AsyncMongoClient(os.getenv("MONGO_URI"),
                          # Set application name
                          appname="agent-os")

db = client[os.getenv("MONGO_DB")]


# voyage_api_key = os.getenv("VOYAGE_API_KEY")
# if voyage_api_key:
#     voyageai.api_key = voyage_api_key
#
#
# def voyage_ai_available():
#     """Check if Voyage API Key is available and valid."""
#     api_key = os.getenv("VOYAGE_API_KEY")
#     if api_key is None or api_key == "your_voyage_api_key":
#         return None
#     return api_key is not None and api_key.strip() != ""


# A quick way to test if we can connect to Atlas instance
def ping():
    client.admin.command("ping")


# Get the MongoDB Atlas collection to connect to
def get_collection(name: str):
    return db[name]


# Query a MongoDB collection
def find(collection_name, filter={}, limit=0):
    collection = get_collection(collection_name)
    items = list(collection.find(filter=filter, limit=limit))
    return items
