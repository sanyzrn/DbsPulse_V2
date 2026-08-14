from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.text_limits import INDICATOR_CATEGORY_MAX, INDICATOR_DESCRIPTION_MAX
from app.models.enums import IndicatorSection


class IndicatorCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    section: IndicatorSection
    category: str = Field(min_length=1, max_length=INDICATOR_CATEGORY_MAX)
    description: str = Field(min_length=1, max_length=INDICATOR_DESCRIPTION_MAX)
    display_order: int = Field(default=0, ge=0)


class IndicatorUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    category: str | None = Field(default=None, min_length=1, max_length=INDICATOR_CATEGORY_MAX)
    description: str | None = Field(default=None, min_length=1, max_length=INDICATOR_DESCRIPTION_MAX)
    display_order: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class IndicatorReorder(BaseModel):
    """ترتیب جدید شاخص‌های یک بخش؛ ordered_ids باید دقیقاً همان مجموعهٔ شناسه‌های
    آن بخش باشد، به ترتیب دلخواه کاربر (drag-and-drop)."""

    section: IndicatorSection
    ordered_ids: list[int] = Field(min_length=1)


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
