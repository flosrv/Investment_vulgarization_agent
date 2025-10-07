import asyncio
import re
import json
from typing import List
import ollama
from fastapi import Request
from pydantic import ValidationError
from langchain.chat_models import ChatOpenAI
from langchain.agents import initialize_agent, Tool
from app.models import CleanedArticle

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


class MarkdownCleanerAgent:
    def __init__(self, prompt_template: str):
        self.prompt_template = prompt_template
        self.ready = False
        self._ready_event = asyncio.Event()
        self.agent_instance = None

    async def initialize(self):
        await asyncio.sleep(1)
        self.agent_instance = "LLM instance"
        self.ready = True
        self._ready_event.set()
        print("[LOG] MarkdownCleanerAgent is ready ✅")

    async def clean(self, markdown_text: str, link: str) -> CleanedArticle:
        await self._ready_event.wait()

        prompt = self.prompt_template.format(markdown=markdown_text, link=link)
        try:
            response = ollama.chat(
                model="gemma3:latest",
                messages=[
                    {"role": "system", "content": "You are an assistant that cleans markdown."},
                    {"role": "user", "content": prompt}
                ],
                stream=False
            )
        except Exception as e:
            raise RuntimeError(f"Ollama call failed: {e}")

        content = getattr(getattr(response, "message", None), "content", None)
        if not content:
            raise ValueError("Ollama response invalid or empty")

        if content.startswith("```json"):
            content = content[len("```json"):].strip()
        if content.endswith("```"):
            content = content[:-3].strip()

        try:
            data_dict = json.loads(content) if not isinstance(content, dict) else content
            cleaned = CleanedArticle(**data_dict)
        except json.JSONDecodeError:
            raise ValueError(f"Ollama did not return valid JSON: {content[:300]}")
        except ValidationError as ve:
            raise ve

        # Nettoyage final
        text = cleaned.text_clean
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        text = re.sub(r'^\s*-\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'https?://\S+', '', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        cleaned.text_clean = text.strip()

        return cleaned


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