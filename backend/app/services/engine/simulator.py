"""Deterministic simulator engine.

A faithful port of the frontend's `src/lib/engine.ts` recipe router, so the
backend produces exactly the rich block vocabulary the UI already renders. It
is deliberately deterministic: a given prompt always yields the same turn,
which makes the whole API testable without a model provider.

Replaced — not extended — in MODULE 6.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.schemas.blocks import (
    CardGridBlock,
    CardItem,
    CodeBlock,
    ContentBlock,
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
from app.services.engine.base import EngineRequest, EngineTurn


@dataclass(frozen=True, slots=True)
class _Trace:
    name: str
    detail: str
    ms: int


@dataclass(frozen=True, slots=True)
class _Recipe:
    key: str
    match: re.Pattern[str]
    mode: str | None
    reasoning: str
    traces: tuple[_Trace, ...]
    blocks: tuple[ContentBlock, ...]
    follow_ups: tuple[str, ...]


def _trace(name: str, detail: str, ms: int) -> _Trace:
    return _Trace(name=name, detail=detail, ms=ms)


_RECIPES: tuple[_Recipe, ...] = (
    _Recipe(
        key="coding",
        match=re.compile(
            r"code|refactor|architecture|monorepo|migrat|typescript|react|api"
            r"|component|bug|implement",
            re.IGNORECASE,
        ),
        mode="coding",
        reasoning=(
            "Scanned the repository index for the affected surface, ranked call "
            "sites by coupling, then generated a reversible change plan with a "
            "verification step per stage."
        ),
        traces=(
            _trace("Repository Index", "resolve affected surface", 1840),
            _trace("Chart Synthesis", "coupling graph", 940),
            _trace("Static Analysis", "type + lint pass", 2310),
        ),
        blocks=(
            TextBlock(
                body=(
                    "I mapped the change surface and split it into three stages. "
                    "The first two are mechanically safe; the third carries a real "
                    "decision and should not be automated."
                )
            ),
            CodeBlock(
                language="typescript",
                filename="src/features/conversation/useThread.ts",
                body=(
                    "import { useCallback, useReducer } from 'react';\n"
                    "import type { Message } from '@/types';\n\n"
                    "type Action =\n"
                    "  | { type: 'append'; message: Message }\n"
                    "  | { type: 'patch'; id: string; patch: Partial<Message> }\n"
                    "  | { type: 'reset' };\n\n"
                    "function reducer(state: Message[], action: Action): Message[] {\n"
                    "  switch (action.type) {\n"
                    "    case 'append':\n"
                    "      return [...state, action.message];\n"
                    "    case 'patch':\n"
                    "      return state.map((m) =>\n"
                    "        m.id === action.id ? { ...m, ...action.patch } : m,\n"
                    "      );\n"
                    "    case 'reset':\n"
                    "      return [];\n"
                    "  }\n"
                    "}"
                ),
            ),
            ListBlock(
                items=[
                    "Stage 1 — extract the reducer into a pure module. No behaviour change, fully reversible.",
                    "Stage 2 — move streaming into a hook with an abort controller so partial responses can be cancelled.",
                    "Stage 3 — decide whether optimistic user messages survive a failed request. That is a product call, not a technical one.",
                ]
            ),
            TimelineBlock(
                steps=[
                    TimelineStep(label="Extract pure reducer", detail="verified against existing tests", state="done"),
                    TimelineStep(label="Introduce streaming hook", detail="abort-safe", state="active"),
                    TimelineStep(label="Resolve optimistic-message policy", state="pending"),
                ]
            ),
            SuggestionBlock(
                label="Continue",
                items=[
                    "Write tests for the reducer",
                    "Show the abort-controller pattern",
                    "Review the error boundary",
                ],
            ),
        ),
        follow_ups=("Show the abort-controller pattern", "Write the reducer tests"),
    ),
    _Recipe(
        key="research",
        match=re.compile(
            r"research|source|citation|market|regulat|jurisdiction|competitor"
            r"|landscape|study",
            re.IGNORECASE,
        ),
        mode="research",
        reasoning=(
            "Queried four independent source classes, discarded two low-authority "
            "results, and weighted the remainder by recency and primary-source "
            "proximity."
        ),
        traces=(
            _trace("Live Web Retrieval", "42 candidate sources", 3120),
            _trace("Source Ranker", "authority + recency weighting", 1180),
            _trace("Corpus Search", "internal archive cross-check", 1420),
        ),
        blocks=(
            TextBlock(
                body=(
                    "I found a consistent direction across jurisdictions, but the "
                    "timelines diverge sharply — which matters more than the "
                    "direction itself."
                )
            ),
            TableBlock(
                caption="Regulatory position — synthesis",
                columns=["Jurisdiction", "Position", "Effective", "Confidence"],
                rows=[
                    ["European Union", "Binding, phased", "Q1 2027", "High"],
                    ["United Kingdom", "Consultation stage", "Indicative 2028", "Medium"],
                    ["United States", "Sector-by-sector", "Rolling", "Medium"],
                    ["Singapore", "Voluntary framework", "Live", "High"],
                ],
            ),
            InsightBlock(
                title="Divergence window",
                metric="9–14 months",
                detail=(
                    "The gap between EU binding effect and UK/UK-equivalent clarity "
                    "is the single largest planning risk in the corpus."
                ),
            ),
            ListBlock(
                ordered=True,
                items=[
                    "Comply to the EU standard as the ceiling — it is the strictest and most precisely drafted.",
                    "Do not build separate regional logic until the UK consultation closes.",
                    "Re-review in 90 days; two of the four positions are still moving.",
                ],
            ),
            SuggestionBlock(
                label="Go deeper",
                items=[
                    "Trace the EU drafting history",
                    "Compare enforcement regimes",
                    "Draft a compliance decision memo",
                ],
            ),
        ),
        follow_ups=("Compare enforcement regimes", "Draft a compliance decision memo"),
    ),
    _Recipe(
        key="analysis",
        match=re.compile(
            r"model|margin|forecast|analysis|data|scenario|sensitivity|metric"
            r"|revenue|cost|trade-?off",
            re.IGNORECASE,
        ),
        mode="analysis",
        reasoning=(
            "Isolated the variable terms, ran a sensitivity sweep, and identified "
            "the binding constraint rather than the headline optimum."
        ),
        traces=(
            _trace("Warehouse Query", "baseline extraction", 1640),
            _trace("Chart Synthesis", "8-scenario sweep", 2480),
        ),
        blocks=(
            TextBlock(
                body=(
                    "The headline number is less interesting than where it breaks. I "
                    "swept the variable and found a sharp cliff rather than a gradual "
                    "decline — that shape is the finding."
                )
            ),
            InsightBlock(
                title="Optimal point",
                metric="+14.2%",
                delta="vs. current",
                detail=(
                    "Peak sits well inside the safe region, but only 1.5 units from "
                    "the constraint boundary."
                ),
            ),
            TableBlock(
                caption="Sensitivity sweep",
                columns=["Scenario", "Outcome", "Headroom", "Binding constraint"],
                rows=[
                    ["Conservative", "27.6%", "11.4", "None"],
                    ["Baseline", "29.9%", "8.1", "None"],
                    ["Optimised", "31.8%", "6.2", "Buffer depletion"],
                    ["Aggressive", "29.1%", "3.4", "Clearance time"],
                    ["Beyond limit", "21.7%", "0.8", "Hard stop"],
                ],
            ),
            TextBlock(
                body=(
                    "Two caveats worth stating explicitly: the denominator excludes "
                    "fixed facility cost, and the sweep assumes last quarter’s "
                    "clearance distribution. Both are conservative, so the true "
                    "optimum is likely marginally better."
                )
            ),
            SuggestionBlock(
                label="Continue",
                items=[
                    "Re-run with fixed cost included",
                    "Stress the clearance distribution",
                    "Export the model as a memo",
                ],
            ),
        ),
        follow_ups=("Re-run with fixed cost included", "Export the model as a memo"),
    ),
    _Recipe(
        key="creative",
        match=re.compile(
            r"draft|write|narrative|story|brand|voice|creative|editorial|copy"
            r"|essay|tone",
            re.IGNORECASE,
        ),
        mode="creative",
        reasoning=(
            "Established the intended register first, then drafted to a strict "
            "word budget and removed every hedging clause."
        ),
        traces=(
            _trace("Style Memory", "retrieve preference profile", 620),
            _trace("Draft Engine", "long-form composition", 3410),
        ),
        blocks=(
            TextBlock(
                body=(
                    "I wrote this to a 160-word budget with no hedging. The opening "
                    "states the position in the first sentence — if that sentence is "
                    "wrong, the whole piece is wrong, which is the correct failure "
                    "mode for this kind of document."
                )
            ),
            CardGridBlock(
                cards=[
                    CardItem(
                        title="Opening — version A",
                        meta="Direct",
                        body=(
                            "We are not building a faster tool. We are removing a "
                            "decision from the critical path."
                        ),
                        tag="Recommended",
                    ),
                    CardItem(
                        title="Opening — version B",
                        meta="Measured",
                        body=(
                            "The constraint was never compute. It was the distance "
                            "between a question and a decision."
                        ),
                        tag="Alternate",
                    ),
                ]
            ),
            ListBlock(
                items=[
                    'Removed three instances of "we believe" — they weakened the thesis without adding caution.',
                    "Replaced two abstract nouns with concrete ones; abstraction was doing the hedging.",
                    "Kept one deliberate hedge on the timeline. That one is honest.",
                ]
            ),
            SuggestionBlock(
                label="Revise",
                items=[
                    "Make it 40 words shorter",
                    "Shift register to more formal",
                    "Write the closing paragraph",
                ],
            ),
        ),
        follow_ups=("Make it 40 words shorter", "Write the closing paragraph"),
    ),
    _Recipe(
        key="vision",
        match=re.compile(
            r"image|vision|screenshot|interface|design|ui|visual|diagram|document|pdf",
            re.IGNORECASE,
        ),
        mode="vision",
        reasoning=(
            "Parsed the visual input into structural regions, then evaluated each "
            "region against interaction intent rather than aesthetics."
        ),
        traces=(
            _trace("Visual Parser", "region segmentation", 2210),
            _trace("Layout Analysis", "hierarchy scoring", 1340),
        ),
        blocks=(
            TextBlock(
                body=(
                    "Structurally this is sound. The problems are all about "
                    "sequencing — value arrives too late relative to the effort the "
                    "user has already spent."
                )
            ),
            FileBlock(name="capture-annotated.png", type="PNG", size="2.8 MB", status="parsed"),
            CardGridBlock(
                cards=[
                    CardItem(
                        title="Primary action buried",
                        meta="Hierarchy · high",
                        body="The action sits at equal weight to three secondary controls.",
                        tag="Fix",
                    ),
                    CardItem(
                        title="Density mismatch",
                        meta="Rhythm · medium",
                        body="Two adjacent regions use different spacing scales — reads as unfinished.",
                        tag="Align",
                    ),
                    CardItem(
                        title="No state feedback",
                        meta="Interaction · high",
                        body="A 4-second operation has no progress affordance.",
                        tag="Add",
                    ),
                ]
            ),
            SuggestionBlock(
                label="Continue",
                items=[
                    "Annotate the fixes on the capture",
                    "Write the change list",
                    "Compare against the previous revision",
                ],
            ),
        ),
        follow_ups=("Write the change list", "Compare against the previous revision"),
    ),
)

_DEFAULT_RECIPE = _Recipe(
    key="default",
    match=re.compile(r".*", re.DOTALL),
    mode=None,
    reasoning=(
        "Parsed the intent, selected the most relevant context from the knowledge "
        "layer, and composed a direct answer before adding supporting structure."
    ),
    traces=(
        _trace("Intent Parser", "classify request", 480),
        _trace("Corpus Search", "retrieve relevant context", 1290),
    ),
    blocks=(
        TextBlock(
            body=(
                "Understood. Here is how I would approach it — starting with the "
                "part that constrains everything else."
            )
        ),
        ListBlock(
            ordered=True,
            items=[
                "Establish the constraint first. Most plans fail because the binding limit was never named.",
                "Choose the smallest reversible step that tests the assumption behind that constraint.",
                "Only widen scope once the first step has produced evidence.",
            ],
        ),
        InsightBlock(
            title="Recommendation",
            metric="Reversible first",
            detail=(
                "Sequence the work so that the first decision can be undone "
                "cheaply. Confidence rises with evidence, not with commitment."
            ),
        ),
        SuggestionBlock(
            label="Continue",
            items=[
                "Go deeper on the constraint",
                "Turn this into a plan",
                "Challenge the assumptions",
            ],
        ),
    ),
    follow_ups=("Go deeper on the constraint", "Turn this into a plan"),
)

_VOICE_RESPONSES: tuple[str, ...] = (
    "I have the context. The constraint is clearance time, not capacity — that is where I would look first.",
    "Three sources agree, one disagrees. The dissenting source is the most recent, so I would weight it carefully rather than discard it.",
    "Done. I staged the change so the first step is fully reversible, and I flagged the one decision that should not be automated.",
    "The headline number improves by fourteen percent, but the more useful finding is where it breaks.",
)


def _stable_hash(value: str) -> int:
    """Process-independent hash.

    Python's built-in `hash()` is salted per process, which would make voice
    reply selection non-deterministic across restarts and test runs.
    """
    result = 2166136261
    for char in value:
        result = ((result ^ ord(char)) * 16777619) & 0xFFFFFFFF
    return result


def token_estimate(text: str) -> int:
    """Cheap, stable token proxy (~3.6 chars/token), matching the frontend."""
    return max(1, round(len(text) / 3.6))


def _traces(recipe: _Recipe, turn_id: str) -> list[ToolTraceSchema]:
    return [
        ToolTraceSchema(
            id=f"tr-{turn_id}-{index}",
            name=trace.name,
            detail=trace.detail,
            state="done",
            duration_ms=trace.ms,
        )
        for index, trace in enumerate(recipe.traces)
    ]


def _count_tokens(blocks: tuple[ContentBlock, ...]) -> int:
    total = 0
    for block in blocks:
        if isinstance(block, TextBlock):
            total += token_estimate(block.body)
        else:
            total += 48
    return total


class SimulatorEngine:
    """Local, deterministic provider used until MODULE 6 lands."""

    name = "simulator"

    def select_recipe(self, prompt: str) -> _Recipe:
        for recipe in _RECIPES:
            if recipe.match.search(prompt):
                return recipe
        return _DEFAULT_RECIPE

    def generate(self, request: EngineRequest) -> EngineTurn:
        prompt = request.prompt.strip()
        turn_id = f"{_stable_hash(prompt):08x}"

        if request.voice:
            return self._voice_turn(prompt, request, turn_id)

        recipe = self.select_recipe(prompt)
        mode_id = recipe.mode or request.mode_id
        blocks = recipe.blocks

        return EngineTurn(
            reasoning=recipe.reasoning,
            traces=_traces(recipe, turn_id),
            blocks=list(blocks),
            mode_id=mode_id,
            tokens=_count_tokens(blocks),
            route=recipe.key,
            follow_ups=list(recipe.follow_ups),
        )

    def _voice_turn(
        self, prompt: str, request: EngineRequest, turn_id: str
    ) -> EngineTurn:
        index = _stable_hash(prompt) % len(_VOICE_RESPONSES)
        body = _VOICE_RESPONSES[index]
        block = TextBlock(body=body)
        return EngineTurn(
            reasoning="Live voice turn — transcribed, intent-classified and answered.",
            traces=[
                ToolTraceSchema(
                    id=f"tr-{turn_id}-asr",
                    name="Speech Transcribe",
                    detail="streaming ASR",
                    state="done",
                    duration_ms=410,
                ),
            ],
            blocks=[block],
            mode_id="voice",
            tokens=token_estimate(body),
            route="voice",
            follow_ups=[],
        )


simulator_engine = SimulatorEngine()