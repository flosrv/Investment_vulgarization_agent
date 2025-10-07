from fastapi import FastAPI
from beanie import init_beanie
import asyncio
from contextlib import asynccontextmanager
from app.models import Article
from app.agents import MarketingAgent, MarkdownCleanerAgent
from app.utils.utils import find_config
from app.database import init_db

# --- Prompts ---
Prompts = find_config(creds="IA_Prompts.json")
MARKDOWN_TEMPLATE = Prompts.get("markdown_assistant_prompt")
print("[LOG] Template de prompt chargé :", MARKDOWN_TEMPLATE[:2000], "...")

# --- Async context manager pour FastAPI lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    marketing_agent = MarketingAgent()
    markdownCleaner_agent = MarkdownCleanerAgent(prompt_template=MARKDOWN_TEMPLATE)

    # Initialisation des agents
    await asyncio.gather(
        marketing_agent.initialize(),
        markdownCleaner_agent.initialize()
    )

    # Stocke-les dans app.state
    app.state.marketing_agent = marketing_agent
    app.state.markdownCleaner_agent = markdownCleaner_agent

    # Base de données
    db = await init_db()
    await init_beanie(database=db, document_models=[Article])

    yield  # permet au serveur de démarrer

# --- Création de l'app FastAPI ---
app = FastAPI(lifespan=lifespan)
