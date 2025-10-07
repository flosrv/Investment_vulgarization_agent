import asyncio
import re
import json
from typing import List
import ollama
from pydantic import ValidationError
from langchain.chat_models import ChatOpenAI
from langchain.agents import initialize_agent, Tool
from app.models import CleanedArticle

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
    Utilise Ollama uniquement, pas ChatOpenAI.
    """
    def __init__(self):
        self.ready = False
        self._ready_event = asyncio.Event()
        self.agent_instance = None
        self.prompt_template = (
            "You are an expert in marketing for precious stones and metals in Colombia.\n"
            "Take this text:\n{text}\n\n"
            "Generate 2-3 short, punchy, informative, educational social media posts.\n"
            "For each post, provide a title, 2-3 relevant tags, and the text.\n"
            "Add the original article link at the end of each post.\n"
            "Return the result as a JSON list."
        )

    async def initialize(self):
        # Simulation d'initialisation
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

        prompt = self.prompt_template.format(text=text)
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

        # Nettoyage si nécessaire
        if content.startswith("```json"):
            content = content[len("```json"):].strip()
        if content.endswith("```"):
            content = content[:-3].strip()

        try:
            posts = json.loads(content) if not isinstance(content, list) else content
        except json.JSONDecodeError:
            raise ValueError(f"Ollama did not return valid JSON: {content[:300]}")

        return posts