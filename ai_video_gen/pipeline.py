import json
from pathlib import Path

from .config import STYLE_PACKS_FILE


def load_style_packs() -> dict[str, dict]:
    """Load style packs from ``style_packs.json``, or return built-in defaults."""
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


def apply_style_pack(clip: dict, style_pack_name: str, packs: dict) -> dict:
    """Return a copy of the clip with the named style pack appended to its prompts."""
    if not style_pack_name or style_pack_name not in packs:
        return clip

    pack = packs[style_pack_name]
    clip = dict(clip)

    suffix = pack.get("style_suffix", "")
    if suffix and suffix not in clip.get("prompt", ""):
        clip["prompt"] = clip["prompt"].rstrip(". ") + ". " + suffix

    neg_base = pack.get("negative_prompt_base", "")
    if neg_base:
        existing_neg = clip.get("negative_prompt", "")
        merged: list[str] = []
        if existing_neg:
            merged.extend(p.strip() for p in existing_neg.split(",") if p.strip())
        for part in neg_base.split(","):
            part = part.strip()
            if part and part.lower() not in {m.lower() for m in merged}:
                merged.append(part)
        clip["negative_prompt"] = ", ".join(merged)

    return clip


def load_clips(path: Path) -> list[dict]:
    """Load clip definitions from a JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def filter_clips(clips: list[dict], clip_ids: str, block_filter: str) -> list[dict]:
    """Filter clips by comma-separated IDs and/or a block name substring."""
    if clip_ids:
        ids = {c.strip() for c in clip_ids.split(",")}
        clips = [c for c in clips if c["clip_id"] in ids]
    if block_filter:
        clips = [c for c in clips if block_filter.lower() in c["block"].lower()]
    return clips


def filter_presentation_clips(clips: list[dict]) -> list[dict]:
    """Return only clips that have a ``presentation_order`` field, sorted by it."""
    pres = [c for c in clips if c.get("presentation_order") is not None]
    pres.sort(key=lambda c: c["presentation_order"])
    return pres


def list_all_clips(clips: list[dict], presentation_only: bool = False) -> None:
    """Print a formatted clip listing to stdout."""
    if presentation_only:
        clips = filter_presentation_clips(clips)
        print(f"\n{'='*70}")
        print(f"PRESENTATION: {len(clips)} clips (narrative order)")
        print(f"{'='*70}")
        for clip in clips:
            ref = clip.get("reference_image_path", "")
            ref_icon = " [IMG]" if ref else ""
            img_status = " OK" if ref and Path(ref).exists() else (" MISSING" if ref else "")
            section = clip.get("presentation_section", "?")
            order = clip.get("presentation_order", "?")
            adj = " *ADJUSTMENTS*" if clip.get("presentation_adjustments") else ""
            var = f" (variant of {clip['variant_of']})" if clip.get("variant_of") else ""
            print(
                f"  #{order:>2} [{section:>14}] {clip['clip_id']:25s} "
                f"{clip['duration']}s{ref_icon}{img_status}{adj}{var}  {clip['scene']}"
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
            img_status = " OK" if ref and Path(ref).exists() else (" MISSING" if ref else "")
            pres = (
                f" P#{clip['presentation_order']}"
                if clip.get("presentation_order") is not None
                else ""
            )
            print(
                f"    {clip['clip_id']:25s} {clip['duration']}s"
                f"{ref_icon}{img_status}{pres}  {clip['scene']}"
            )

    total_seconds = sum(c["duration"] for c in clips)
    print(f"\n  Total clip duration: {total_seconds}s ({total_seconds / 60:.1f} min)")
