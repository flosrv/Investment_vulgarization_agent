import os
import re
import json
import httpx
from bs4 import BeautifulSoup
from pydantic import ValidationError
from fastapi import Request
from langchain.schema import Document
from langchain_community.document_transformers import MarkdownifyTransformer
from app.models import Article, CleanedArticle
from deep_translator import GoogleTranslator
import asyncio
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


# --- Accès aux agents ---
async def get_markdown_cleaner_agent(request: Request):
    agent = getattr(request.app.state, "markdownCleaner_agent", None)
    if agent is None:
        raise RuntimeError("MarkdownCleanerAgent not initialized yet.")
    await agent._ready_event.wait()
    return agent

async def get_marketing_agent(request: Request):
    agent = getattr(request.app.state, "marketing_agent", None)
    if agent is None:
        raise RuntimeError("MarketingAgent not initialized yet.")
    await agent._ready_event.wait()
    return agent


# --- HTML / Markdown ---
async def get_article_html(url: str) -> str:
    print(f"[LOG] Étape 2 : Extraction du HTML depuis l'URL : {url}")
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
        html = r.text

    soup = BeautifulSoup(html, "html.parser")
    content_divs = soup.find_all("div", 
                                 class_=lambda x: x and "content" in x.lower()) + \
                   soup.find_all("div", 
                                 id=lambda x: x and "content" in x.lower())

    if not content_divs:
        content_divs = [soup.find("body")]

    allowed_tags = ["p", "h1", "h2", "h3", "h4", "h5", "li", "strong", "em"]
    cleaned_html = ""
    for div in content_divs:
        for tag in div.find_all(allowed_tags):
            cleaned_html += str(tag)

    return cleaned_html

async def html_to_markdown(html: str, batch_size: int = 1000) -> str:
    print("[LOG] Étape 3 : Conversion du HTML en Markdown...")
    batches = []
    start = 0
    while start < len(html):
        if start + batch_size >= len(html):
            batches.append(html[start:])
            break
        end = html.rfind('.', start, start + batch_size)
        if end == -1:
            end = start + batch_size
        else:
            end += 1
        batches.append(html[start:end])
        start = end

    print(f"[LOG] {len(batches)} batchs créés pour conversion Markdown.")
    md_transformer = MarkdownifyTransformer()
    final_md = ""
    for i, batch_html in enumerate(batches):
        print(f"[LOG] Conversion batch {i+1}/{len(batches)}...")
        doc = Document(page_content=batch_html)
        converted_docs = md_transformer.transform_documents([doc])
        final_md += converted_docs[0].page_content + "\n\n"

    print("[LOG] Conversion Markdown terminée. Taille finale :", len(final_md))
    return final_md
