import argparse
import sys
from pathlib import Path

from .config import (
    DEFAULT_LOGO_MARGIN,
    DEFAULT_LOGO_OPACITY,
    DEFAULT_LOGO_PATH,
    DEFAULT_LOGO_POSITION,
    DEFAULT_LOGO_SCALE,
    OUTPUT_DIR,
    PROJECT_ID,
    PROMPTS_FILE,
)
from .pipeline import (
    apply_style_pack,
    filter_clips,
    filter_presentation_clips,
    list_all_clips,
    load_clips,
    load_style_packs,
)
from .postprocess import apply_logo_overlay, find_ffmpeg
from .providers import PROVIDER_REGISTRY, get_provider
from .providers.base import GenerationConfig

STYLE_PACKS = load_style_packs()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="ai-video-gen — JSON-driven batch video generation from multiple AI providers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python main.py --dry-run\n"
            "  python main.py --clips clip_1_1a --variants 1\n"
            "  python main.py --presentation --style-pack corporate_clean --variants 2\n"
            "  python main.py --block 'Block 1' --provider veo --logo-overlay\n"
        ),
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate config and preview what would be generated without making API calls.",
    )
    p.add_argument(
        "--clips",
        type=str,
        default="",
        help="Generate only these clips (comma-separated IDs). Example: --clips clip_1_1a,clip_1_1b",
    )
    p.add_argument(
        "--block",
        type=str,
        default="",
        help="Generate only clips from this block. Example: --block 'Block 1'",
    )
    p.add_argument(
        "--variants",
        type=int,
        default=1,
        choices=[1, 2, 3, 4],
        help="Number of variants per clip (1 for testing, 4 for production). Default: 1",
    )
    p.add_argument(
        "--audio",
        action="store_true",
        help="Enable audio generation (provider support may vary).",
    )
    p.add_argument(
        "--list",
        action="store_true",
        help="List all available clips and exit.",
    )
    p.add_argument(
        "--presentation",
        action="store_true",
        help="Use curated presentation sequence (clips with a presentation_order field).",
    )
    p.add_argument(
        "--style-pack",
        type=str,
        default="",
        choices=["", *STYLE_PACKS.keys()],
        help="Apply a style pack for visual consistency across all clips.",
    )
    p.add_argument(
        "--provider",
        type=str,
        default="veo",
        choices=list(PROVIDER_REGISTRY.keys()),
        help="Video generation provider to use. Default: veo",
    )
    p.add_argument(
        "--logo-overlay",
        action="store_true",
        help="Apply a logo overlay to all generated videos (requires ffmpeg).",
    )
    p.add_argument(
        "--logo-path",
        type=str,
        default=str(DEFAULT_LOGO_PATH),
        help=f"Path to the logo PNG file. Default: {DEFAULT_LOGO_PATH}",
    )
    p.add_argument(
        "--logo-position",
        type=str,
        default=DEFAULT_LOGO_POSITION,
        choices=["top-left", "top-right", "bottom-left", "bottom-right", "center"],
        help=f"Logo position on the video. Default: {DEFAULT_LOGO_POSITION}",
    )
    p.add_argument(
        "--logo-scale",
        type=float,
        default=DEFAULT_LOGO_SCALE,
        help=f"Logo scale relative to video width (0.0–1.0). Default: {DEFAULT_LOGO_SCALE}",
    )
    p.add_argument(
        "--logo-opacity",
        type=float,
        default=DEFAULT_LOGO_OPACITY,
        help=f"Logo opacity (0.0–1.0). Default: {DEFAULT_LOGO_OPACITY}",
    )
    p.add_argument(
        "--logo-margin",
        type=int,
        default=DEFAULT_LOGO_MARGIN,
        help=f"Margin from edge in pixels. Default: {DEFAULT_LOGO_MARGIN}",
    )
    return p.parse_args()


def _print_clip_info(clip: dict, variants: int, dry_run: bool) -> None:
    tag = "[DRY-RUN] " if dry_run else ""
    print(f"\n{'='*70}")
    print(f"{tag}[{clip['clip_id']}] {clip['block']} / {clip['scene']}")
    print(f"  Prompt       : {clip['prompt'][:120]}...")
    print(f"  Neg. Prompt  : {clip.get('negative_prompt', '(none)')}")
    aspect = clip.get("aspect_ratio", "16:9")
    print(f"  Duration     : {clip['duration']}s | Aspect: {aspect} | Variants: {variants}")

    ref = clip.get("reference_image_path", "")
    if ref:
        status = "OK" if Path(ref).exists() else "MISSING"
        print(f"  Ref. Image   : {ref} [{status}]")
    else:
        print("  Ref. Image   : (none — text only)")

    if clip.get("notes"):
        print(f"  Notes        : {clip['notes']}")

    pres_order = clip.get("presentation_order")
    if pres_order is not None:
        section = clip.get("presentation_section", "")
        adj = clip.get("presentation_adjustments", "")
        print(f"  Presentation : #{pres_order} [{section}]")
        if adj:
            print(f"  Adjustments  : {adj}")


def _validate_setup(clips: list[dict], args: argparse.Namespace, provider) -> list[str]:
    """Validate configuration; return a list of warning strings."""
    warnings: list[str] = []

    warnings.extend(provider.validate())

    missing_images = [
        f"  - {c['clip_id']}: {c['reference_image_path']}"
        for c in clips
        if c.get("reference_image_path") and not Path(c["reference_image_path"]).exists()
    ]
    if missing_images:
        warnings.append("Missing reference images:\n" + "\n".join(missing_images))

    if args.logo_overlay:
        if not find_ffmpeg():
            warnings.append(
                "ffmpeg not found (not in PATH, imageio-ffmpeg unavailable). "
                "--logo-overlay will be skipped."
            )
        if not Path(args.logo_path).exists():
            warnings.append(
                f"Logo file not found: {args.logo_path}. --logo-overlay will be skipped."
            )

    return warnings


def main() -> None:
    args = parse_args()

    if not PROMPTS_FILE.exists():
        print(f"ERROR: Prompts file not found: {PROMPTS_FILE}")
        print("Copy the example and customise it:")
        print("  cp examples/prompts.example.json input/prompts.json")
        sys.exit(1)

    all_clips = load_clips(PROMPTS_FILE)

    if args.list:
        list_all_clips(all_clips, presentation_only=args.presentation)
        return

    if args.presentation:
        clips = filter_presentation_clips(all_clips)
    else:
        clips = filter_clips(all_clips, args.clips, args.block)

    if not clips:
        print("ERROR: No clips found with the specified filters.")
        print("Use --list to see available clips.")
        return

    if args.style_pack:
        clips = [apply_style_pack(c, args.style_pack, STYLE_PACKS) for c in clips]

    ProviderClass = get_provider(args.provider)
    provider = ProviderClass()

    print(f"\n{'#'*70}")
    mode = "DRY-RUN (no API calls)" if args.dry_run else "GENERATION"
    print(f"  MODE              : {mode}")
    if args.presentation:
        print(f"  Sequence          : PRESENTATION (narrative order)")
    print(f"  Provider          : {args.provider}")
    print(f"  Clips selected    : {len(clips)} of {len(all_clips)}")
    print(f"  Variants per clip : {args.variants}")
    print(f"  Audio             : {'yes' if args.audio else 'no'}")
    if args.style_pack:
        print(f"  Style pack        : {args.style_pack}")
    if args.logo_overlay:
        print(
            f"  Logo overlay      : {args.logo_path} "
            f"({args.logo_position}, scale={args.logo_scale}, opacity={args.logo_opacity})"
        )
    print(f"{'#'*70}")

    warnings = _validate_setup(clips, args, provider)
    if warnings:
        print("\n  WARNINGS:")
        for w in warnings:
            print(f"    ! {w}")

    if args.provider == "veo" and not PROJECT_ID:
        raise SystemExit("\nERROR: PROJECT_ID is not set. Check your .env file.")

    if args.dry_run:
        print("\n--- CLIP PREVIEW ---")
        for clip in clips:
            _print_clip_info(clip, args.variants, dry_run=True)
        total = sum(c["duration"] for c in clips)
        missing_ref = sum(
            1
            for c in clips
            if c.get("reference_image_path") and not Path(c["reference_image_path"]).exists()
        )
        print(f"\n{'='*70}")
        print("DRY-RUN SUMMARY:")
        print(f"  Clips to generate    : {len(clips)}")
        print(f"  Total videos (x{args.variants})  : {len(clips) * args.variants}")
        print(f"  Total clip duration  : {total}s")
        print(f"  Missing ref images   : {missing_ref}")
        if args.logo_overlay:
            print("  Logo overlay         : yes (applied after generation)")
        print("\nReady? Run without --dry-run to generate.")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    logo_path = Path(args.logo_path) if args.logo_overlay else None
    if args.logo_overlay and (not find_ffmpeg() or not Path(args.logo_path).exists()):
        print("\n  WARNING: Logo overlay disabled (ffmpeg or logo file missing).")
        logo_path = None

    results: list[dict] = []
    for clip in clips:
        _print_clip_info(clip, args.variants, dry_run=False)
        try:
            gen_config = GenerationConfig(
                aspect_ratio=clip.get("aspect_ratio", "16:9"),
                duration_seconds=clip.get("duration", 8),
                number_of_videos=args.variants,
                enable_audio=args.audio,
                negative_prompt=clip.get("negative_prompt", ""),
                output_dir=OUTPUT_DIR,
            )
            video_results = provider.generate(
                clip_id=clip["clip_id"],
                prompt=clip["prompt"],
                config=gen_config,
                image_path=clip.get("reference_image_path"),
            )

            if logo_path and logo_path.exists() and video_results:
                print(f"  [{clip['clip_id']}] Applying logo overlay...")
                for vr in video_results:
                    vr.path = apply_logo_overlay(
                        vr.path,
                        logo_path,
                        args.logo_position,
                        args.logo_scale,
                        args.logo_opacity,
                        args.logo_margin,
                    )

            results.append(
                {
                    "clip_id": clip["clip_id"],
                    "outputs": [str(vr.path) for vr in video_results],
                    "status": "ok" if video_results else "no video",
                }
            )
        except Exception as exc:
            print(f"  [{clip['clip_id']}] FAILED: {exc}")
            results.append(
                {
                    "clip_id": clip["clip_id"],
                    "outputs": [],
                    "status": f"error: {exc}",
                }
            )

    print(f"\n{'='*70}")
    print("GENERATION SUMMARY")
    print(f"{'='*70}")
    ok = sum(1 for r in results if r["status"] == "ok")
    fail = len(results) - ok
    for r in results:
        icon = "+" if r["status"] == "ok" else "X"
        files = ", ".join(r["outputs"]) if r["outputs"] else "N/A"
        print(f"  [{icon}] {r['clip_id']}: {r['status']} -> {files}")
    print(f"\n  OK: {ok} | Failed: {fail} | Total: {len(results)}")
