import argparse
import json
import mimetypes
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

PROJECT_ID = os.getenv("PROJECT_ID")
LOCATION = os.getenv("LOCATION", "us-central1")
GCS_BUCKET = os.getenv("GCS_BUCKET", "").strip()

MODEL = "veo-3.1-generate-001"
PROMPTS_FILE = Path("input/prompts.json")
PRESENTATION_FILE = Path("input/presentation_sequence.json")
OUTPUT_DIR = Path("output")
POLL_INTERVAL_SECONDS = 15

STYLE_PACKS_FILE = Path("style_packs.json")

def load_style_packs() -> dict[str, dict]:
    """Load style packs from JSON file if it exists, otherwise use built-in defaults."""
    if STYLE_PACKS_FILE.exists():
        with open(STYLE_PACKS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "corporate_clean": {
            "style_suffix": (
                "Consistent corporate visual identity throughout. "
                "Clean, modern, professional cinematography. "
                "No amateur or stock-footage feel."
            ),
            "negative_prompt_base": (
                "text on screen, subtitles, watermark, face distortion, morphing, "
                "warping, inconsistent branding, wrong logo, misspelled text, "
                "low quality, blurry, amateur look"
            ),
        },
    }

STYLE_PACKS: dict[str, dict] = load_style_packs()

DEFAULT_LOGO_PATH = Path("input/images/logo.png")
DEFAULT_LOGO_POSITION = "bottom-right"
DEFAULT_LOGO_SCALE = 0.08
DEFAULT_LOGO_OPACITY = 0.85
DEFAULT_LOGO_MARGIN = 30


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Veo 3.1 Video Pipeline — structured video generation from JSON prompts")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Valida configuracion, muestra lo que haria, pero NO llama a la API.",
    )
    p.add_argument(
        "--clips",
        type=str,
        default="",
        help="Generar solo estos clips (IDs separados por coma). Ej: --clips clip_1_1a,clip_1_1b",
    )
    p.add_argument(
        "--block",
        type=str,
        default="",
        help="Generar solo clips de este bloque. Ej: --block 'Bloque 1'",
    )
    p.add_argument(
        "--variants",
        type=int,
        default=1,
        choices=[1, 2, 3, 4],
        help="Numero de variantes por clip (1 para test, 4 para produccion). Default: 1",
    )
    p.add_argument(
        "--audio",
        action="store_true",
        help="Habilitar generacion de audio (puede no estar soportado en todos los modelos).",
    )
    p.add_argument(
        "--list",
        action="store_true",
        help="Lista todos los clips disponibles y sale.",
    )

    p.add_argument(
        "--presentation",
        action="store_true",
        help="Usar secuencia curada de presentacion (input/presentation_sequence.json).",
    )
    p.add_argument(
        "--style-pack",
        type=str,
        default="",
        choices=["", *STYLE_PACKS.keys()],
        help="Aplicar style pack para coherencia visual transversal. Ej: --style-pack falabella_v1",
    )
    p.add_argument(
        "--logo-overlay",
        action="store_true",
        help="Aplicar logo overlay a los videos generados (requiere ffmpeg).",
    )
    p.add_argument(
        "--logo-path",
        type=str,
        default=str(DEFAULT_LOGO_PATH),
        help=f"Ruta al archivo del logo PNG. Default: {DEFAULT_LOGO_PATH}",
    )
    p.add_argument(
        "--logo-position",
        type=str,
        default=DEFAULT_LOGO_POSITION,
        choices=["top-left", "top-right", "bottom-left", "bottom-right", "center"],
        help=f"Posicion del logo en el video. Default: {DEFAULT_LOGO_POSITION}",
    )
    p.add_argument(
        "--logo-scale",
        type=float,
        default=DEFAULT_LOGO_SCALE,
        help=f"Escala del logo relativa al ancho del video (0.0-1.0). Default: {DEFAULT_LOGO_SCALE}",
    )
    p.add_argument(
        "--logo-opacity",
        type=float,
        default=DEFAULT_LOGO_OPACITY,
        help=f"Opacidad del logo (0.0-1.0). Default: {DEFAULT_LOGO_OPACITY}",
    )
    p.add_argument(
        "--logo-margin",
        type=int,
        default=DEFAULT_LOGO_MARGIN,
        help=f"Margen en pixeles desde el borde. Default: {DEFAULT_LOGO_MARGIN}",
    )

    return p.parse_args()


# ---------------------------------------------------------------------------
# Style normalizer
# ---------------------------------------------------------------------------

def apply_style_pack(clip: dict, style_pack_name: str) -> dict:
    """Returns a copy of the clip with style pack applied to prompt and negative_prompt."""
    if not style_pack_name or style_pack_name not in STYLE_PACKS:
        return clip

    pack = STYLE_PACKS[style_pack_name]
    clip = dict(clip)

    suffix = pack.get("style_suffix", "")
    if suffix and suffix not in clip.get("prompt", ""):
        clip["prompt"] = clip["prompt"].rstrip(". ") + ". " + suffix

    neg_base = pack.get("negative_prompt_base", "")
    if neg_base:
        existing_neg = clip.get("negative_prompt", "")
        merged_parts: list[str] = []
        if existing_neg:
            merged_parts.extend(
                p.strip() for p in existing_neg.split(",") if p.strip()
            )
        for part in neg_base.split(","):
            part = part.strip()
            if part and part.lower() not in {m.lower() for m in merged_parts}:
                merged_parts.append(part)
        clip["negative_prompt"] = ", ".join(merged_parts)

    return clip


# ---------------------------------------------------------------------------
# Presentation sequence
# ---------------------------------------------------------------------------

def load_presentation_sequence(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def filter_presentation_clips(all_clips: list[dict]) -> list[dict]:
    """Return only clips with presentation_order, sorted by that order."""
    pres_clips = [c for c in all_clips if c.get("presentation_order") is not None]
    pres_clips.sort(key=lambda c: c["presentation_order"])
    return pres_clips


# ---------------------------------------------------------------------------
# Logo overlay (ffmpeg)
# ---------------------------------------------------------------------------

def find_ffmpeg() -> str | None:
    """Find ffmpeg: system PATH first, then imageio-ffmpeg bundled binary."""
    path = shutil.which("ffmpeg")
    if path:
        return path
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return None


def compute_overlay_position(
    position: str, margin: int, scale_expr: str
) -> str:
    """Build ffmpeg overlay position expression."""
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
    """Overlay logo on video using ffmpeg. Returns path to the output file."""
    output_path = video_path.with_stem(video_path.stem + "_logo")

    scale_filter = f"scale=iw*{scale}:-1"
    if opacity < 1.0:
        scale_filter += f",format=rgba,colorchannelmixer=aa={opacity}"

    pos_expr = compute_overlay_position(position, margin, "")

    ffmpeg_bin = find_ffmpeg()
    if not ffmpeg_bin:
        print(f"  LOGO ERROR: ffmpeg no encontrado")
        return video_path

    cmd = [
        ffmpeg_bin, "-y",
        "-i", str(video_path),
        "-i", str(logo_path),
        "-filter_complex",
        f"[1:v]{scale_filter}[logo];[0:v][logo]overlay={pos_expr}",
        "-codec:a", "copy",
        str(output_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  LOGO ERROR: ffmpeg fallo para {video_path.name}")
        print(f"    stderr: {result.stderr[:300]}")
        return video_path

    print(f"  LOGO OK -> {output_path}")
    return output_path


# ---------------------------------------------------------------------------
# Core functions (unchanged logic)
# ---------------------------------------------------------------------------

def init_client() -> genai.Client:
    return genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)


def load_clips(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def filter_clips(
    clips: list[dict], clip_ids: str, block_filter: str
) -> list[dict]:
    if clip_ids:
        ids = {c.strip() for c in clip_ids.split(",")}
        clips = [c for c in clips if c["clip_id"] in ids]
    if block_filter:
        clips = [c for c in clips if block_filter.lower() in c["block"].lower()]
    return clips


def load_image(image_path: str) -> types.Image | None:
    if not image_path:
        return None
    p = Path(image_path)
    if not p.exists():
        return None
    mime, _ = mimetypes.guess_type(str(p))
    return types.Image(
        image_bytes=p.read_bytes(),
        mime_type=mime or "image/png",
    )


def download_from_gcs(gcs_uri: str, local_path: Path) -> None:
    from google.cloud import storage as gcs

    uri_body = gcs_uri.replace("gs://", "")
    bucket_name, blob_path = uri_body.split("/", 1)

    storage_client = gcs.Client(project=PROJECT_ID)
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    blob.download_to_filename(str(local_path))


def print_clip_info(clip: dict, variants: int, dry_run: bool) -> None:
    tag = "[DRY-RUN] " if dry_run else ""
    print(f"\n{'='*70}")
    print(f"{tag}[{clip['clip_id']}] {clip['block']} / {clip['scene']}")
    print(f"  Prompt    : {clip['prompt'][:120]}...")
    print(f"  Neg.Prompt: {clip.get('negative_prompt', '(ninguno)')}")
    print(f"  Duracion  : {clip['duration']}s | Aspecto: 16:9 | Variantes: {variants}")

    ref = clip.get("reference_image_path", "")
    if ref:
        exists = Path(ref).exists()
        status = "OK" if exists else "FALTA"
        print(f"  Imagen ref: {ref} [{status}]")
    else:
        print("  Imagen ref: (ninguna, solo texto)")

    if clip.get("notes"):
        print(f"  Notas     : {clip['notes']}")

    pres_order = clip.get("presentation_order")
    if pres_order is not None:
        section = clip.get("presentation_section", "")
        adj = clip.get("presentation_adjustments", "")
        print(f"  Presentac.: #{pres_order} [{section}]")
        if adj:
            print(f"  Ajustes   : {adj}")


def generate_clip_video(
    client: genai.Client, clip: dict, variants: int, enable_audio: bool
) -> list[Path]:
    clip_id = clip["clip_id"]
    prompt = clip["prompt"]
    neg_prompt = clip.get("negative_prompt", "")
    image_path = clip.get("reference_image_path", "")
    duration = clip.get("duration", 8)

    image = load_image(image_path)

    config_kwargs: dict = {
        "aspect_ratio": "16:9",
        "duration_seconds": duration,
        "number_of_videos": variants,
    }
    if enable_audio:
        config_kwargs["generate_audio"] = True
    if neg_prompt:
        config_kwargs["negative_prompt"] = neg_prompt
    if GCS_BUCKET:
        config_kwargs["output_gcs_uri"] = f"gs://{GCS_BUCKET}/veo-output/{clip_id}"

    config = types.GenerateVideosConfig(**config_kwargs)

    api_kwargs: dict = {"model": MODEL, "prompt": prompt, "config": config}
    if image:
        api_kwargs["image"] = image

    operation = client.models.generate_videos(**api_kwargs)
    op_name = getattr(operation, "name", "N/A")
    print(f"  [{clip_id}] Operation: {op_name}")

    print(f"  [{clip_id}] Esperando resultado (polling cada {POLL_INTERVAL_SECONDS}s)...")
    elapsed = 0
    while not operation.done:
        time.sleep(POLL_INTERVAL_SECONDS)
        elapsed += POLL_INTERVAL_SECONDS
        operation = client.operations.get(operation)
        print(f"  [{clip_id}] Procesando... ({elapsed}s)")

    if hasattr(operation, "error") and operation.error:
        print(f"  [{clip_id}] OPERATION ERROR: {operation.error}")

    response = operation.response
    if not response:
        response = getattr(operation, "result", None)

    filtered = getattr(response, "rai_media_filtered_count", 0)
    if filtered:
        reasons = getattr(response, "rai_media_filtered_reasons", [])
        print(f"  [{clip_id}] AVISO: {filtered} video(s) filtrados por seguridad. Razones: {reasons}")

    if not response or not getattr(response, "generated_videos", None):
        print(f"  [{clip_id}] ERROR: La API no devolvio video.")
        return []

    saved: list[Path] = []
    for i, gen_video in enumerate(response.generated_videos):
        suffix = f"_v{i+1}" if variants > 1 else ""
        output_path = OUTPUT_DIR / f"{clip_id}{suffix}.mp4"

        video_uri = getattr(gen_video.video, "uri", None)
        if GCS_BUCKET and video_uri:
            print(f"  [{clip_id}] Descargando v{i+1} desde GCS: {video_uri}")
            download_from_gcs(video_uri, output_path)
        else:
            client.files.download(file=gen_video.video)
            gen_video.video.save(str(output_path))

        print(f"  [{clip_id}] Video guardado -> {output_path}")
        saved.append(output_path)

    return saved


def validate_setup(clips: list[dict], args: argparse.Namespace) -> list[str]:
    """Validates config and returns list of warnings."""
    warnings: list[str] = []

    if not PROJECT_ID:
        warnings.append("PROJECT_ID no esta definido en .env")
    if not GCS_BUCKET:
        warnings.append("GCS_BUCKET esta vacio. Se intentara descarga directa (puede fallar en Vertex AI).")

    missing_images = []
    for clip in clips:
        ref = clip.get("reference_image_path", "")
        if ref and not Path(ref).exists():
            missing_images.append(f"  - {clip['clip_id']}: {ref}")

    if missing_images:
        warnings.append(
            "Imagenes de referencia faltantes:\n" + "\n".join(missing_images)
        )

    if args.logo_overlay:
        if not find_ffmpeg():
            warnings.append("ffmpeg no encontrado (ni en PATH ni via imageio-ffmpeg). --logo-overlay no funcionara.")
        logo = Path(args.logo_path)
        if not logo.exists():
            warnings.append(f"Logo no encontrado: {logo}. --logo-overlay no funcionara.")

    return warnings


def list_all_clips(clips: list[dict], presentation_only: bool = False) -> None:
    if presentation_only:
        clips = filter_presentation_clips(clips)
        print(f"\n{'='*70}")
        print(f"PRESENTACION: {len(clips)} clips (orden narrativo)")
        print(f"{'='*70}")
        for clip in clips:
            ref = clip.get("reference_image_path", "")
            ref_icon = " [IMG]" if ref else ""
            has_img = " OK" if ref and Path(ref).exists() else (" FALTA" if ref else "")
            section = clip.get("presentation_section", "?")
            order = clip.get("presentation_order", "?")
            adj = " *AJUSTES*" if clip.get("presentation_adjustments") else ""
            var = f" (variante de {clip['variant_of']})" if clip.get("variant_of") else ""
            print(
                f"  #{order:>2} [{section:>10}] {clip['clip_id']:25s} "
                f"{clip['duration']}s{ref_icon}{has_img}{adj}{var}  {clip['scene']}"
            )
    else:
        print(f"\n{'='*70}")
        print(f"TOTAL: {len(clips)} clips")
        print(f"{'='*70}")

        current_block = ""
        for clip in clips:
            if clip["block"] != current_block:
                current_block = clip["block"]
                print(f"\n  [{current_block}]")

            ref = clip.get("reference_image_path", "")
            ref_icon = " [IMG]" if ref else ""
            has_img = " OK" if ref and Path(ref).exists() else (" FALTA" if ref else "")
            pres = f" P#{clip['presentation_order']}" if clip.get("presentation_order") is not None else ""
            print(f"    {clip['clip_id']:25s} {clip['duration']}s{ref_icon}{has_img}{pres}  {clip['scene']}")

    total_seconds = sum(c["duration"] for c in clips)
    print(f"\n  Duracion total de clips: {total_seconds}s ({total_seconds/60:.1f} min)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    all_clips = load_clips(PROMPTS_FILE)

    if args.list:
        list_all_clips(all_clips, presentation_only=args.presentation)
        return

    if args.presentation:
        clips = filter_presentation_clips(all_clips)
    else:
        clips = filter_clips(all_clips, args.clips, args.block)

    if not clips:
        print("ERROR: No se encontraron clips con los filtros indicados.")
        print("Usa --list para ver los clips disponibles.")
        return

    if args.style_pack:
        clips = [apply_style_pack(c, args.style_pack) for c in clips]

    print(f"\n{'#'*70}")
    mode = "DRY-RUN (sin llamadas a la API)" if args.dry_run else "GENERACION"
    print(f"  MODO: {mode}")
    if args.presentation:
        print(f"  Secuencia : PRESENTACION (orden narrativo)")
    print(f"  Clips seleccionados: {len(clips)} de {len(all_clips)}")
    print(f"  Variantes por clip : {args.variants}")
    print(f"  Modelo             : {MODEL}")
    print(f"  Proyecto           : {PROJECT_ID}")
    print(f"  Bucket GCS         : {GCS_BUCKET or '(no configurado)'}")
    print(f"  Audio              : {'SI' if args.audio else 'NO'}")
    if args.style_pack:
        print(f"  Style Pack         : {args.style_pack}")
    if args.logo_overlay:
        print(f"  Logo Overlay       : {args.logo_path} ({args.logo_position}, scale={args.logo_scale}, opacity={args.logo_opacity})")
    print(f"{'#'*70}")

    warnings = validate_setup(clips, args)
    if warnings:
        print("\n  ADVERTENCIAS:")
        for w in warnings:
            print(f"    ! {w}")

    if not PROJECT_ID:
        raise SystemExit("\nERROR: PROJECT_ID no esta definido. Revisa tu archivo .env")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        print("\n--- PREVIEW DE CLIPS ---")
        for clip in clips:
            print_clip_info(clip, args.variants, dry_run=True)
        total = sum(c["duration"] for c in clips)
        cost_clips = len(clips) * args.variants
        print(f"\n{'='*70}")
        print(f"DRY-RUN RESUMEN:")
        print(f"  Clips a generar      : {len(clips)}")
        print(f"  Videos totales (x{args.variants}) : {cost_clips}")
        print(f"  Duracion total clips : {total}s")
        print(f"  Imagenes faltantes   : {sum(1 for c in clips if c.get('reference_image_path') and not Path(c['reference_image_path']).exists())}")
        if args.logo_overlay:
            print(f"  Logo overlay         : SI (se aplicara despues de generar)")
        print(f"\nTodo listo? Ejecuta sin --dry-run para generar.")
        return

    client = init_client()
    print(f"\nCliente Vertex AI inicializado correctamente.")

    logo_path = Path(args.logo_path) if args.logo_overlay else None
    if args.logo_overlay and not find_ffmpeg():
        print("\n  AVISO: ffmpeg no encontrado. Logo overlay deshabilitado.")
        logo_path = None

    results: list[dict] = []
    for clip in clips:
        print_clip_info(clip, args.variants, dry_run=False)
        try:
            paths = generate_clip_video(client, clip, args.variants, args.audio)

            if logo_path and logo_path.exists() and paths:
                print(f"  [{clip['clip_id']}] Aplicando logo overlay...")
                logo_paths = []
                for vp in paths:
                    lp = apply_logo_overlay(
                        vp, logo_path,
                        args.logo_position, args.logo_scale,
                        args.logo_opacity, args.logo_margin,
                    )
                    logo_paths.append(lp)
                paths = logo_paths

            results.append({
                "clip_id": clip["clip_id"],
                "outputs": [str(p) for p in paths],
                "status": "ok" if paths else "sin video",
            })
        except Exception as exc:
            print(f"  [{clip['clip_id']}] FALLO: {exc}")
            results.append({
                "clip_id": clip["clip_id"],
                "outputs": [],
                "status": f"error: {exc}",
            })

    print(f"\n{'='*70}")
    print("RESUMEN DE GENERACION")
    print(f"{'='*70}")
    ok = sum(1 for r in results if r["status"] == "ok")
    fail = len(results) - ok
    for r in results:
        icon = "+" if r["status"] == "ok" else "X"
        files = ", ".join(r["outputs"]) if r["outputs"] else "N/A"
        print(f"  [{icon}] {r['clip_id']}: {r['status']} -> {files}")
    print(f"\n  OK: {ok} | Fallidos: {fail} | Total: {len(results)}")


if __name__ == "__main__":
    main()
