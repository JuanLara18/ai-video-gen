# Providers

ai-video-gen uses a provider abstraction so you can swap or add video generation backends without touching the pipeline logic.

---

## Available Providers

| Provider | Flag | Status | Docs |
|----------|------|--------|------|
| Google Veo (Vertex AI) | `--provider veo` | Available | See below |
| Runway Gen-3/Gen-4 | `--provider runway` | Coming soon | — |
| Kling | `--provider kling` | Coming soon | — |
| MiniMax / Hailuo | `--provider minimax` | Coming soon | — |
| OpenAI Sora | `--provider sora` | Coming soon | — |

---

## How Providers Work

Every provider is a Python class that subclasses `BaseProvider` from
`ai_video_gen/providers/base.py`. The pipeline calls two methods:

```python
provider.validate() -> list[str]     # check config, return warnings
provider.generate(...)  -> list[VideoResult]  # run generation, save files
```

The CLI resolves the provider at runtime using a registry dict in
`ai_video_gen/providers/__init__.py`.

---

## Adding a New Provider

Follow these steps to add support for any video generation API.

### Step 1 — Create the provider file

Create `ai_video_gen/providers/myprovider.py`:

```python
from pathlib import Path
from .base import BaseProvider, GenerationConfig, VideoResult


class MyProvider(BaseProvider):
    """
    Short description of this provider.

    Required environment variables:
        MY_API_KEY — API key for the service
    """

    name = "myprovider"

    def __init__(self, api_key: str = "") -> None:
        import os
        self.api_key = api_key or os.getenv("MY_API_KEY", "")

    def validate(self) -> list[str]:
        warnings: list[str] = []
        if not self.api_key:
            warnings.append("MY_API_KEY is not set in .env")
        return warnings

    def generate(
        self,
        clip_id: str,
        prompt: str,
        config: GenerationConfig,
        image_path: str | None = None,
    ) -> list[VideoResult]:
        config.output_dir.mkdir(parents=True, exist_ok=True)
        results: list[VideoResult] = []

        for i in range(config.number_of_videos):
            # --- Call your API here ---
            # video_bytes = my_api_client.generate(prompt, ...)
            # --------------------------

            suffix = f"_v{i + 1}" if config.number_of_videos > 1 else ""
            output_path = config.output_dir / f"{clip_id}{suffix}.mp4"

            # Save the result
            # output_path.write_bytes(video_bytes)

            results.append(
                VideoResult(
                    path=output_path,
                    provider=self.name,
                    clip_id=clip_id,
                    variant=i + 1,
                    metadata={},
                )
            )

        return results
```

### Step 2 — Register the provider

Open `ai_video_gen/providers/__init__.py` and add your provider:

```python
from .myprovider import MyProvider

PROVIDER_REGISTRY: dict[str, type[BaseProvider]] = {
    "veo": VeoProvider,
    "myprovider": MyProvider,   # add this line
}
```

### Step 3 — Document environment variables

Add the required env vars to `.env.example`:

```env
# --- My Provider ---
MY_API_KEY=your-api-key-here
```

### Step 4 — Add optional dependencies (if needed)

If your provider requires extra packages, add them as an optional group in
`pyproject.toml`:

```toml
[project.optional-dependencies]
myprovider = ["my-provider-sdk>=1.0.0"]
```

### Step 5 — Use it

```bash
pip install -e ".[myprovider]"
python main.py --provider myprovider --clips clip_1_1a
```

---

## BaseProvider Reference

```python
@dataclass
class GenerationConfig:
    aspect_ratio: str = "16:9"
    duration_seconds: int = 8
    number_of_videos: int = 1
    enable_audio: bool = False
    negative_prompt: str = ""
    output_dir: Path = Path("output")

@dataclass
class VideoResult:
    path: Path          # absolute path to the saved MP4
    provider: str       # provider name string
    clip_id: str        # clip_id from the prompts JSON
    variant: int = 1    # variant number (1-based)
    metadata: dict      # provider-specific metadata

class BaseProvider(ABC):
    name: str

    def validate(self) -> list[str]: ...
    def generate(
        self,
        clip_id: str,
        prompt: str,
        config: GenerationConfig,
        image_path: str | None = None,
    ) -> list[VideoResult]: ...
```

---

## Contributing a Provider

Contributions are welcome! If you implement a new provider, please open a pull
request with:

1. The provider file (`ai_video_gen/providers/yourprovider.py`)
2. Registration in `__init__.py`
3. Updated `.env.example`
4. A brief section added to this document

See the [GitHub Issues](https://github.com/JuanLara18/ai-video-gen/issues) page
for providers that are actively being requested.
