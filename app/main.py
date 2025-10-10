# main.py
from fastapi import FastAPI
from beanie import init_beanie
import asyncio
from contextlib import asynccontextmanager
from app.models import Article
from app.routes.colllections import router as collection_routers
from app.routes.ia_actions import router as articles_routers
from app.routes.stats import router as stats_routers
from app.agents import MarketingAgent, MarkdownCleanerAgent, RAGAgent
from app.utils.utils import find_config
from app.database import init_db, get_faiss_index, connect_to_sheet, read_links
from app.config import markdown_cleaning_prompt, json_generation_prompt
import logging

logging.basicConfig(level=logging.INFO)

try:
    MARKDOWN_TEMPLATE = markdown_cleaning_prompt
    JSON_TEMPLATE = json_generation_prompt
    logging.info("[LOG] Templates de prompt chargés : Markdown (%d chars), JSON (%d chars)",
                 len(MARKDOWN_TEMPLATE), len(JSON_TEMPLATE))
except Exception as e:
    logging.error(f"[ERROR] Échec chargement des templates de prompt :\n{e}")

# --- Async context manager pour FastAPI lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    marketing_agent = MarketingAgent()
    markdownCleaner_agent = MarkdownCleanerAgent()

    # Initialisation des agents
    await asyncio.gather(
        marketing_agent.initialize(),
        markdownCleaner_agent.initialize()
    )

    # Stocker dans app.state
    app.state.marketing_agent = marketing_agent
    app.state.markdownCleaner_agent = markdownCleaner_agent

    # Base de données Mongo / Beanie
    db = await init_db()
    await init_beanie(database=db, document_models=[Article])
    app.state.db = db

    # Vector DB FAISS
    faiss_index = await get_faiss_index()
    app.state.faiss_index = faiss_index

    # Set pour suivre les IDs déjà vectorisés
    app.state.article_ids = set()

    # --- Initialisation du RAGAgent ---
    rag_agent = RAGAgent(top_k=5)
    app.state.rag_agent = rag_agent
    logging.info("RAGAgent initialized and added to app.state")

    # --- Connexion Google Sheets ---
    try:
        sheet = connect_to_sheet()
        if sheet:
            app.state.sheet = sheet
            logging.info("✅ Google Sheet connecté et stocké dans app.state")
            articles_links = read_links(sheet)
            if articles_links:
                app.state.articles_links = articles_links
                logging.info(f"{len(articles_links)} liens récupérés depuis la feuille Google")
            else:
                logging.warning("❌ Aucun lien trouvé dans la feuille Google")
    except Exception as e:
        logging.error(f"❌ Échec de connexion à Google Sheets :\n{e}")

    logging.info("App lifespan setup complete")
    yield  # permet au serveur de démarrer

# --- Création de l'app FastAPI ---
app = FastAPI(lifespan=lifespan)
app.include_router(collection_routers, prefix="/collections", tags=["Collections"])
app.include_router(articles_routers, prefix="/ia", tags=["IA"])
app.include_router(stats_routers, prefix="/stats", tags=["Stats"])
