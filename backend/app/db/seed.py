"""Seed data, ported from the frontend's `src/data/mock.ts`.

Seeding is idempotent: reference rows are upserted by primary key and
conversations/messages are only inserted when absent, so re-running never
clobbers work done through the API. `--reset` drops content rows first, which
is what a developer wants when the local database has drifted.

Run with:  python -m app.db.seed
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.models import (
    AIMode,
    ActivityEvent,
    Conversation,
    DailyUsage,
    KnowledgeSource,
    MemoryRecord,
    Message,
    Project,
    ToolIntegration,
)
from app.schemas.blocks import (
    CardGridBlock,
    CardItem,
    CodeBlock,
    FileBlock,
    InsightBlock,
    ListBlock,
    SuggestionBlock,
    TableBlock,
    TextBlock,
    TimelineBlock,
    TimelineStep,
    ToolTraceSchema,
)

SEED_VERSION = "module2.1"

# ── Reference data ────────────────────────────────────────────────────

MODES: list[dict[str, object]] = [
    {
        "id": "general",
        "label": "General",
        "caption": "Balanced reasoning",
        "description": "Everyday intelligence for questions, drafting, planning and synthesis.",
        "aura": "110 168 255",
        "glyph": "◍",
    },
    {
        "id": "research",
        "label": "Research",
        "caption": "Sources & synthesis",
        "description": "Deep multi-source investigation with citations, timelines and confidence scoring.",
        "aura": "150 190 255",
        "glyph": "◎",
    },
    {
        "id": "coding",
        "label": "Coding",
        "caption": "Architecture & refactor",
        "description": "Repository-aware engineering: design, implement, review and harden systems.",
        "aura": "130 200 230",
        "glyph": "⌘",
    },
    {
        "id": "creative",
        "label": "Creative",
        "caption": "Narrative & direction",
        "description": "Editorial writing, brand voice, concept development and art direction.",
        "aura": "216 195 154",
        "glyph": "✦",
    },
    {
        "id": "analysis",
        "label": "Analysis",
        "caption": "Data & decisions",
        "description": "Structured evaluation, modelling, trade-off matrices and decision memos.",
        "aura": "170 210 200",
        "glyph": "◈",
    },
    {
        "id": "vision",
        "label": "Vision",
        "caption": "Visual understanding",
        "description": "Interpret documents, interfaces, diagrams and photographic context.",
        "aura": "190 170 255",
        "glyph": "◉",
    },
    {
        "id": "voice",
        "label": "Voice",
        "caption": "Live conversation",
        "description": "Continuous spoken dialogue with interruption handling and live transcription.",
        "aura": "140 220 210",
        "glyph": "◌",
    },
]

PROJECTS: list[dict[str, object]] = [
    {
        "id": "p-helios",
        "name": "Helios Program",
        "brief": "Autonomous orbital logistics planning and margin optimisation.",
        "progress": 0.72,
        "accent": "216 195 154",
    },
    {
        "id": "p-atlas",
        "name": "Atlas Platform",
        "brief": "Core product re-architecture and design system consolidation.",
        "progress": 0.46,
        "accent": "110 168 255",
    },
    {
        "id": "p-capital",
        "name": "Capital Raise",
        "brief": "Series B materials, diligence room and investor narrative.",
        "progress": 0.88,
        "accent": "150 190 255",
    },
    {
        "id": "p-ops",
        "name": "Operations",
        "brief": "Supply resilience, vendor risk and regional compliance mapping.",
        "progress": 0.35,
        "accent": "170 210 200",
    },
]

KNOWLEDGE: list[dict[str, object]] = [
    {
        "id": "k-corp",
        "name": "Corporate Archive 2019–2026",
        "kind": "document",
        "item_count": 12480,
        "status": "synced",
        "last_synced_at_minutes": 4,
    },
    {
        "id": "k-atlas",
        "name": "atlas-platform (monorepo)",
        "kind": "repository",
        "item_count": 3842,
        "status": "indexing",
        "last_synced_at_minutes": 0,
    },
    {
        "id": "k-market",
        "name": "Market Intelligence Feed",
        "kind": "feed",
        "item_count": 912,
        "status": "synced",
        "last_synced_at_minutes": 22,
    },
    {
        "id": "k-telemetry",
        "name": "Product Telemetry Warehouse",
        "kind": "dataset",
        "item_count": 210650,
        "status": "synced",
        "last_synced_at_minutes": 60,
    },
    {
        "id": "k-legal",
        "name": "Contracts & Regulatory Corpus",
        "kind": "document",
        "item_count": 2264,
        "status": "paused",
        "last_synced_at_minutes": 4320,
    },
]

TOOLS: list[dict[str, object]] = [
    {"id": "t-web", "name": "Live Web Retrieval", "category": "Research", "connected": True, "permission": "Read", "call_count": 1840},
    {"id": "t-repo", "name": "Repository Index", "category": "Engineering", "connected": True, "permission": "Read / Write", "call_count": 642},
    {"id": "t-sql", "name": "Warehouse Query", "category": "Data", "connected": True, "permission": "Read", "call_count": 318},
    {"id": "t-chart", "name": "Chart Synthesis", "category": "Visualisation", "connected": True, "permission": "Compute", "call_count": 205},
    {"id": "t-calendar", "name": "Calendar Bridge", "category": "Productivity", "connected": False, "permission": "Read / Write", "call_count": 0},
    {"id": "t-mail", "name": "Correspondence Draft", "category": "Productivity", "connected": True, "permission": "Draft only", "call_count": 96},
    {"id": "t-vision", "name": "Visual Parser", "category": "Vision", "connected": True, "permission": "Compute", "call_count": 411},
]

MEMORY: list[dict[str, object]] = [
    {
        "id": "m-1",
        "statement": "Prefers decisions framed as a recommendation with an explicit cost and a reversal path.",
        "scope": "Communication",
        "confidence": 0.96,
        "learned_at_days": 42,
    },
    {
        "id": "m-2",
        "statement": "Operating across the Helios and Atlas workstreams; Helios takes priority before Thursday board cycles.",
        "scope": "Context",
        "confidence": 0.91,
        "learned_at_days": 21,
    },
    {
        "id": "m-3",
        "statement": "Writes in British spelling for external documents, American for internal engineering notes.",
        "scope": "Style",
        "confidence": 0.88,
        "learned_at_days": 60,
    },
    {
        "id": "m-4",
        "statement": "Distrusts aggregated metrics without a stated denominator; always show the base.",
        "scope": "Analysis",
        "confidence": 0.94,
        "learned_at_days": 35,
    },
    {
        "id": "m-5",
        "statement": "Holds a standing review Thursday 09:00 UTC — long-form output should land the evening before.",
        "scope": "Schedule",
        "confidence": 0.83,
        "learned_at_days": 14,
    },
]

USAGE: list[dict[str, object]] = [
    {"label": "Mon", "value": 128, "secondary": 42},
    {"label": "Tue", "value": 186, "secondary": 61},
    {"label": "Wed", "value": 242, "secondary": 88},
    {"label": "Thu", "value": 205, "secondary": 74},
    {"label": "Fri", "value": 268, "secondary": 103},
    {"label": "Sat", "value": 96, "secondary": 31},
    {"label": "Sun", "value": 74, "secondary": 22},
]

ACTIVITY: list[dict[str, object]] = [
    {"label": "Indexed 412 files from atlas-platform", "mode_id": "coding", "minutes_ago": 2},
    {"label": "Completed margin sensitivity sweep (8 scenarios)", "mode_id": "analysis", "minutes_ago": 18},
    {"label": "Retrieved 23 sources on APAC tariff amendments", "mode_id": "research", "minutes_ago": 46},
    {"label": "Drafted investor long-form — v4", "mode_id": "creative", "minutes_ago": 120},
    {"label": "Parsed 6 interface captures from onboarding audit", "mode_id": "vision", "minutes_ago": 240},
]

CONVERSATIONS: list[dict[str, object]] = [
    {
        "id": "c-orbital",
        "title": "Orbital logistics margin model",
        "preview": "Reframed the launch cadence assumption — recoverable margin improves by 14.2% under the revised window.",
        "mode_id": "analysis",
        "project_id": "p-helios",
        "pinned": True,
        "minutes_ago": 24,
    },
    {
        "id": "c-atlas",
        "title": "Atlas design system migration",
        "preview": "Generated the codemod plan for 340 legacy components with a staged rollout sequence.",
        "mode_id": "coding",
        "project_id": "p-atlas",
        "pinned": True,
        "minutes_ago": 120,
    },
    {
        "id": "c-series-b",
        "title": "Series B narrative — investor long form",
        "preview": "Tightened the opening to 84 words and removed three hedging clauses from the thesis.",
        "mode_id": "creative",
        "project_id": "p-capital",
        "pinned": False,
        "minutes_ago": 300,
    },
    {
        "id": "c-supply",
        "title": "Supply chain exposure across APAC",
        "preview": "Mapped 6 tier-2 dependencies against the new tariff schedule; two need dual-sourcing.",
        "mode_id": "research",
        "project_id": "p-ops",
        "pinned": False,
        "minutes_ago": 1440,
    },
    {
        "id": "c-board",
        "title": "Board pre-read — FY26 strategy",
        "preview": "Restructured into three decisions, each with a recommendation and a cost.",
        "mode_id": "general",
        "project_id": None,
        "pinned": False,
        "minutes_ago": 1620,
    },
    {
        "id": "c-interface",
        "title": "Interface audit — onboarding funnel",
        "preview": "Identified 4 friction points in the activation path with annotated captures.",
        "mode_id": "vision",
        "project_id": None,
        "pinned": False,
        "minutes_ago": 2880,
    },
    {
        "id": "c-voice-notes",
        "title": "Voice notes — product review",
        "preview": "Spoken review transcribed and organised into 9 actionable items.",
        "mode_id": "voice",
        "project_id": None,
        "pinned": False,
        "minutes_ago": 4320,
    },
    {
        "id": "c-lattice",
        "title": "Lattice inference cost curve",
        "preview": "Quantised deployment path cuts per-request cost by 61% at parity quality.",
        "mode_id": "coding",
        "project_id": "p-atlas",
        "pinned": False,
        "minutes_ago": 5760,
    },
]


# ── Seeded transcripts ────────────────────────────────────────────────


def _dump(block: object) -> dict:
    return block.model_dump(by_alias=True, exclude_none=True)  # type: ignore[attr-defined]


def _margin_transcript() -> list[dict[str, object]]:
    """The analysis thread shown when the conversation surface opens."""
    return [
        {
            "id": "m-seed-u1",
            "role": "user",
            "mode_id": "analysis",
            "minutes_ago": 12,
            "blocks": [
                _dump(
                    TextBlock(
                        body=(
                            "Model the margin impact if we move the Helios launch "
                            "cadence from 9 to 7 days. Show me where it breaks first."
                        )
                    )
                )
            ],
            "reasoning": None,
            "traces": None,
            "tokens": None,
        },
        {
            "id": "m-seed-a1",
            "role": "assistant",
            "mode_id": "analysis",
            "minutes_ago": 11,
            "tokens": 847,
            "reasoning": (
                "Retrieved three cost baselines, isolated the fixed-facility term, "
                "then swept cadence 9→7 days in 0.5-day increments against the "
                "revised tariff schedule."
            ),
            "traces": [
                ToolTraceSchema(id="tr-1", name="Warehouse Query", detail="helios_cost_baseline", state="done", duration_ms=1840).model_dump(by_alias=True, exclude_none=True),
                ToolTraceSchema(id="tr-2", name="Chart Synthesis", detail="cadence sensitivity sweep", state="done", duration_ms=2620).model_dump(by_alias=True, exclude_none=True),
                ToolTraceSchema(id="tr-3", name="Live Web Retrieval", detail="tariff schedule Q3 revision", state="done", duration_ms=1130).model_dump(by_alias=True, exclude_none=True),
            ],
            "blocks": [
                _dump(
                    TextBlock(
                        body=(
                            "I ran the sweep across 8 cadence scenarios against the "
                            "Q3 tariff revision. Recoverable margin rises to a peak "
                            "at 7.5 days, then collapses — the binding constraint is "
                            "not launch capacity, it is the tier-2 component buffer."
                        )
                    )
                ),
                _dump(
                    InsightBlock(
                        title="Optimal cadence",
                        metric="7.5 days",
                        delta="+14.2% margin",
                        detail=(
                            "Peak recoverable margin of 31.8%. Beyond 7.5 days the "
                            "buffer depletes faster than replenishment clears customs."
                        ),
                    )
                ),
                _dump(
                    TableBlock(
                        caption="Cadence sensitivity — recoverable margin",
                        columns=["Cadence", "Margin", "Buffer days", "Constraint"],
                        rows=[
                            ["9.0 d", "27.6%", "11.4", "None"],
                            ["8.0 d", "29.9%", "8.1", "None"],
                            ["7.5 d", "31.8%", "6.2", "Component buffer"],
                            ["7.0 d", "29.1%", "3.4", "Customs clearance"],
                            ["6.0 d", "21.7%", "0.8", "Hard stop"],
                        ],
                    )
                ),
                _dump(
                    TextBlock(
                        body=(
                            "It breaks first at tier-2 replenishment. Two suppliers "
                            "— both APAC — carry a 5.5-day effective lead time once "
                            "customs variability is included. Below a 7.5-day cadence "
                            "you are consuming buffer faster than it clears."
                        )
                    )
                ),
                _dump(
                    ListBlock(
                        items=[
                            "Dual-source the two APAC tier-2 components — removes the 7.5-day floor entirely.",
                            "Pre-clear customs for a rolling 3-launch window — recovers ~1.2 buffer days.",
                            "Hold cadence at 7.5 days until either mitigation lands.",
                        ]
                    )
                ),
                _dump(
                    SuggestionBlock(
                        label="Continue",
                        items=[
                            "Cost the dual-sourcing option",
                            "Model a 6-day cadence with pre-clearance",
                            "Draft the supplier negotiation brief",
                        ],
                    )
                ),
            ],
        },
    ]


def _codemod_transcript() -> list[dict[str, object]]:
    return [
        {
            "id": "m-seed-a-code",
            "role": "assistant",
            "mode_id": "coding",
            "minutes_ago": 120,
            "tokens": 1204,
            "reasoning": (
                "Scanned the monorepo for legacy Card usages, classified by prop "
                "surface, then generated a staged codemod with a reversible rollout."
            ),
            "traces": [
                ToolTraceSchema(id="tr-4", name="Repository Index", detail="scan 340 component usages", state="done", duration_ms=4210).model_dump(by_alias=True, exclude_none=True),
                ToolTraceSchema(id="tr-5", name="Chart Synthesis", detail="dependency graph render", state="done", duration_ms=990).model_dump(by_alias=True, exclude_none=True),
            ],
            "blocks": [
                _dump(
                    TextBlock(
                        body=(
                            "The migration is mechanically safe for 291 of 340 "
                            "usages. The remaining 49 depend on legacy layout props "
                            "that have no direct equivalent — those need a decision, "
                            "not a codemod."
                        )
                    )
                ),
                _dump(
                    CodeBlock(
                        language="typescript",
                        filename="codemods/migrate-card.ts",
                        body=(
                            "import { Project, SyntaxKind } from 'ts-morph';\n\n"
                            "/**\n"
                            " * Migrates legacy <Card> usage to the Atlas surface primitive.\n"
                            " * Skips any element that still reads a layout prop — those are\n"
                            " * reported for human review rather than rewritten.\n"
                            " */\n"
                            "const LEGACY_LAYOUT_PROPS = ['gutter', 'span', 'collapseBelow'];\n\n"
                            "export async function migrate(glob = 'src/**/*.tsx') {\n"
                            "  const project = new Project({ tsConfigFilePath: 'tsconfig.json' });\n"
                            "  project.addSourceFilesAtPaths(glob);\n\n"
                            "  const report: string[] = [];\n\n"
                            "  for (const file of project.getSourceFiles()) {\n"
                            "    for (const jsx of file.getDescendantsOfKind(SyntaxKind.JsxElement)) {\n"
                            "      if (jsx.getOpeningElement().getTagNameNode().getText() !== 'Card') continue;\n\n"
                            "      const attributes = jsx.getOpeningElement().getAttributes();\n"
                            "      const blocked = attributes.some((attr) =>\n"
                            "        LEGACY_LAYOUT_PROPS.includes(attr.getText().split('=')[0].trim()),\n"
                            "      );\n\n"
                            "      if (blocked) {\n"
                            "        report.push(`${file.getFilePath()}:${jsx.getStartLineNumber()}`);\n"
                            "        continue;\n"
                            "      }\n\n"
                            "      jsx.getOpeningElement().setName('Surface');\n"
                            "      jsx.getClosingElement().setName('Surface');\n"
                            "      jsx.getOpeningElement().addAttribute({\n"
                            "        name: 'elevation',\n"
                            "        initializer: '\"raised\"',\n"
                            "      });\n"
                            "    }\n"
                            "  }\n\n"
                            "  await project.save();\n"
                            "  return { migrated: 291, needsReview: report };\n"
                            "}"
                        ),
                    )
                ),
                _dump(
                    TimelineBlock(
                        steps=[
                            TimelineStep(label="Freeze legacy Card surface", detail="291 of 340 usages covered", state="done"),
                            TimelineStep(label="Run codemod on a feature branch", detail="isolated to one workstream", state="done"),
                            TimelineStep(label="Resolve 49 layout-dependent usages", detail="requires design decision", state="active"),
                            TimelineStep(label="Delete legacy surface", state="pending"),
                        ]
                    )
                ),
                _dump(
                    SuggestionBlock(
                        label="Next",
                        items=[
                            "Group the 49 usages by prop pattern",
                            "Open the migration tracking issue",
                            "Estimate the design-decision cost",
                        ],
                    )
                ),
            ],
        }
    ]


def _onboarding_transcript() -> list[dict[str, object]]:
    return [
        {
            "id": "m-seed-a-file",
            "role": "assistant",
            "mode_id": "vision",
            "minutes_ago": 300,
            "tokens": 402,
            "reasoning": None,
            "traces": None,
            "blocks": [
                _dump(
                    TextBlock(
                        body=(
                            "Parsed the onboarding flow capture. Four friction points "
                            "stand out — all of them before first value is delivered."
                        )
                    )
                ),
                _dump(
                    FileBlock(
                        name="onboarding-audit-v3.pdf",
                        type="PDF",
                        size="4.2 MB",
                        status="indexed",
                    )
                ),
                _dump(
                    CardGridBlock(
                        cards=[
                            CardItem(
                                title="Step 3 — workspace naming",
                                meta="Friction · high",
                                body="Unlabeled field with no example. 38% of sessions stall here for over 20 seconds.",
                                tag="Fix",
                            ),
                            CardItem(
                                title="Step 5 — permission prompt",
                                meta="Friction · medium",
                                body="Native browser prompt interrupts a single-screen flow. Defer until after first value.",
                                tag="Defer",
                            ),
                            CardItem(
                                title="Step 6 — empty dashboard",
                                meta="Friction · high",
                                body="No guidance after activation. Users cannot tell what to do next.",
                                tag="Redesign",
                            ),
                        ]
                    )
                ),
            ],
        }
    ]


_SEED_TRANSCRIPTS: dict[str, list[dict[str, object]]] = {
    "c-orbital": _margin_transcript(),
    "c-atlas": _codemod_transcript(),
    "c-interface": _onboarding_transcript(),
}


# ── Seeding ───────────────────────────────────────────────────────────


def _upsert(session: Session, model: type, rows: list[dict[str, object]]) -> None:
    """Insert-or-update reference rows keyed by their primary key.

    `sort_order` is applied positionally when the model declares that column,
    which keeps the seed lists ordered without every table needing the field.
    A `<column>_minutes` or `<column>_days` key is a relative offset from now,
    expanded into a real timestamp: seed data stays readable ("4 min ago", "6
    weeks ago") without the relative wording being frozen into the database.
    """
    columns = model.__table__.columns  # type: ignore[attr-defined]
    has_sort_order = "sort_order" in columns
    now = utcnow()
    for index, row in enumerate(rows):
        payload: dict[str, object] = {}
        for field, value in row.items():
            if field.endswith("_minutes"):
                payload[field.removesuffix("_minutes")] = now - timedelta(
                    minutes=int(value)  # type: ignore[arg-type]
                )
            elif field.endswith("_days"):
                payload[field.removesuffix("_days")] = now - timedelta(
                    days=int(value)  # type: ignore[arg-type]
                )
            else:
                payload[field] = value
        if has_sort_order:
            payload["sort_order"] = index
        existing = session.get(model, payload["id"])
        if existing is None:
            session.add(model(**payload))
        else:
            for field, value in payload.items():
                setattr(existing, field, value)


def _seed_conversations(session: Session) -> None:
    now = utcnow()
    for row in CONVERSATIONS:
        conversation_id = str(row["id"])
        last_message_at = now - timedelta(minutes=int(row["minutes_ago"]))  # type: ignore[arg-type]
        transcript = _SEED_TRANSCRIPTS.get(conversation_id, [])

        conversation = session.get(Conversation, conversation_id)
        if conversation is None:
            conversation = Conversation(
                id=conversation_id,
                title=str(row["title"]),
                preview=str(row["preview"]),
                mode_id=str(row["mode_id"]),
                project_id=row["project_id"],  # type: ignore[arg-type]
                pinned=bool(row["pinned"]),
                archived=False,
                # Derived from the rows actually inserted, never authored by
                # hand — `message_count` is a cache of COUNT(messages).
                message_count=len(transcript),
                last_message_at=last_message_at,
            )
            session.add(conversation)
        else:
            conversation.preview = str(row["preview"])
            conversation.project_id = row["project_id"]  # type: ignore[assignment]

        for position, message in enumerate(transcript, start=1):
            message_id = str(message["id"])
            if session.get(Message, message_id) is not None:
                continue
            session.add(
                Message(
                    id=message_id,
                    conversation_id=conversation_id,
                    position=position,
                    role=str(message["role"]),
                    mode_id=str(message["mode_id"]),
                    blocks=message["blocks"],  # type: ignore[arg-type]
                    reasoning=message["reasoning"],  # type: ignore[arg-type]
                    traces=message["traces"],  # type: ignore[arg-type]
                    voice=False,
                    tokens=message["tokens"],  # type: ignore[arg-type]
                )
            )


def _seed_usage(session: Session) -> None:
    today = utcnow().date()
    # Walk back to the most recent Monday so the series reads Mon→Sun.
    start = today - timedelta(days=today.weekday())
    existing_days = set(session.scalars(select(DailyUsage.day)).all())
    for index, point in enumerate(USAGE):
        day = start + timedelta(days=index)
        if day in existing_days:
            continue
        session.add(
            DailyUsage(
                day=day,
                label=str(point["label"]),
                value=int(point["value"]),  # type: ignore[arg-type]
                secondary=int(point["secondary"]),  # type: ignore[arg-type]
            )
        )


def _seed_activity(session: Session) -> None:
    if session.scalar(select(ActivityEvent.id).limit(1)) is not None:
        return
    now = utcnow()
    for row in ACTIVITY:
        session.add(
            ActivityEvent(
                label=str(row["label"]),
                mode_id=str(row["mode_id"]),
                occurred_at=now - timedelta(minutes=int(row["minutes_ago"])),  # type: ignore[arg-type]
            )
        )


def reset_content(session: Session) -> None:
    """Remove seeded content rows (messages first, then conversations)."""
    for message in session.query(Message).all():
        session.delete(message)
    for conversation in session.query(Conversation).all():
        session.delete(conversation)
    for event in session.query(ActivityEvent).all():
        session.delete(event)
    for usage in session.query(DailyUsage).all():
        session.delete(usage)
    session.flush()


def seed_all(session: Session, *, reset: bool = False) -> dict[str, int]:
    """Idempotently populate the database. Returns per-table row counts."""
    if reset:
        reset_content(session)

    _upsert(session, AIMode, MODES)
    _upsert(session, Project, PROJECTS)
    _upsert(session, KnowledgeSource, KNOWLEDGE)
    _upsert(session, ToolIntegration, TOOLS)
    _upsert(session, MemoryRecord, MEMORY)
    _seed_usage(session)
    _seed_activity(session)

    # Flush reference rows so conversation FKs resolve on insert.
    session.flush()
    _seed_conversations(session)
    session.commit()

    return {
        "ai_modes": session.query(AIMode).count(),
        "projects": session.query(Project).count(),
        "knowledge_sources": session.query(KnowledgeSource).count(),
        "tool_integrations": session.query(ToolIntegration).count(),
        "memory_records": session.query(MemoryRecord).count(),
        "daily_usage": session.query(DailyUsage).count(),
        "activity_events": session.query(ActivityEvent).count(),
        "conversations": session.query(Conversation).count(),
        "messages": session.query(Message).count(),
    }


def main() -> None:
    import argparse

    from app.core.logging import configure_logging, get_logger
    from app.db.session import SessionLocal

    parser = argparse.ArgumentParser(description="Seed the AURELIS database.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing conversations/messages/telemetry before seeding.",
    )
    args = parser.parse_args()

    configure_logging()
    logger = get_logger("seed")

    with SessionLocal() as session:
        counts = seed_all(session, reset=args.reset)

    logger.info("Seed complete (version %s):", SEED_VERSION)
    for table, count in counts.items():
        logger.info("  %-20s %d", table, count)


if __name__ == "__main__":
    main()