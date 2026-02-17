"""
Modular illustration providers for converting photos to graphic illustrations.

To add a new provider:
1. Create a new module in this package inheriting from BaseIllustrationProvider
2. Register it in the registry via ILLUSTRATION_PROVIDERS

Default: deAPI (https://deapi.ai) - $5 free credits, no credit card required.
"""

from plugins.image_album.illustration_providers.base import BaseIllustrationProvider
from plugins.image_album.illustration_providers.registry import (
    get_illustration_provider,
    ILLUSTRATION_PROVIDERS,
)

__all__ = [
    "BaseIllustrationProvider",
    "get_illustration_provider",
    "ILLUSTRATION_PROVIDERS",
]
