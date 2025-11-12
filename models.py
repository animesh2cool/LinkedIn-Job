# models.py
from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field

class JobPost(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source: str  # "linkedin"
    post_url: Optional[str] = None
    raw_text: str
    summary: Optional[str] = None
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    image_paths: Optional[str] = None  # comma-separated or JSON string for simplicity
