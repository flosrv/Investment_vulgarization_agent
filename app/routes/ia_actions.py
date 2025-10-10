from fastapi import APIRouter, Request, Query, HTTPException
from datetime import datetime
from app.models import Article, SocialPost
from typing import List, Dict, Any
import logging
from app.agents import RAGAgent
from beanie import PydanticObjectId
from fastapi import APIRouter, Request, HTTPException
from app.models import Article
import numpy as np
from sentence_transformers import SentenceTransformer  # ou ton modèle d'embeddings

embed_model = SentenceTransformer("all-MiniLM-L6-v2")  # exemple de modèle
logger = logging.getLogger("social_posts")
router = APIRouter()

@router.post("/vectorize_articles")
async def vectorize_all_articles(request: Request):
    """
    Récupère tous les articles de MongoDB et les ajoute dans l'index FAISS.
    Ignore ceux déjà présents. Renvoie toujours une réponse même en cas d'erreur.
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

        return {"added": len(new_articles), "total_in_index": len(article_ids), "status": "success"}

    except Exception as e:
        logging.exception("Error vectorizing articles")
        # On renvoie l’erreur dans le JSON au lieu de lever une exception
        return {"added": 0, "total_in_index": len(request.app.state.article_ids), "status": "error", "detail": str(e)}

@router.post("/generate_social_posts/")
async def generate_social_posts(
    request: Request,
    count: int = Query(default=1, ge=1, le=10, description="Nombre de posts à générer par article (1–10)")
):
    """
    Génère des posts sociaux pour les articles non traités (processed=False).
    Utilise la traduction espagnole de chaque article.
    Marque processed=True uniquement si tous les posts sont générés correctement.
    """

    # Vérification basique du contexte applicatif
    if not hasattr(request.app.state, "marketing_agent"):
        logger.error("🚫 Aucun agent de marketing détecté dans l'application FastAPI.")
        raise HTTPException(
            status_code=500,
            detail="Agent de marketing non initialisé dans l'application. Vérifiez request.app.state.marketing_agent."
        )

    marketing_agent = request.app.state.marketing_agent
    logger.info("🔎 Démarrage génération des posts sociaux...")
    logger.info(f"Paramètres reçus : count={count}")

    try:
        unprocessed_articles = await Article.find(Article.processed == False).to_list()
    except Exception as e:
        logger.exception("💥 Erreur lors de la récupération des articles non traités.")
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la lecture de la base de données : {e}"
        )

    if not unprocessed_articles:
        logger.warning("⚠️ Aucun article non traité trouvé dans la base.")
        return {
            "success": False,
            "message": "Aucun article non traité trouvé.",
            "hint": "Ajoutez ou réinitialisez des articles avec processed=False pour les traiter."
        }

    total_articles = len(unprocessed_articles)
    logger.info(f"📚 {total_articles} article(s) à traiter.")

    results = []
    errors = []

    for i, article in enumerate(unprocessed_articles, start=1):
        logger.info(f"\n——— [{i}/{total_articles}] Traitement de : {article.name} ——–")
        success = False

        try:
            # Vérification des champs essentiels
            if not article.translation:
                msg = f"Aucune traduction espagnole trouvée pour l'article ({article.link})."
                logger.warning(f"🚫 {msg}")
                errors.append({
                    "article_id": str(article.id),
                    "error": msg,
                    "suggestion": "Assurez-vous que la clé 'translation' contient du texte espagnol."
                })
                continue

            if not isinstance(article.translation, str) or len(article.translation.strip()) < 30:
                msg = f"Contenu traduit vide ou trop court pour l'article ({article.link})."
                logger.warning(f"🚫 {msg}")
                errors.append({
                    "article_id": str(article.id),
                    "error": msg,
                    "suggestion": "Vérifiez que la traduction de l'article est bien complète."
                })
                continue

            # Génération via agent
            logger.info(f"🤖 Génération des posts via Ollama pour {article.link} ...")
            try:
                posts = await marketing_agent.generate_for_article(article.translation, article.link)
            except Exception as e:
                raise RuntimeError(f"Erreur lors de la génération par l'agent : {e}")

            if not posts or not isinstance(posts, list):
                raise ValueError(f"Aucun post valide généré pour {article.link}.")

            posts = posts[:count]
            formatted_posts = []

            for post in posts:
                # Validation structurelle de chaque post
                if not isinstance(post, dict):
                    raise ValueError(f"Structure inattendue pour un post : {post}")
                if not all(k in post for k in ("title", "text", "tags")):
                    raise ValueError(f"Post mal formé : {post}")

                formatted_posts.append({
                    "title": post.get("title", "Sin título"),
                    "text": post.get("text", "").strip(),
                    "tags": post.get("tags", [])
                })

            # Vérification du résultat final
            if not formatted_posts:
                raise ValueError(f"Aucun post utilisable généré pour {article.link}.")

            # Mise à jour DB
            article.articles = formatted_posts
            article.processed = True
            article.date_added = datetime.now()
            await article.save()
            success = True

            results.append({
                "article_id": str(article.id),
                "posts_generated": len(formatted_posts),
                "link": article.link,
                "status": "success"
            })

            logger.info(f"✅ {len(formatted_posts)} posts générés et sauvegardés pour {article.name}")

        except Exception as e:
            logger.exception(f"💥 Erreur avec {article.link} → {e}")
            errors.append({
                "article_id": str(article.id),
                "error": str(e),
                "suggestion": "Consultez les logs du serveur pour plus de détails sur l'exception."
            })

        if not success:
            logger.info(f"⚠️ Article {article.name} non traité complètement, processed reste False.")

    logger.info(f"🏁 Terminé : {len(results)} articles mis à jour, {len(errors)} erreurs détectées.")

    # Réponse enrichie et explicite
    return {
        "success": True if results else False,
        "message": f"Traitement terminé : {len(results)} article(s) mis à jour, {len(errors)} erreur(s).",
        "summary": {
            "articles_traites": len(results),
            "articles_en_erreur": len(errors),
            "total_initial": total_articles
        },
        "details_succes": results,
        "details_erreurs": errors,
        "suggestions": [
            "Vérifiez que chaque article contient une clé 'translation' non vide.",
            "Assurez-vous que l'agent marketing (Ollama / LLM) est bien initialisé et fonctionnel.",
            "Consultez les logs pour identifier les articles ignorés ou les erreurs de génération."
        ]
    }

@router.post("/ask")
async def ask_knowledge(request: Request, question: str):
    """
    Pose une question à la base de connaissances vectorielle FAISS.
    Retourne les articles les plus proches et une réponse générée.
    """
    try:
        logging.info("[/ask] Received question: %s", question)

        # Accès aux ressources du serveur
        faiss_index = request.app.state.faiss_index
        rag_agent = request.app.state.rag_agent
        article_ids = list(request.app.state.article_ids)  # IDs déjà dans FAISS

        if not article_ids:
            logging.warning("[/ask] No articles in FAISS yet.")
            return {"question": question, "answer": "No articles indexed yet.", "articles": []}

        # Crée le vecteur de la question via l'agent RAG
        q_vector = np.array([rag_agent.markdown_agent.embed_text(question)], dtype='float32')

        # Recherche des k voisins les plus proches
        D, I = faiss_index.search(q_vector, rag_agent.top_k)
        logging.info("[/ask] FAISS returned %d nearest neighbors", len(I[0]))

        # Récupérer les IDs correspondants
        closest_ids = [article_ids[i] for i in I[0] if i < len(article_ids)]
        logging.info("[/ask] Closest article IDs: %s", closest_ids)

        # Obtenir les contenus via l'agent RAG
        result = await rag_agent.answer_question_by_ids(question, closest_ids)
        logging.info("[/ask] Returning answer to client")

        return result

    except Exception as e:
        logging.error("[/ask] Error during RAG query: %s", e)
        raise HTTPException(status_code=500, detail=f"Error in RAG query: {e}")


