import shutil
import subprocess
from pathlib import Path


def find_ffmpeg() -> str | None:
    """Return the path to ffmpeg: system PATH first, then imageio-ffmpeg bundled binary."""
    path = shutil.which("ffmpeg")
    if path:
        return path
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return None


def _overlay_position_expr(position: str, margin: int) -> str:
    """Build an ffmpeg overlay position expression string."""
    positions = {
        "top-left": f"x={margin}:y={margin}",
        "top-right": f"x=W-w-{margin}:y={margin}",
        "bottom-left": f"x={margin}:y=H-h-{margin}",
        "bottom-right": f"x=W-w-{margin}:y=H-h-{margin}",
        "center": "x=(W-w)/2:y=(H-h)/2",
    }
    return positions.get(position, positions["bottom-right"])


def apply_logo_overlay(
    video_path: Path,
    logo_path: Path,
    position: str,
    scale: float,
    opacity: float,
    margin: int,
) -> Path:
    """
    Burn a PNG logo onto a video using ffmpeg.

    The original video is preserved; a new file ``{stem}_logo.mp4`` is created
    alongside it. Returns the path to the new file, or the original path if
    ffmpeg is unavailable or fails.
    """
    output_path = video_path.with_stem(video_path.stem + "_logo")

    scale_filter = f"scale=iw*{scale}:-1"
    if opacity < 1.0:
        scale_filter += f",format=rgba,colorchannelmixer=aa={opacity}"

    pos_expr = _overlay_position_expr(position, margin)
    ffmpeg_bin = find_ffmpeg()

    if not ffmpeg_bin:
        print("  LOGO ERROR: ffmpeg not found")
        return video_path

    cmd = [
        ffmpeg_bin,
        "-y",
        "-i", str(video_path),
        "-i", str(logo_path),
        "-filter_complex",
        f"[1:v]{scale_filter}[logo];[0:v][logo]overlay={pos_expr}",
        "-codec:a", "copy",
        str(output_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  LOGO ERROR: ffmpeg failed for {video_path.name}")
        print(f"    stderr: {result.stderr[:300]}")
        return video_path

    print(f"  LOGO OK -> {output_path}")
    return output_path


def video_to_gif(
    video_path: Path,
    output_path: Path,
    fps: int = 12,
    width: int = 480,
) -> Path | None:
    """
    Convert a video file to an optimised GIF using ffmpeg.

    Uses the two-pass palettegen approach for significantly better colour
    quality than a naive conversion. Returns the output path on success or
    None if ffmpeg is unavailable.
    """
    ffmpeg_bin = find_ffmpeg()
    if not ffmpeg_bin:
        print("  GIF ERROR: ffmpeg not found")
        return None

    palette_path = output_path.with_suffix(".palette.png")
    filters = f"fps={fps},scale={width}:-1:flags=lanczos"

    # Pass 1 — generate optimal palette
    pass1 = [
        ffmpeg_bin, "-y",
        "-i", str(video_path),
        "-vf", f"{filters},palettegen",
        str(palette_path),
    ]
    # Pass 2 — render GIF with palette
    pass2 = [
        ffmpeg_bin, "-y",
        "-i", str(video_path),
        "-i", str(palette_path),
        "-filter_complex", f"{filters}[x];[x][1:v]paletteuse",
        "-loop", "0",
        str(output_path),
    ]

    for cmd in (pass1, pass2):
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  GIF ERROR: {result.stderr[:300]}")
            palette_path.unlink(missing_ok=True)
            return None

    palette_path.unlink(missing_ok=True)
    return output_path
