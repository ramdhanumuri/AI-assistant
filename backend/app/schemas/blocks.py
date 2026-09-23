"""Content block schemas.

Mirrors the frontend's `ContentBlock` union so a stored message round-trips to
the UI without translation. Known kinds are validated strictly; unrecognised
kinds fall through to `GenericBlock` so MODULE 8/9 can introduce new block
types without breaking reads of older rows.
"""

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Discriminator, Field, Tag

from app.schemas.common import APIModel


class _BlockBase(APIModel):
    pass


class TextBlock(_BlockBase):
    kind: Literal["text"] = "text"
    body: str


class CodeBlock(_BlockBase):
    kind: Literal["code"] = "code"
    language: str
    filename: str | None = None
    body: str


class ListBlock(_BlockBase):
    kind: Literal["list"] = "list"
    ordered: bool = False
    items: list[str]


class TableBlock(_BlockBase):
    kind: Literal["table"] = "table"
    caption: str | None = None
    columns: list[str]
    rows: list[list[str]]


class InsightBlock(_BlockBase):
    kind: Literal["insight"] = "insight"
    title: str
    metric: str
    delta: str | None = None
    detail: str


class CardItem(APIModel):
    title: str
    meta: str
    body: str
    tag: str | None = None


class CardGridBlock(_BlockBase):
    kind: Literal["cards"] = "cards"
    cards: list[CardItem]


class FileBlock(_BlockBase):
    kind: Literal["file"] = "file"
    name: str
    type: str
    size: str
    status: Literal["parsed", "indexed", "processing"]


class SuggestionBlock(_BlockBase):
    kind: Literal["suggestions"] = "suggestions"
    label: str
    items: list[str]


class TimelineStep(APIModel):
    label: str
    detail: str | None = None
    state: Literal["done", "active", "pending"]


class TimelineBlock(_BlockBase):
    kind: Literal["timeline"] = "timeline"
    steps: list[TimelineStep]


class GenericBlock(BaseModel):
    """Forward-compatibility hatch for block kinds this build does not know."""

    model_config = ConfigDict(extra="allow")

    kind: str


_KNOWN_KINDS = frozenset(
    {
        "text",
        "code",
        "list",
        "table",
        "insight",
        "cards",
        "file",
        "suggestions",
        "timeline",
    }
)


def _block_tag(value: Any) -> str:
    kind = value.get("kind") if isinstance(value, dict) else getattr(value, "kind", None)
    return kind if kind in _KNOWN_KINDS else "__generic__"


def _tagged(model: type[BaseModel], tag: str) -> Any:
    return Annotated[model, Tag(tag)]


ContentBlock = Annotated[
    Union[
        _tagged(TextBlock, "text"),
        _tagged(CodeBlock, "code"),
        _tagged(ListBlock, "list"),
        _tagged(TableBlock, "table"),
        _tagged(InsightBlock, "insight"),
        _tagged(CardGridBlock, "cards"),
        _tagged(FileBlock, "file"),
        _tagged(SuggestionBlock, "suggestions"),
        _tagged(TimelineBlock, "timeline"),
        _tagged(GenericBlock, "__generic__"),
    ],
    Discriminator(_block_tag),
]


class ToolTraceSchema(APIModel):
    id: str
    name: str
    detail: str
    state: Literal["running", "done"]
    duration_ms: int | None = Field(default=None)