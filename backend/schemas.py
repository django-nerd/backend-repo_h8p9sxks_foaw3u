"""
Database Schemas for kupi-bassein content

Each Pydantic model corresponds to a MongoDB collection (lowercased class name).
"""
from typing import List, Optional
from pydantic import BaseModel, Field, HttpUrl

class Project(BaseModel):
    title: str = Field(..., description="Название проекта")
    city: Optional[str] = Field(None, description="Город")
    image: Optional[HttpUrl] = Field(None, description="Изображение проекта")
    specs: List[str] = Field(default_factory=list, description="Характеристики")
    source_url: Optional[HttpUrl] = Field(None, description="Ссылка на оригинал")

class Service(BaseModel):
    title: str = Field(..., description="Название услуги")
    description: Optional[str] = Field(None, description="Описание услуги")
    source_url: Optional[HttpUrl] = Field(None, description="Ссылка на оригинал")
