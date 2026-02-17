"""
Abstract base class for illustration providers.

Implement this interface to add new AI-powered photo-to-illustration backends.
"""

from abc import ABC, abstractmethod
from PIL import Image


class BaseIllustrationProvider(ABC):
    """Abstract base for providers that convert photos to graphic illustrations."""

    # Provider identifier used in settings (e.g. "huggingface", "replicate")
    provider_id: str = ""

    # Human-readable display name
    display_name: str = ""

    # Whether this provider requires an API key
    requires_api_key: bool = False

    # Expected env key for API token (e.g. "HUGGINGFACE_TOKEN")
    expected_key: str = ""

    @abstractmethod
    def to_illustration(self, image: Image.Image, **kwargs) -> Image.Image | None:
        """
        Convert a photo to a graphic illustration.

        Args:
            image: Input PIL Image (photo)
            **kwargs: Provider-specific options (e.g. prompt, style)

        Returns:
            PIL Image (illustration) or None on failure
        """
        pass

    def is_configured(self, api_key: str | None) -> bool:
        """Check if provider has required configuration (e.g. API key)."""
        if not self.requires_api_key:
            return True
        return bool(api_key and api_key.strip())
