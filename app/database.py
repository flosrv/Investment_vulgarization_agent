# database.py
import os, gspread, logging
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import faiss
import numpy as np
from app.utils.utils import find_config
from google.oauth2.service_account import Credentials

logging.basicConfig(level=logging.INFO)
load_dotenv()

config = find_config(creds="mongo_creds.json")

# --------------------------
# MongoDB async
# --------------------------
async def init_db():
    MONGODB_URL = config.get("emeralds_business_url")
    if not MONGODB_URL:
        logging.error("MONGODB_URL not found in config.")
        raise EnvironmentError("MONGODB_URL not set.")

    client = AsyncIOMotorClient(MONGODB_URL)
    db = client["Emeralds_Business"]
    existing_collections = await db.list_collection_names()
    if "Articles" not in existing_collections:
        await db.create_collection("Articles")
        logging.info("Collection 'Articles' created.")
    else:
        logging.info("Collection 'Articles' already exists.")
    logging.info("Connected to MongoDB.")
    return db

# --------------------------
# FAISS vector database
# --------------------------
_faiss_index = None
_faiss_dim = 128  # adapte selon ton embedding

def init_faiss(dim=_faiss_dim, path="./faiss_index.index"):
    """
    Initialise un index FAISS sur disque ou mémoire.
    """
    global _faiss_index
    if os.path.exists(path):
        logging.info(f"Loading FAISS index from {path}")
        _faiss_index = faiss.read_index(path)
    else:
        logging.info("Creating new FAISS index")
        _faiss_index = faiss.IndexFlatL2(dim)
    return _faiss_index

async def get_faiss_index():
    """
    Retourne l'index FAISS de manière async-safe.
    """
    global _faiss_index
    if _faiss_index is None:
        _faiss_index = await asyncio.to_thread(init_faiss)
    return _faiss_index


# --------------------------
# Connect to Sheet
# --------------------------

# --- CONFIG ---
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
CREDS_FILE = r"C:\Users\flosr\Credentials\Sheet_Access.json"
SPREADSHEET_ID = "1Hsgp5-2kb7r9xx-jQA93830dCTfQX881-uOcXOyT3Ek"
SHEET_NAME = "Articles Links for IA"

# --- Connexion ---
def connect_to_sheet():
    logging.info("🔐 Connexion à Google Sheets...")
    creds = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_ID)
    return sheet

def read_links(sheet, sheet_name=SHEET_NAME):

    try:
        worksheet = sheet.worksheet(sheet_name)

        # Récupère toutes les valeurs de la colonne 2 (B)
        column_values = worksheet.col_values(2)

        # Ignore la première ligne et les valeurs vides
        column_values = [val.strip() for val in column_values[1:] if val.strip()]

        logging.info(f"✅ Lecture réussie de la feuille '{sheet_name}' — {len(column_values)} liens valides trouvés.")

        for i, val in enumerate(column_values, start=1):
            logging.info(f"{i}) {val}\n")
            print(val)

        return column_values

    except Exception as e:
        logging.error(f"❌ Erreur lors de la lecture de la feuille '{sheet_name}': {e}")
        return []

