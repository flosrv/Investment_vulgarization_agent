from beanie import Document
from pydantic import Field
from datetime import datetime
from typing import List
from pydantic import BaseModel, Field, ValidationError

class Article(Document):
    name: str = Field(default="")
    description: str = Field(default="")
    link: str = Field(..., unique=True)
    cleaned_text : str = Field(default="")
    date_added: datetime = Field(default_factory=datetime.utcnow)
    processed: bool = Field(default=False)
    articles: List[str] = Field(default_factory=list)
    translation: str = Field(..., description="Traduction en espagnol")
    
    class Settings:
        name = "Articles"

class CleanedArticle(BaseModel):
    name: str = Field(..., description="Titre principal de l'article")
    description: str = Field(..., description="Résumé court de l'article (2-3 phrases)")
    tags: List[str] = Field(default_factory=list, description="Mots-clés représentatifs")
    text_clean: str = Field(..., description="Version nettoyée du Markdown")
    link: str = Field(..., description="Lien original de l'article")
