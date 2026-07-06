from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import IndicatorSection


class IndicatorCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    section: IndicatorSection
    category: str = Field(min_length=1)
    description: str = Field(min_length=1)
    display_order: int = Field(default=0, ge=0)


class IndicatorUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    category: str | None = Field(default=None, min_length=1)
    description: str | None = Field(default=None, min_length=1)
    display_order: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class IndicatorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    section: IndicatorSection
    category: str
    description: str
    display_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
