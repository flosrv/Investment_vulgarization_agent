from fastapi import APIRouter, Request, Query
from datetime import datetime
from app.models import Article, SocialPost  # ton modèle Beanie
from typing import List, Dict, Any
import logging
from datetime import datetime

logger = logging.getLogger("social_posts")
router = APIRouter()


@router.post("/generate_social_posts/")
async def generate_social_posts(
    request: Request,
    count: int = Query(default=1, description="Nombre de posts à générer par article")
):
    """
    Parcourt tous les articles non traités (processed=False),
    génère des posts sociaux depuis leur traduction espagnole,
    les enregistre dans le champ 'articles' et ne met à jour
    processed=True que si tout a réussi.
    """

    marketing_agent = request.app.state.marketing_agent

    logger.info("🔎 Démarrage génération des posts sociaux...")
    logger.info(f"Paramètres : count={count}")

    unprocessed_articles = await Article.find(Article.processed == False).to_list()
    if not unprocessed_articles:
        logger.warning("⚠️ Aucun article non traité trouvé.")
        return {"message": "Aucun article non traité trouvé."}

    total_articles = len(unprocessed_articles)
    logger.info(f"📚 {total_articles} articles à traiter...")

    results = []

    for i, article in enumerate(unprocessed_articles, start=1):
        logger.info(f"\n——— [{i}/{total_articles}] Traitement de : {article.name} ——–")
        success = False  # Flag pour savoir si tout s'est bien passé

        try:
            if not article.translation:
                logger.warning(f"🚫 Aucun texte traduit pour {article.link}, ignoré.")
                continue

            logger.info(f"🤖 Génération de posts via Ollama pour {article.link} ...")
            posts = await marketing_agent.generate_for_article(article.translation, article.link)

            posts = posts[:count]

            formatted_posts = []
            for post in posts:
                # Vérifie que le post contient bien tous les champs requis
                if not all(k in post for k in ("title", "text", "tags")):
                    raise ValueError(f"Post mal formé : {post}")
                formatted_posts.append({
                    "title": post.get("title", "Sin título"),
                    "text": post.get("text", ""),
                    "tags": post.get("tags", [])
                })

            # Tout a réussi → mise à jour
            article.articles = formatted_posts
            article.processed = True
            article.date_added = datetime.now()
            await article.save()
            success = True

            results.append({
                "article_id": str(article.id),
                "posts_generated": len(formatted_posts),
                "link": article.link
            })

            logger.info(f"✅ {len(formatted_posts)} posts générés pour {article.name}")

        except Exception as e:
            # Si erreur, processed reste False
            logger.exception(f"💥 Erreur avec {article.link} → {e}")

        if not success:
            logger.info(f"⚠️ Article {article.name} non traité complètement, processed reste False.")

    logger.info(f"🏁 Terminé : {len(results)} articles mis à jour.")

    return {
        "message": f"Posts générés pour {len(results)} articles.",
        "details": results
    }
