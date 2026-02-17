"""
Registry for illustration providers. Enables easy scaling by adding new providers.
"""

import logging
from typing import Type

from plugins.image_album.illustration_providers.base import BaseIllustrationProvider
from plugins.image_album.illustration_providers.deapi_provider import (
    DeAPIIllustrationProvider,
)

logger = logging.getLogger(__name__)

# Registry: provider_id -> provider class
# Add new providers here to scale the system
ILLUSTRATION_PROVIDERS: dict[str, Type[BaseIllustrationProvider]] = {
    DeAPIIllustrationProvider.provider_id: DeAPIIllustrationProvider,
}


def get_illustration_provider(
    provider_id: str, api_key: str | None = None, **kwargs
) -> BaseIllustrationProvider | None:
    """
    Factory to get an illustration provider instance.

    Args:
        provider_id: Provider identifier (e.g. "huggingface")
        api_key: API key if required by provider
        **kwargs: Additional constructor args for the provider

    Returns:
        Provider instance or None if not found
    """
    provider_cls = ILLUSTRATION_PROVIDERS.get(provider_id)
    if not provider_cls:
        logger.warning(f"Unknown illustration provider: {provider_id}")
        return None

    try:
        return provider_cls(api_key=api_key, **kwargs)
    except Exception as e:
        logger.error(f"Failed to instantiate provider {provider_id}: {e}")
        return None
