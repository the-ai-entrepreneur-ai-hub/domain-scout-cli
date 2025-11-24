from pydantic import BaseModel, EmailStr, Field, HttpUrl
from typing import Optional
from datetime import datetime

class CrawlResult(BaseModel):
    domain: str
    company_name: Optional[str] = None
    description: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    status: str = Field(default="SUCCESS")
    error_reason: Optional[str] = None
    crawled_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True
