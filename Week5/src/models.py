from typing import Optional
from pydantic import BaseModel, HttpUrl


class Book(BaseModel):
    title: str
    product_url: HttpUrl
    price_text: str
    price_gbp: float
    availability_text: str
    rating_text: str
    description: Optional[str]
    source_page: HttpUrl
    fetched_at: str