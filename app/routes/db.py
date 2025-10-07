# app/routes/article_routes.py
from fastapi import APIRouter, HTTPException, Query, Request
from app.models import *
from app.database import *
from faker import Faker
from datetime import datetime
from typing import List, Optional
from bson import ObjectId
import logging, time, re
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from app.agents import MarkdownCleanerAgent, MarketingAgent
# app/routes/db.py
from app.utils.articles import (
    create_article_in_db,
    clean_markdown_with_llm,
    get_article_html,
    html_to_markdown
)
router = APIRouter()
fake = Faker()

# ---------------------
# GET ALL ARTICLES
# ---------------------
@router.get("/all")
async def get_articles():
    try:
        articles = await Article.find_all().to_list()
        return {"count": len(articles), "articles": articles}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching articles")


    for _ in range(5):
        try:
            article = Article(
                name=fake.sentence(nb_words=6),
                description=fake.text(max_nb_chars=150),
                language=fake.random_element(elements=["ENG", "FR"]),
                link=fake.url(),
                date_added=datetime.utcnow(),
                processed=False,
                articles=[]
            )
            await article.insert()
            return {"message": "Fake article created", "id": str(article.id)}
        except Exception:
            continue
    raise HTTPException(status_code=409, detail="Unable to generate a unique fake article link after 5 attempts")

# ---------------------
# READ ARTICLE BY ID
# ---------------------
@router.get("/{article_id}")
async def get_article(article_id: str):
    try:
        article = await Article.get(ObjectId(article_id))
        if not article:
            raise HTTPException(status_code=404, detail="Article not found")
        return article
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid ID or error: {str(e)}")

# ---------------------
# LIST ARTICLES WITH FILTERS
# ---------------------
@router.get("/find-with-filters")
async def list_articles(
    processed: Optional[bool] = None,
    language: Optional[str] = None,
    limit: int = 50,
    skip: int = 0
):
    query = {}
    if processed is not None:
        query["processed"] = processed
    if language:
        query["language"] = language.upper()
    
    articles = await Article.find(query).skip(skip).limit(limit).to_list()
    return articles

# ---------------------
# UPDATE ARTICLE
# ---------------------
@router.put("/update/{article_id}")
async def update_article(article_id: str, name: Optional[str] = None, description: Optional[str] = None, processed: Optional[bool] = None):
    article = await Article.get(ObjectId(article_id))
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    if name:
        article.name = name
    if description:
        article.description = description
    if processed is not None:
        article.processed = processed
    
    await article.save()
    return {"message": "Article updated", "id": str(article.id)}

# ---------------------
# DELETE ARTICLE
# ---------------------
@router.delete("/delete/{article_id}")
async def delete_article(article_id: str):
    article = await Article.get(ObjectId(article_id))
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    await article.delete()
    return {"message": "Article deleted", "id": str(article_id)}

# ---------------------
# CREATE ARTICLE FROM LINK
# ---------------------
@router.post("/add/")
async def create_article_from_link(link: str, request: Request):
    total_start = time.time()
    try:
        markdown_agent: MarkdownCleanerAgent = request.app.state.markdownCleaner_agent

        # Étape 1 : récupération HTML
        start = time.time()
        clean_html = await get_article_html(link)
        duration = time.time() - start
        print(f"[DURATION] Extraction HTML : {duration:.2f}s")

        # Étape 2 : conversion HTML -> Markdown
        start = time.time()
        markdown_text = await html_to_markdown(clean_html)
        duration = time.time() - start
        print(f"[DURATION] Conversion HTML -> Markdown : {duration:.2f}s")

        # Étape 3 : nettoyage Markdown + métadonnées via LLM
        start = time.time()
        cleaned_article = await clean_markdown_with_llm(markdown_agent, markdown_text, link)
        duration = time.time() - start
        print(f"[DURATION] Nettoyage et extraction LLM : {duration:.2f}s")

        # Étape 4 : insertion en DB
        start = time.time()
        article = await create_article_in_db(cleaned_article)
        duration = time.time() - start
        print(f"[DURATION] Insertion en DB : {duration:.2f}s")

        total_duration = time.time() - total_start
        return {
            "success": True,
            "article_id": str(article.id),
            "duration_seconds": round(total_duration, 2)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create article: {str(e)}")
