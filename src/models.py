from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field, HttpUrl, ConfigDict


class Source(BaseModel):
    name: str
    url: HttpUrl


class Startup(BaseModel):
    model_config = ConfigDict(extra="ignore")
    schemaVersion: str = "1.0"
    recordType: Literal["STARTUP"] = "STARTUP"
    source: Source
    content: dict[str, Any]
    collectedAt: datetime


class Product(BaseModel):
    model_config = ConfigDict(extra="ignore")
    schemaVersion: str = "1.0"
    recordType: Literal["PRODUCT"] = "PRODUCT"
    source: Source
    content: dict[str, Any]
    collectedAt: datetime


class ResearchPaper(BaseModel):
    model_config = ConfigDict(extra="ignore")
    schemaVersion: str = "1.0"
    recordType: Literal["RESEARCH_PAPER"] = "RESEARCH_PAPER"
    content: dict[str, Any]


class Job(BaseModel):
    model_config = ConfigDict(extra="ignore")
    schemaVersion: str = "1.0"
    recordType: Literal["JOB"] = "JOB"
    content: dict[str, Any]


class News(BaseModel):
    model_config = ConfigDict(extra="ignore")
    schemaVersion: str = "1.0"
    recordType: Literal["NEWS"] = "NEWS"
    content: dict[str, Any]


class EntityMapping(BaseModel):
    raw_name: str
    canonical_name: str
    entity_type: str
    method: str
    score: float | None = None
