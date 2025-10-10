# app/routes/article_routes.py
from fastapi import APIRouter, HTTPException, Query, Request
from app.models import *
from app.database import *
from fastapi import Query
from faker import Faker
from datetime import datetime
from typing import List, Optional
from bson import ObjectId
import logging, time, re
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from app.agents import MarkdownCleanerAgent, MarketingAgent
# routes/vectorize.py
import numpy as np
import logging
from app.utils.ia import (
    create_article_in_db,
    clean_markdown_with_llm,
    get_article_html,
    html_to_markdown
)
router = APIRouter()
fake = Faker()

# --------------------- GET -------------------------------------------------------------------------------------
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

# ---------------------
# 🔹 OBTENER LOS ARTÍCULOS MÁS RECIENTES
# ---------------------

@router.get("/recent")
async def get_recent_articles(limit: int = Query(10, ge=1, le=50)):
    """
    Devuelve los N artículos más recientes añadidos o modificados.
    """
    try:
        articles = await Article.find_all().sort("-date_added").limit(limit).to_list()
        return {"count": len(articles), "articles": articles}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener artículos recientes: {str(e)}")

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
    logger = logging.getLogger("article_creation")

    # 0️⃣ Vérification du lien
    if not link or not re.match(r"^https?://", link):
        logger.error(f"Validación de enlace fallida: '{link}' no comienza con http:// o https://")
        raise HTTPException(status_code=400, detail="❌ Enlace inválido. Debe comenzar con http:// o https://")
    logger.info(f"Enlace válido recibido: {link}")

    try:
        markdown_agent: MarkdownCleanerAgent = request.app.state.markdownCleaner_agent

        # 1️⃣ Récupération HTML
        start = time.time()
        clean_html = await get_article_html(link)
        if not clean_html:
            logger.error(f"No se pudo extraer contenido HTML del enlace: {link}")
            raise HTTPException(status_code=422, detail="⚠️ No se pudo extraer contenido HTML del enlace proporcionado.")
        logger.info(f"HTML extraído correctamente desde {link} en {time.time() - start:.2f}s")

        # 2️⃣ Conversion HTML → Markdown
        start = time.time()
        markdown_text = await html_to_markdown(clean_html)
        if not markdown_text.strip():
            logger.error(f"Markdown generado vacío o corrupto desde {link}")
            raise HTTPException(status_code=422, detail="⚠️ El contenido convertido a Markdown está vacío o corrupto.")
        logger.info(f"HTML convertido a Markdown correctamente en {time.time() - start:.2f}s")

        # 3️⃣ Nettoyage et extraction LLM
        start = time.time()
        cleaned_article = None
        retries = 3
        for attempt in range(retries):
            try:
                cleaned_article = await clean_markdown_with_llm(markdown_agent, markdown_text, link)
                if cleaned_article and "name" in cleaned_article:
                    logger.info(f"Limpieza y extracción LLM exitosa en intento {attempt + 1}")
                    break
            except Exception as e:
                logger.warning(f"Intento {attempt + 1} de limpieza LLM falló: {e}")
                await asyncio.sleep(1)

        if not cleaned_article or "name" not in cleaned_article:
            logger.warning(f"LLM falló tras {retries} intentos, usando fallback con Markdown crudo")
            cleaned_article = CleanedArticle(
                text_clean=re.sub(r'\s+', ' ', markdown_text.strip())[:5000],
                name=link.split("/")[-1][:50]
            )
        logger.info(f"Proceso de limpieza/fallback completado en {time.time() - start:.2f}s")

        # 4️⃣ Insertion en DB
        start = time.time()
        article = await create_article_in_db(cleaned_article)
        logger.info(f"Artículo insertado en DB correctamente en {time.time() - start:.2f}s")

        total_duration = time.time() - total_start
        logger.info(f"Proceso completo finalizado exitosamente en {total_duration:.2f}s")
        return {
            "success": True,
            "article_id": str(article.id),
            "duration_seconds": round(total_duration, 2),
            "message": "✅ Artículo creado correctamente desde el enlace."
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error inesperado al crear el artículo desde {link}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"💥 Error inesperado al crear el artículo desde el enlace: {str(e)}"
        )


@router.post("/process_all_sheets_links/")
async def process_all_article_links(request: Request):
    """
    Parcourt tous les liens stockés dans app.state.articles_links, nettoie le contenu via
    MarkdownCleanerAgent et crée les articles dans la DB si ils n'existent pas encore.
    Ignore et log les doublons.
    """
    try:
        markdown_agent: MarkdownCleanerAgent = request.app.state.markdownCleaner_agent
        article_links = getattr(request.app.state, "articles_links", [])
        if not article_links:
            logging.info("❌ Aucun lien trouvé dans app.state.articles_links.")
            return {"success": False, "message": "❌ Aucun lien trouvé dans app.state.articles_links."}

        created_articles = []
        skipped_links = []

        for link in article_links:
            # Vérifier si l'article existe déjà dans MongoDB
            existing = await request.app.state.db["IA"].find_one({"lien": link})
            if existing:
                skipped_links.append(link)
                logging.info(f"Lien déjà présent en DB, ignoré: {link}")
                continue

            # Récupération HTML
            clean_html = await get_article_html(link)
            if not clean_html:
                logging.warning(f"Impossible d'extraire HTML: {link}")
                continue

            # Conversion HTML → Markdown
            markdown_text = await html_to_markdown(clean_html)
            if not markdown_text.strip():
                logging.warning(f"Markdown vide après conversion: {link}")
                continue

            # Nettoyage batch + génération JSON
            try:
                cleaned_text = await markdown_agent.clean_markdown_in_batches(markdown_text, link)
                cleaned_article = await markdown_agent.generate_json_from_cleaned_text(cleaned_text, link)
            except Exception as e:
                logging.warning(f"Échec nettoyage ou génération JSON pour {link}: {e}")
                continue

            # Création article en DB
            try:
                article = await create_article_in_db(cleaned_article)
                created_articles.append(str(article.id))
                logging.info(f"Article créé avec succès: {link}")
            except Exception as e:
                logging.warning(f"Erreur insertion DB pour {link}: {e}")
                continue

        return {
            "success": True,
            "created_articles": created_articles,
            "skipped_links": skipped_links,
            "total_links_processed": len(article_links)
        }

    except Exception as e:
        logging.exception(f"💥 Erreur inattendue lors du traitement des liens:\n{str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"💥 Erreur inattendue lors du traitement des liens:\n{str(e)}"
        )

@router.post("/vectorize_articles")
async def vectorize_all_articles(request: Request):
    """
    Récupère tous les articles de MongoDB et les ajoute dans l'index FAISS.
    Ignore ceux déjà présents.
    """
    try:
        faiss_index = request.app.state.faiss_index
        article_ids = request.app.state.article_ids  # set des IDs déjà indexés

        # Récupérer tous les articles
        articles = await Article.find_all().to_list()
        logging.info(f"Found {len(articles)} articles in MongoDB")

        new_articles = []
        vectors_to_add = []
        ids_to_add = []

        for art in articles:
            str_id = str(art.id)
            if str_id not in article_ids:
                vector = np.array(art.embedding if hasattr(art, "embedding") else [0.0]*128, dtype='float32')
                vectors_to_add.append(vector)
                ids_to_add.append(str_id)
                new_articles.append(art)

        if vectors_to_add:
            faiss_index.add(np.array(vectors_to_add, dtype='float32'))
            article_ids.update(ids_to_add)
            logging.info(f"Added {len(new_articles)} new articles to FAISS index")
        else:
            logging.info("No new articles to add to FAISS index")

        return {"added": len(new_articles), "total_in_index": len(article_ids)}

    except Exception as e:
        logging.exception("Error vectorizing articles")
        raise HTTPException(status_code=500, detail=f"Error vectorizing articles: {e}")

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


# ---------------- PATCH ----------------------
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


# --------------------- DELETE -------------------------------------------------------------------------------------

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
    Elimina varios artículos según filtros: processed, older_than.
    """
    start_time = time.time()
    try:
        query = {}
        if processed is not None:
            query["processed"] = processed

        if older_than:
            query["date_added"] = {"$lt": older_than}

        result = await Article.find(query).delete()
        duration = round(time.time() - start_time, 2)
        print(f"[DURACIÓN] /bulk-delete {query}: {duration}s")
        return {"deleted_count": result.deleted_count, "filters": query}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"💥 Error al eliminar artículos: {str(e)}")

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