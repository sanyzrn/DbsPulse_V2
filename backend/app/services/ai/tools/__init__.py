"""ثبتِ همهٔ ابزارها با یک import — حلقهٔ گفت‌وگو همین را می‌خواهد.

ماژولِ تازه‌ای که ابزار دارد، به همین فهرست اضافه می‌شود؛ نه جای دیگری.
تستِ «هم‌پوشانیِ پرامپت و مجری» هم از همین REGISTRY می‌خواند.
"""
from app.services.ai.tools import (
    analytics,
    evaluations,
    framework,
    people,
    uploads,
)
from app.services.ai.tools.base import (
    REGISTRY,
    ToolContext,
    ToolOutcome,
    ToolSpec,
    allowed_tools,
    execute_tool,
    get_tool,
    guard,
    is_allowed,
    json_content,
    openai_tools_schema,
    parse_fallback_blocks,
    strip_fallback_blocks,
)

__all__ = [
    "REGISTRY",
    "ToolContext",
    "ToolOutcome",
    "ToolSpec",
    "allowed_tools",
    "analytics",
    "evaluations",
    "execute_tool",
    "framework",
    "get_tool",
    "guard",
    "is_allowed",
    "json_content",
    "openai_tools_schema",
    "parse_fallback_blocks",
    "people",
    "strip_fallback_blocks",
    "uploads",
]
