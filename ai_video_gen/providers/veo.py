import time
from pathlib import Path

from .base import BaseProvider, GenerationConfig, VideoResult
from ..config import (
    GCS_BUCKET,
    LOCATION,
    POLL_INTERVAL_SECONDS,
    PROJECT_ID,
    VEO_MODEL,
)
from ..utils import download_from_gcs, load_image


class VeoProvider(BaseProvider):
    """
    Google Veo video generation via Vertex AI (google-genai SDK).

    Required environment variables:
        PROJECT_ID  — Google Cloud project ID
        LOCATION    — Vertex AI region (default: us-central1)
        GCS_BUCKET  — GCS bucket for output storage (strongly recommended)

    Install dependencies:
        pip install ai-video-gen[veo]
    """

    name = "veo"

    def __init__(
        self,
        project_id: str = PROJECT_ID,
        location: str = LOCATION,
        gcs_bucket: str = GCS_BUCKET,
        model: str = VEO_MODEL,
    ) -> None:
        self.project_id = project_id
        self.location = location
        self.gcs_bucket = gcs_bucket
        self.model = model
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from google import genai  # lazy import

            self._client = genai.Client(
                vertexai=True,
                project=self.project_id,
                location=self.location,
            )
        return self._client

    def validate(self) -> list[str]:
        warnings: list[str] = []
        if not self.project_id:
            warnings.append("PROJECT_ID is not set in .env")
        if not self.gcs_bucket:
            warnings.append(
                "GCS_BUCKET is empty. Direct download will be attempted "
                "(may fail on Vertex AI — set GCS_BUCKET for reliable downloads)."
            )
        return warnings

    def generate(
        self,
        clip_id: str,
        prompt: str,
        config: GenerationConfig,
        image_path: str | None = None,
    ) -> list[VideoResult]:
        from google.genai import types  # lazy import

        image = load_image(image_path) if image_path else None

        config_kwargs: dict = {
            "aspect_ratio": config.aspect_ratio,
            "duration_seconds": config.duration_seconds,
            "number_of_videos": config.number_of_videos,
        }
        if config.enable_audio:
            config_kwargs["generate_audio"] = True
        if config.negative_prompt:
            config_kwargs["negative_prompt"] = config.negative_prompt
        if self.gcs_bucket:
            config_kwargs["output_gcs_uri"] = f"gs://{self.gcs_bucket}/veo-output/{clip_id}"

        gen_config = types.GenerateVideosConfig(**config_kwargs)

        api_kwargs: dict = {
            "model": self.model,
            "prompt": prompt,
            "config": gen_config,
        }
        if image:
            api_kwargs["image"] = image

        operation = self.client.models.generate_videos(**api_kwargs)
        op_name = getattr(operation, "name", "N/A")
        print(f"  [{clip_id}] Operation: {op_name}")
        print(f"  [{clip_id}] Waiting for result (polling every {POLL_INTERVAL_SECONDS}s)...")

        elapsed = 0
        while not operation.done:
            time.sleep(POLL_INTERVAL_SECONDS)
            elapsed += POLL_INTERVAL_SECONDS
            operation = self.client.operations.get(operation)
            print(f"  [{clip_id}] Processing... ({elapsed}s elapsed)")

        if hasattr(operation, "error") and operation.error:
            print(f"  [{clip_id}] OPERATION ERROR: {operation.error}")

        response = operation.response
        if not response:
            response = getattr(operation, "result", None)

        filtered = getattr(response, "rai_media_filtered_count", 0)
        if filtered:
            reasons = getattr(response, "rai_media_filtered_reasons", [])
            print(
                f"  [{clip_id}] WARNING: {filtered} video(s) filtered by safety policy. "
                f"Reasons: {reasons}"
            )

        if not response or not getattr(response, "generated_videos", None):
            print(f"  [{clip_id}] ERROR: API returned no video.")
            return []

        config.output_dir.mkdir(parents=True, exist_ok=True)
        results: list[VideoResult] = []

        for i, gen_video in enumerate(response.generated_videos):
            variant_num = i + 1
            suffix = f"_v{variant_num}" if config.number_of_videos > 1 else ""
            output_path = config.output_dir / f"{clip_id}{suffix}.mp4"

            video_uri = getattr(gen_video.video, "uri", None)
            if self.gcs_bucket and video_uri:
                print(f"  [{clip_id}] Downloading v{variant_num} from GCS: {video_uri}")
                download_from_gcs(video_uri, output_path, self.project_id)
            else:
                self.client.files.download(file=gen_video.video)
                gen_video.video.save(str(output_path))

            print(f"  [{clip_id}] Saved -> {output_path}")
            results.append(
                VideoResult(
                    path=output_path,
                    provider=self.name,
                    clip_id=clip_id,
                    variant=variant_num,
                    metadata={
                        "model": self.model,
                        "gcs_uri": video_uri or "",
                    },
                )
            )

        return results
