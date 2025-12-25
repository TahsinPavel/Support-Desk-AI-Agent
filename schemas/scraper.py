from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional


class ScrapedFAQItem(BaseModel):
    question: str = Field(..., min_length=1)
    answer: str = Field(..., min_length=1)


class ScrapedServiceItem(BaseModel):
    service: str = Field(..., min_length=1)
    price: Optional[str] = Field(None, description="If found on the site (e.g. '$99', 'From $50').")


class ScraperRequest(BaseModel):
    url: HttpUrl
    business_name: Optional[str] = Field(
        None,
        description="Optional hint for the extractor if the page contains multiple businesses.",
        max_length=255,
    )


class ScraperResponse(BaseModel):
    source_url: HttpUrl
    extracted_business_name: Optional[str] = None

    timezone: Optional[str] = Field(
        None,
        description="IANA timezone if confidently known (e.g. 'America/New_York').",
    )
    open_time: Optional[str] = Field(None, description="Business opening time, e.g. '09:00'.")
    close_time: Optional[str] = Field(None, description="Business closing time, e.g. '17:00'.")

    faqs: List[ScrapedFAQItem] = Field(default_factory=list)
    services: List[ScrapedServiceItem] = Field(default_factory=list)

    notes: Optional[str] = Field(
        None,
        description="Short notes when the source data is incomplete/ambiguous.",
        max_length=1000,
    )
