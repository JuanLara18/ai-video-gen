from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class GenerationConfig:
    """Parameters for a single video generation call."""

    aspect_ratio: str = "16:9"
    duration_seconds: int = 8
    number_of_videos: int = 1
    enable_audio: bool = False
    negative_prompt: str = ""
    output_dir: Path = field(default_factory=lambda: Path("output"))


@dataclass
class VideoResult:
    """A single successfully generated video with associated metadata."""

    path: Path
    provider: str
    clip_id: str
    variant: int = 1
    metadata: dict = field(default_factory=dict)


class BaseProvider(ABC):
    """
    Abstract base class for all video generation providers.

    To add a new provider, subclass this class and implement `generate` and
    `validate`, then register it in `ai_video_gen/providers/__init__.py`.

    See docs/providers.md for a full step-by-step guide.
    """

    name: str = "base"

    @abstractmethod
    def generate(
        self,
        clip_id: str,
        prompt: str,
        config: GenerationConfig,
        image_path: str | None = None,
    ) -> list[VideoResult]:
        """
        Generate one or more videos from a text prompt.

        Args:
            clip_id:    Unique identifier for this clip (used for output file naming).
            prompt:     Text description of the video to generate.
            config:     Generation parameters (aspect ratio, duration, variants, etc.).
            image_path: Optional path to a reference/start-frame image.

        Returns:
            List of VideoResult objects, one per generated video file.
        """
        ...

    @abstractmethod
    def validate(self) -> list[str]:
        """
        Check provider-level configuration (API keys, project IDs, etc.).

        Returns:
            List of human-readable warning or error strings.
            An empty list means the configuration is valid.
        """
        ...
