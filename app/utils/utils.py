from beanie import PydanticObjectId
from datetime import datetime
from deep_translator import GoogleTranslator  # pip install deep-translator
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from faker import Faker
from fastapi import APIRouter
from langchain.schema import Document
from langchain_community.document_transformers import MarkdownifyTransformer
import time, os, json, ollama, re, asyncio, httpx
from datetime import datetime
from typing import List
from app.models import Article
from langchain.schema import Document
from app.models import  CleanedArticle
from pydantic import ValidationError
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from langchain.chat_models import ChatOpenAI
from langchain.agents import initialize_agent, Tool

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

Prompts = find_config(creds="IA_Prompts.json")

PROMPT_TEMPLATE = Prompts.get("markdown_assistant_prompt")
print("[LOG] Template de prompt chargé :", PROMPT_TEMPLATE[:200], "...")



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


async def clean_markdown_with_llm(markdown_text: str, link: str) -> CleanedArticle:
    """
    Envoie le Markdown au LLM pour le nettoyer et extraire les métadonnées.
    Retourne un objet CleanedArticle avec le texte final nettoyé.
    """
    print("[LOG] Étape 4a : Envoi du Markdown au modèle LLM...")
    prompt = PROMPT_TEMPLATE.format(markdown=markdown_text, link=link)

    try:
        response = ollama.chat(
            model="gemma3:latest",
            messages=[
                {"role": "system", "content": "You are an assistant that cleans markdown."},
                {"role": "user", "content": prompt}
            ],
            stream=False
        )
        print(f"[LOG] Réponse brute reçue depuis Ollama:\n{response}\nResponse Data Type: {type(response)}")
    except Exception as e:
        raise RuntimeError(f"Ollama call failed: {e}")

    # ✅ Extraction du texte JSON depuis ChatResponse
    if hasattr(response, "message") and hasattr(response.message, "content"):
        content = response.message.content
    else:
        raise ValueError(f"[ERROR] Unexpected Ollama response type: {type(response)}")

    if not content:
        raise ValueError("Ollama response invalid or empty")

    # Nettoyage des backticks Markdown
    print("[LOG] Nettoyage des backticks Markdown autour du JSON...")
    if content.startswith("```json"):
        content = content[len("```json"):].strip()
    if content.endswith("```"):
        content = content[:-3].strip()

    # Conversion en dict et validation Pydantic
    print("[LOG] Tentative de parsing JSON de la réponse...")
    try:
        data_dict = json.loads(content) if not isinstance(content, dict) else content
        cleaned = CleanedArticle(**data_dict)
        print("[LOG] Validation Pydantic réussie ✅")
    except json.JSONDecodeError:
        print("[ERROR] Réponse non-JSON après nettoyage :\n", content[:300])
        raise ValueError("Ollama did not return valid JSON.")
    except ValidationError as ve:
        print("[ERROR] Validation Pydantic échouée :\n", ve)
        raise ve

    # 🔹 Nettoyage final du texte pour qu'il soit plus naturel
    text = cleaned.text_clean
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)     # supprime les liens Markdown
    text = re.sub(r'^\s*-\s+', '', text, flags=re.MULTILINE) # supprime les tirets isolés
    text = re.sub(r'https?://\S+', '', text)                 # supprime URLs seules
    text = re.sub(r'\n{3,}', '\n\n', text)                  # réduit les sauts de ligne multiples
    cleaned.text_clean = text.strip()

    print("[LOG] Nettoyage final du texte terminé ✅")
    return cleaned


async def create_article_in_db(cleaned: CleanedArticle) -> Article:
    """
    Crée un Article Beanie à partir d'un CleanedArticle et l'insère dans la DB.
    Applique un nettoyage regex pour rendre le texte plus naturel, évite les doublons,
    et traduit le texte nettoyé en espagnol.
    """
    print("[LOG] Étape 4b : Nettoyage final du texte avant insertion...")

    text = cleaned.text_clean

    print("[LOG] Vérification des doublons dans la base de données...")

    # 🔍 Vérifie si un article avec exactement le même texte existe déjà
    existing = await Article.find_one(Article.cleaned_text == text)
    if existing:
        print(f"[LOG] Doublon détecté pour l'article '{cleaned.name}' (ID: {existing.id}), insertion annulée.")
        return existing  # retourne l'article existant au lieu de créer un doublon

    print("[LOG] Traduction du texte nettoyé en espagnol...")

    # Traduction via GoogleTranslator
    translated_text = GoogleTranslator(source='auto', target='es').translate(text)

    print("[LOG] Texte nettoyé, traduit, et aucun doublon trouvé ✅")

    article = Article(
        name=cleaned.name,
        description=cleaned.description,
        link=cleaned.link,
        date_added=datetime.utcnow(),
        processed=False,
        cleaned_text=text,
        translation=translated_text
    )

    await article.insert()
    print("[LOG] Article inséré avec succès dans la collection Beanie 🎉")
    return article

# Agent global, créé une seule fois
MARKETING_AGENT = None

def get_marketing_agent():
    global MARKETING_AGENT
    if MARKETING_AGENT is not None:
        return MARKETING_AGENT

    print("[LOG] Création de l'agent marketing spécialisé pour pierres et métaux précieux en Colombie...")

    llm = ChatOpenAI(model_name="gpt-4", temperature=0.7)

    # Définition d'un outil qui prend le texte traduit et renvoie des posts courts
    def create_social_posts(text: str, link: str) -> str:
        prompt = f"""
        Tu es un expert en marketing pour pierres précieuses et métaux précieux en Colombie. 
        Prends ce texte traduit en espagnol et génère 3 à 5 textes courts percutants, informatifs et éducatifs,
        adaptés pour des posts sur les réseaux sociaux colombiens. 
        Ajoute le lien de l'article original à la fin de chaque texte.
        
        Texte à transformer : 
        {text}

        Format attendu : 
        - Texte 1
        - Texte 2
        - Texte 3
        ...
        """
        # On peut utiliser Ollama ou tout autre LLM déjà intégré
        response = ollama.chat(
            model="gemma3:latest",
            messages=[{"role": "user", "content": prompt}],
            stream=False
        )
        if hasattr(response, "message") and hasattr(response.message, "content"):
            return response.message.content.strip()
        else:
            return response.strip()

    tool = Tool(
        name="SocialMediaPostsCreator",
        func=create_social_posts,
        description="Transforme un texte en plusieurs posts courts adaptés aux réseaux sociaux colombiens"
    )

    MARKETING_AGENT = initialize_agent(
        tools=[tool],
        llm=llm,
        agent="zero-shot-react-description",
        verbose=True
    )
    return MARKETING_AGENT
