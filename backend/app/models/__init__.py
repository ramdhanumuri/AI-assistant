"""Model registry.

Importing this package registers every mapper on `Base.metadata`, which
Alembic autogenerate and `create_all()` both depend on. Keep the imports
explicit — a missing entry silently drops a table from migrations.
"""

from app.models.conversation import Conversation, Message
from app.models.knowledge import KnowledgeSource
from app.models.memory import MemoryRecord
from app.models.mode import AIMode
from app.models.project import Project
from app.models.telemetry import ActivityEvent, DailyUsage
from app.models.tool import ToolIntegration

__all__ = [
    "AIMode",
    "ActivityEvent",
    "Conversation",
    "DailyUsage",
    "KnowledgeSource",
    "MemoryRecord",
    "Message",
    "Project",
    "ToolIntegration",
]
