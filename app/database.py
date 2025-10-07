import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import logging
import asyncio
from app.utils.utils import find_config

logging.basicConfig(level=logging.INFO)

config = find_config(creds="mongo_creds.json")

async def init_db():
    """
    Initialise la connexion à MongoDB et la collection 'Articles'.
    Retourne l'objet db Motor.
    """
    MONGODB_URL = config.get("emeralds_business_url")
    if not MONGODB_URL:
        logging.error("MONGODB_URL not found in environment variables.")
        raise EnvironmentError("MONGODB_URL not set.")

    try:
        client = AsyncIOMotorClient(MONGODB_URL)
        db = client["Emeralds_Business"]
        logging.info("Successfully connected to MongoDB.")

        # Vérifie si la collection 'Articles' existe
        existing_collections = await db.list_collection_names()
        if "Articles" not in existing_collections:
            await db.create_collection("Articles")
            logging.info("Collection 'Articles' created.")
        else:
            logging.info("Collection 'Articles' already exists.")

        return db

    except Exception as e:
        logging.exception(f"Error connecting to MongoDB: {e}")
        raise
