"""Intelligence modes.

Mode identity drives the frontend's aura/glass treatment, so the palette
lives in the database rather than in a client constant. Seven rows are seeded
from the frontend's `AI_MODES`.
"""

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class AIMode(Base, TimestampMixin):
    __tablename__ = "ai_modes"

    # Human-readable slug ('general', 'research', …) mirrors the frontend id.
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    caption: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    # "r g b" triple, consumed verbatim by the UI's rgba() helper.
    aura: Mapped[str] = mapped_column(String(32), nullable=False)
    glyph: Mapped[str] = mapped_column(String(8), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)