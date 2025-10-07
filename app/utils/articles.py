# app/services/article_service.py
import re, json, asyncio, httpx
from app.models import Article, CleanedArticle
from app.agents import MarkdownCleanerAgent, MarketingAgent
from bs4 import BeautifulSoup
from typing import Optional, List
from app.models import Article
from deep_translator import GoogleTranslator
from langchain.schema import Document
from langchain_community.document_transformers import MarkdownifyTransformer
from fastapi import APIRouter, Request, HTTPException, Query
from app.models import Article
from datetime import datetime

async def clean_markdown_with_llm(agent: MarkdownCleanerAgent, markdown_text: str, link: str) -> CleanedArticle:
    """Nettoie le Markdown via l'agent MarkdownCleanerAgent."""
    return await agent.clean(markdown_text, link)

async def get_article_html(url: str) -> str:
    """Récupère le contenu HTML pertinent de l'article."""
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
        html = r.text
    soup = BeautifulSoup(html, "html.parser")
    content_divs = soup.find_all("div", class_=lambda x: x and "content" in x.lower())
    if not content_divs:
        content_divs = [soup.find("body")]
    allowed_tags = ["p", "h1", "h2", "h3", "h4", "h5", "li", "strong", "em"]
    cleaned_html = ""
    for div in content_divs:
        for tag in div.find_all(allowed_tags):
            cleaned_html += str(tag)
    return cleaned_html

async def html_to_markdown(html: str, batch_size: int = 1000) -> str:
    """Convertit le HTML en Markdown."""


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

    md_transformer = MarkdownifyTransformer()
    final_md = ""
    for batch_html in batches:
        doc = Document(page_content=batch_html)
        converted_docs = md_transformer.transform_documents([doc])
        final_md += converted_docs[0].page_content + "\n\n"
    return final_md

async def create_article_in_db(cleaned: CleanedArticle) -> Article:
    """Crée un Article Beanie à partir d'un CleanedArticle, le traduit en espagnol et l'insère dans la DB."""
    text = cleaned.text_clean
    existing = await Article.find_one(Article.cleaned_text == text)
    if existing:
        return existing

    spanish = GoogleTranslator(source='auto', target='es').translate(text)

    article = Article(
        name=cleaned.name,
        description=cleaned.description,
        link=cleaned.link,
        processed=False,
        cleaned_text=text,
        translation=spanish
    )
    await article.insert()
    return article

