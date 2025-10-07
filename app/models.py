from beanie import Document
from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional

class SocialPost(BaseModel):
    title: str
    tags: List[str]
    text: str

class Article(Document):
    name: str = Field(default="")
    description: str = Field(default="")
    link: str = Field(..., unique=True)
    cleaned_text: str = Field(default="")
    date_added: datetime = Field(default_factory=datetime.now)
    processed: bool = Field(default=False)
    articles: List[SocialPost] = Field(default_factory=list)
    translation: Optional[str] = Field(default=None, description="Traduction en espagnol")

    class Settings:
        name = "Articles"

class CleanedArticle(BaseModel):
    name: str = Field(..., description="Titre principal de l'article")
    description: str = Field(..., description="Résumé court de l'article (2-3 phrases)")
    tags: List[str] = Field(default_factory=list, description="Mots-clés représentatifs")
    text_clean: str = Field(..., description="Version nettoyée du Markdown")
    link: str = Field(..., description="Lien original de l'article")
