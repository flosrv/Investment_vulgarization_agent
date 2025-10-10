import ollama, asyncio, json, re, numpy as np
from typing import List
from fastapi import Request
from app.config import markdown_cleaning_prompt, json_generation_prompt
from pydantic import ValidationError
from langchain.chat_models import ChatOpenAI
from langchain.agents import initialize_agent, Tool
from app.models import CleanedArticle
import logging, numpy as np
from sentence_transformers import SentenceTransformer
from app.models import Article
logging.basicConfig(level=logging.INFO)

# --- Accès aux agents ---
async def get_markdown_cleaner_agent(request: Request):
    agent = getattr(request.app.state, "markdownCleaner_agent", None)
    if agent is None:
        raise RuntimeError("MarkdownCleanerAgent not initialized yet.")
    await agent._ready_event.wait()
    return agent

async def get_marketing_agent(request: Request):
    agent = getattr(request.app.state, "marketing_agent", None)
    if agent is None:
        raise RuntimeError("MarketingAgent not initialized yet.")
    await agent._ready_event.wait()
    return agent

# --- Accès au RAGAgent ---
async def get_rag_agent(request: Request):
    agent = getattr(request.app.state, "rag_agent", None)
    if agent is None:
        raise RuntimeError("RAGAgent not initialized yet.")
    # Si ton RAGAgent a un event ready, attends-le (comme les autres agents)
    if hasattr(agent, "_ready_event"):
        await agent._ready_event.wait()
    return agent

class MarkdownCleanerAgent:
    def __init__(
        self, 
        cleaning_prompt_template: str = markdown_cleaning_prompt,
        json_prompt_template: str = json_generation_prompt,
        max_retries: int = 3
    ):
        self.cleaning_prompt_template = cleaning_prompt_template
        self.json_prompt_template = json_prompt_template
        self.max_retries = max_retries
        self.ready = False
        self._ready_event = asyncio.Event()
        self.agent_instance = None


    async def initialize(self):
        logging.info("🔧 Initialisation de MarkdownCleanerAgent...")
        await asyncio.sleep(1)
        self.agent_instance = "LLM instance"
        self.ready = True
        self._ready_event.set()
        logging.info("✅ MarkdownCleanerAgent est prêt")

    async def clean_markdown_in_batches(self, markdown_text: str, link: str) -> str:
        await self._ready_event.wait()
        logging.info(f"📄 Début nettoyage markdown pour {link}")

        batch_size = 1000
        segments = [markdown_text[i:i+batch_size] for i in range(0, len(markdown_text), batch_size)]
        logging.info(f"🧩 Segmentation du texte en {len(segments)} batch(s)")
        cleaned_parts = []

        for idx, seg in enumerate(segments, start=1):
            logging.info(f"⏳ Nettoyage batch {idx}/{len(segments)}")
            prompt = self.cleaning_prompt_template.format(markdown_segment=seg, link=link)
            try:
                cleaned_text = await self._call_llm_with_retries(prompt)
                cleaned_parts.append(cleaned_text)
                logging.info(f"✅ Batch {idx} nettoyé avec succès")
            except Exception as e:
                logging.warning(f"⚠️ Échec nettoyage batch {idx}: {e}")

        final_cleaned_text = "\n\n".join(cleaned_parts)
        final_cleaned_text = re.sub(r'\n{3,}', '\n\n', final_cleaned_text).strip()
        logging.info("🧹 Texte final concaténé et post-traité")
        return final_cleaned_text

    async def generate_json_from_cleaned_text(self, cleaned_text: str, link: str) -> 'CleanedArticle':
        await self._ready_event.wait()
        prompt = self.json_prompt_template.format(cleaned_text=cleaned_text, link=link)
        logging.info(f"📄 Début génération JSON pour {link}")
        try:
            response_content = await self._call_llm_with_retries(prompt)
            data_dict = json.loads(response_content)
            cleaned_article = CleanedArticle(**data_dict)
            logging.info("✅ JSON généré et CleanedArticle créé avec succès")
            return cleaned_article
        except Exception as e:
            logging.warning(f"⚠️ Échec génération JSON ou validation CleanedArticle: {e}")
            raise ValueError(f"Échec génération JSON ou validation CleanedArticle: {e}")

    async def _call_llm_with_retries(self, prompt: str) -> str:
        last_exception = None
        for attempt in range(1, self.max_retries + 1):
            logging.info(f"🤖 Appel LLM, tentative {attempt}/{self.max_retries}")
            try:
                response = ollama.chat(
                    model="gemma3:latest",
                    messages=[
                        {"role": "system", "content": "You are an assistant that processes markdown."},
                        {"role": "user", "content": prompt}
                    ],
                    stream=False
                )
                content = self._extract_content(response)
                if content:
                    return content.strip()
            except Exception as e:
                last_exception = e
                logging.warning(f"⚠️ Erreur LLM: {e}, backoff avant prochaine tentative")
                await asyncio.sleep(2 ** attempt)
        raise RuntimeError(f"💥 Échec LLM après {self.max_retries} tentatives: {last_exception}")

    def _extract_content(self, response) -> str:
        if isinstance(response, dict):
            return response.get("message", {}).get("content")
        return getattr(getattr(response, "message", None), "content", None)

class MarketingAgent:
    """
    Agent pour générer des posts courts, percutants et éducatifs
    à partir d'un texte, pour les réseaux sociaux en Colombie.
    Utilise Ollama uniquement (pas ChatOpenAI).
    """

    def __init__(self):
        self.ready = False
        self._ready_event = asyncio.Event()
        self.agent_instance = None

        self.prompt_template = (
            "You are a senior marketing strategist specialized in precious stones and metals in Colombia.\n\n"
            "Take the following text:\n{text}\n\n"
            "Your task:\n"
            "Generate 3 short social media posts in Spanish that are:\n"
            "- Unique from each other in tone, structure, and perspective.\n"
            "- Short, punchy, informative, and educational.\n"
            "- Culturally adapted to Latin American audiences.\n"
            "- Focused on different angles of the same topic (for example: technique, culture, value, sustainability, or emotion).\n\n"
            "For each post, provide:\n"
            "- 'title': a captivating short title (max 7 words)\n"
            "- 'tags': 2–3 relevant hashtags or keywords\n"
            "- 'text': the full body of the post, max 600 characters, ending with the original article link: {link}\n\n"
            "Do NOT repeat the same ideas or phrases between posts.\n"
            "Use natural, engaging language suitable for Instagram, LinkedIn, or Facebook audiences.\n\n"
            "Return ONLY a valid JSON list, like this:\n"
            "[\n"
            "  {{'title': '...', 'tags': ['...', '...'], 'text': '...'}}\n"
            "]"
        )

    async def initialize(self):
        """Initialise l'agent Ollama."""
        await asyncio.sleep(1)
        self.agent_instance = "Ollama Marketing Agent"
        self.ready = True
        self._ready_event.set()
        print("[LOG] MarketingAgent is ready ✅")

    async def generate_for_article(self, text: str, link: str) -> List[dict]:
        """
        Génère des posts sociaux à partir du texte et du lien fourni.
        Retourne une liste de dictionnaires JSON.
        """
        await self._ready_event.wait()

        prompt = self.prompt_template.format(text=text, link=link)
        try:
            response = ollama.chat(
                model="gemma3:latest",
                messages=[{"role": "user", "content": prompt}],
                stream=False
            )
        except Exception as e:
            raise RuntimeError(f"Ollama call failed: {e}")

        content = getattr(getattr(response, "message", None), "content", None)
        if not content:
            raise ValueError("Ollama response invalid or empty")

        # Nettoyage Markdown ou blocs de code éventuels
        content = content.strip()
        if content.startswith("```json"):
            content = content[len("```json"):].strip()
        if content.endswith("```"):
            content = content[:-3].strip()

        # Tentative de parsing JSON
        try:
            posts = json.loads(content)
        except json.JSONDecodeError:
            # Fallback : parfois le modèle renvoie des quotes simples
            content_fixed = content.replace("'", '"')
            try:
                posts = json.loads(content_fixed)
            except Exception:
                raise ValueError(f"Ollama did not return valid JSON: {content[:400]}")

        # Validation légère du format
        if not isinstance(posts, list):
            raise ValueError("Expected a JSON list of posts.")
        for post in posts:
            if not isinstance(post, dict) or "text" not in post:
                raise ValueError(f"Invalid post structure: {post}")

        return posts

class RAGAgent:
    """
    Agent spécialisé pour répondre à des questions
    en s'appuyant sur la base vectorielle FAISS des articles.
    """
    def __init__(self, top_k: int = 5, model_name: str = "all-MiniLM-L6-v2"):
        """
        top_k: nombre d'articles à retourner
        model_name: modèle de sentence-transformers pour les embeddings
        """
        self.top_k = top_k
        self.model = SentenceTransformer(model_name)

    def embed_text(self, text: str) -> np.ndarray:
        """
        Transforme un texte en vecteur float32 compatible FAISS.
        """
        return self.model.encode(text, convert_to_numpy=True).astype("float32")

    async def answer_question(self, question: str, articles, faiss_index):
        """
        Recherche les articles les plus proches dans FAISS et génère une réponse concise.
        """
        # Crée le vecteur de la question
        q_vector = np.array([self.embed_text(question)], dtype='float32')

        # Recherche des k plus proches voisins
        D, I = faiss_index.search(q_vector, self.top_k)  # distances et indices

        # Récupère les articles correspondants
        closest_articles = [articles[i] for i in I[0] if i < len(articles)]

        # Génère une réponse simple basée sur les titres et contenus
        titles = [a.title for a in closest_articles]
        context_texts = [a.content for a in closest_articles]
        answer = f"Found {len(closest_articles)} relevant articles: {titles}"

        return {
            "question": question,
            "answer": answer,
            "articles": [a.dict() for a in closest_articles],
            "titles": titles,
            "context_texts": context_texts
        }
