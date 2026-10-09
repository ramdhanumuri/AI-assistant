"""Provider adapters.

Each module here implements `app.ai.base.AIProvider` for one vendor. Nothing
outside this package may import a vendor SDK, so swapping or adding a provider
touches only this directory plus one line in the factory registry.
"""

from app.ai.providers.openai import OpenAIProvider

__all__ = ["OpenAIProvider"]
