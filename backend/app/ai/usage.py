"""Cost foundation.

Cost is only ever computed from pricing the deployment actually configured.
There is no built-in price table: model prices change, differ per region and
per contract, and a hard-coded number would silently become wrong. With the
default zero pricing, `estimate_cost` returns `None`, which the usage row
stores as NULL — "unknown" is the honest value, and a fabricated zero or a
guess would corrupt any downstream spend reporting.

When an operator sets real per-million prices, cost is computed and the
`pricing_version` records which prices were in force, so a historical row stays
interpretable after pricing changes.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from app.ai.types import TokenUsage
from app.core.config import settings

# Costs are stored to this many decimal places. Four is finer than any real
# per-request cost while still exact enough for aggregation.
_COST_QUANTUM = Decimal("0.0001")


def estimate_cost(usage: TokenUsage) -> float | None:
    """Return the cost in the configured currency, or `None` if unknown.

    `None` is returned when no pricing is configured, or when the provider did
    not report the token counts needed to compute it. Both mean "we do not
    know", which must not be conflated with "zero".
    """
    input_price = Decimal(str(settings.AI_INPUT_COST_PER_MILLION))
    output_price = Decimal(str(settings.AI_OUTPUT_COST_PER_MILLION))
    if input_price == 0 and output_price == 0:
        return None
    if usage.input_tokens is None and usage.output_tokens is None:
        return None

    million = Decimal(1_000_000)
    cost = (
        Decimal(usage.input_tokens or 0) * input_price / million
        + Decimal(usage.output_tokens or 0) * output_price / million
    )
    return float(cost.quantize(_COST_QUANTUM, rounding=ROUND_HALF_UP))


def cost_currency() -> str:
    return settings.AI_COST_CURRENCY


def pricing_version() -> str | None:
    """The pricing label recorded with a cost, or `None` when unset."""
    return settings.AI_PRICING_VERSION.strip() or None


__all__ = ["cost_currency", "estimate_cost", "pricing_version"]
