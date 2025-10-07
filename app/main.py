# main.py
from fastapi import FastAPI
from app.routes.db import router
from app.models import Article
from app.database import init_db
from beanie import init_beanie

import asyncio
import logging

logging.basicConfig(level=logging.INFO)

async def lifespan(app: FastAPI):
    """
    Lifespan context pour initialiser MongoDB + Beanie avant de démarrer l'app
    """
    # 1. Initialisation de MongoDB avec ton init_db()
    db = await init_db()

    # 2. Initialisation de Beanie avec la base et le modèle Article
    await init_beanie(database=db, document_models=[Article])

    yield  # Tout ce qui suit le yield sera exécuté à la fermeture de l'app si nécessaire

app = FastAPI(lifespan=lifespan)

# Routes
app.include_router(router, tags=["collections"], prefix="/collections")
