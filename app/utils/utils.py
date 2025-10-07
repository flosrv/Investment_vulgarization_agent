import os, re, json, httpx, asyncio
from bs4 import BeautifulSoup
from pydantic import ValidationError
from fastapi import Request
from langchain.schema import Document
from langchain_community.document_transformers import MarkdownifyTransformer
from app.models import Article, CleanedArticle
from deep_translator import GoogleTranslator
from datetime import datetime

# --- Fonction de configuration ---
def find_config(creds: str, folder=r"C:\Users\flosr\Credentials") -> dict:
    print("[LOG] Étape 1 : Chargement du fichier de configuration...")
    config_path = os.path.join(folder, creds)
    
    if not os.path.isfile(config_path):
        print("[ERREUR] Fichier introuvable :", config_path)
        raise FileNotFoundError(f"Credential file '{creds}' not found in folder '{folder}'.")
    print("[LOG] Fichier trouvé :", config_path)

    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        print("[LOG] Configuration chargée avec succès.")
        return data

