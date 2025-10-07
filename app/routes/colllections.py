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

# --------------------- GET -------------------------------------------------------------------------------------
# ---------------------

# 🔹 OBTENER TODOS LOS ARTÍCULOS
# ---------------------
@router.get("/all")
async def get_articles():
    """
    Devuelve todos los artículos almacenados en la base de datos.
    """
    try:
        articles = await Article.find_all().to_list()
        return {"count": len(articles), "articles": articles}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"❌ Error al obtener los artículos: {str(e)}. Verifica la conexión con la base de datos o la integridad de los datos."
        )

# ---------------------
# 🔹 OBTENER UN ARTÍCULO POR ID
# ---------------------
@router.get("/{article_id}")
async def get_article(article_id: str):
    """
    Busca y devuelve un artículo específico por su ID.
    """
    try:
        if not ObjectId.is_valid(article_id):
            raise HTTPException(status_code=400, detail="❌ ID inválido. Asegúrate de usar un ObjectId válido de MongoDB.")

        article = await Article.get(ObjectId(article_id))
        if not article:
            raise HTTPException(status_code=404, detail="⚠️ Artículo no encontrado en la base de datos.")
        return article

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"💥 Error inesperado al buscar el artículo: {str(e)}"
        )

# ---------------------
# 🔹 OBTENER LOS ARTÍCULOS MÁS RECIENTES
# ---------------------
@router.get("/recent")
async def get_recent_articles(limit: int = 10):
    """
    Devuelve los N artículos más recientes añadidos o modificados.
    """
    start_time = time.time()
    try:
        articles = await Article.find_all().sort("date_added", -1).limit(limit).to_list()
        duration = round(time.time() - start_time, 2)
        print(f"[DURACIÓN] /recent: {duration}s")
        return {"count": len(articles), "articles": articles}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"💥 Error al obtener artículos recientes: {str(e)}")

# ---------------------
# 🔹 BÚSQUEDA FULL-TEXT
# ---------------------
@router.get("/search")
async def search_articles(query: str, limit: int = 20):
    """
    Busca artículos por palabra clave en 'name' o 'description'.
    """
    start_time = time.time()
    try:
        regex = re.compile(query, re.IGNORECASE)
        articles = await Article.find({"$or": [{"name": regex}, {"description": regex}]}).limit(limit).to_list()
        duration = round(time.time() - start_time, 2)
        print(f"[DURACIÓN] /search '{query}': {duration}s")
        return {"count": len(articles), "query": query, "articles": articles}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"💥 Error al buscar artículos: {str(e)}")


# --------------------- POST -------------------------------------------------------------------------------------
# ---------------------
# 🔹 CREAR UN ARTÍCULO DESDE UN ENLACE
# ---------------------
@router.post("/add/")
async def create_article_from_link(link: str, request: Request):
    """
    Crea un nuevo artículo extrayendo contenido desde un enlace (scraping + limpieza + guardado).
    """
    total_start = time.time()

    if not link or not re.match(r"^https?://", link):
        raise HTTPException(status_code=400, detail="❌ Enlace inválido. Debe comenzar con http:// o https://")

    try:
        markdown_agent: MarkdownCleanerAgent = request.app.state.markdownCleaner_agent

        # 1️⃣ Recuperar HTML
        start = time.time()
        clean_html = await get_article_html(link)
        if not clean_html:
            raise HTTPException(status_code=422, detail="⚠️ No se pudo extraer contenido HTML del enlace proporcionado.")
        print(f"[DURACIÓN] Extracción HTML: {time.time() - start:.2f}s")

        # 2️⃣ Convertir HTML → Markdown
        start = time.time()
        markdown_text = await html_to_markdown(clean_html)
        if not markdown_text.strip():
            raise HTTPException(status_code=422, detail="⚠️ El contenido convertido a Markdown está vacío o corrupto.")
        print(f"[DURACIÓN] Conversión HTML → Markdown: {time.time() - start:.2f}s")

        # 3️⃣ Limpieza y metadatos con LLM
        start = time.time()
        cleaned_article = await clean_markdown_with_llm(markdown_agent, markdown_text, link)
        if not cleaned_article or "name" not in cleaned_article:
            raise HTTPException(status_code=422, detail="⚠️ No se pudo limpiar ni procesar correctamente el artículo.")
        print(f"[DURACIÓN] Limpieza y extracción LLM: {time.time() - start:.2f}s")

        # 4️⃣ Insertar en la base de datos
        start = time.time()
        article = await create_article_in_db(cleaned_article)
        print(f"[DURACIÓN] Inserción en DB: {time.time() - start:.2f}s")

        total_duration = time.time() - total_start
        return {
            "success": True,
            "article_id": str(article.id),
            "duration_seconds": round(total_duration, 2),
            "message": "✅ Artículo creado correctamente desde el enlace."
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"💥 Error inesperado al crear el artículo desde el enlace: {str(e)}"
        )

# --------------------- PUT -------------------------------------------------------------------------------------
# ---------------------
# 🔹 ACTUALIZAR UN ARTÍCULO
# ---------------------
@router.put("/update/{article_id}")
async def update_article(
    article_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    processed: Optional[bool] = None
):
    """
    Actualiza los campos especificados de un artículo existente.
    """
    try:
        if not ObjectId.is_valid(article_id):
            raise HTTPException(status_code=400, detail="❌ ID inválido.")

        article = await Article.get(ObjectId(article_id))
        if not article:
            raise HTTPException(status_code=404, detail="⚠️ Artículo no encontrado para actualizar.")

        if not any([name, description, processed is not None]):
            raise HTTPException(status_code=400, detail="⚠️ No se proporcionaron campos para actualizar.")

        if name:
            article.name = name
        if description:
            article.description = description
        if processed is not None:
            article.processed = processed

        await article.save()
        return {"message": "✅ Artículo actualizado correctamente.", "id": str(article.id)}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"💥 Error al actualizar el artículo: {str(e)}"
        )


# --------------------- DELETE -------------------------------------------------------------------------------------
# ---------------------
# 🔹 ELIMINAR UN ARTÍCULO
# ---------------------
@router.delete("/delete/{article_id}")
async def delete_article(article_id: str):
    """
    Elimina un artículo de la base de datos por su ID.
    """
    try:
        if not ObjectId.is_valid(article_id):
            raise HTTPException(status_code=400, detail="❌ ID inválido.")

        article = await Article.get(ObjectId(article_id))
        if not article:
            raise HTTPException(status_code=404, detail="⚠️ El artículo no existe o ya fue eliminado.")

        await article.delete()
        return {"message": "🗑️ Artículo eliminado exitosamente.", "id": str(article_id)}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"💥 Error al eliminar el artículo: {str(e)}"
        )

# ---------------------
# 🔹 ELIMINACIÓN CONDICIONAL (BULK)
# ---------------------
@router.delete("/bulk-delete")
async def bulk_delete_articles(
    processed: Optional[bool] = None,
    older_than: Optional[datetime] = None,
    language: Optional[str] = None
):
    """
    Elimina varios artículos según filtros: processed, older_than, language.
    """
    start_time = time.time()
    try:
        query = {}
        if processed is not None:
            query["processed"] = processed
        if language:
            query["language"] = language.upper()
        if older_than:
            query["date_added"] = {"$lt": older_than}

        result = await Article.find(query).delete()
        duration = round(time.time() - start_time, 2)
        print(f"[DURACIÓN] /bulk-delete {query}: {duration}s")
        return {"deleted_count": result.deleted_count, "filters": query}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"💥 Error al eliminar artículos: {str(e)}")


# ---------------------
# 🔹 ACTUALIZAR METADATOS ADICIONALES
# ---------------------
@router.patch("/update-metadata/{article_id}")
async def update_metadata(
    article_id: str,
    tags: Optional[List[str]] = None,
    category: Optional[str] = None
):
    """
    Actualiza campos adicionales como 'tags' o 'category'.
    """
    start_time = time.time()
    try:
        if not ObjectId.is_valid(article_id):
            raise HTTPException(status_code=400, detail="❌ ID inválido.")

        article = await Article.get(ObjectId(article_id))
        if not article:
            raise HTTPException(status_code=404, detail="⚠️ Artículo no encontrado")

        if tags is not None:
            article.tags = tags
        if category:
            article.category = category

        await article.save()
        duration = round(time.time() - start_time, 2)
        print(f"[DURACIÓN] /update-metadata {article_id}: {duration}s")
        return {"id": str(article.id), "tags": article.tags, "category": article.category}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"💥 Error al actualizar metadatos: {str(e)}")

