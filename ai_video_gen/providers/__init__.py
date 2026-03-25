from .base import BaseProvider, GenerationConfig, VideoResult
from .veo import VeoProvider

PROVIDER_REGISTRY: dict[str, type[BaseProvider]] = {
    "veo": VeoProvider,
}


def get_provider(name: str) -> type[BaseProvider]:
    """Look up a provider class by name. Raises ValueError for unknown names."""
    if name not in PROVIDER_REGISTRY:
        available = list(PROVIDER_REGISTRY.keys())
        raise ValueError(f"Unknown provider: '{name}'. Available providers: {available}")
    return PROVIDER_REGISTRY[name]


__all__ = [
    "BaseProvider",
    "GenerationConfig",
    "VideoResult",
    "VeoProvider",
    "PROVIDER_REGISTRY",
    "get_provider",
]
