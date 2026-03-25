# Style Packs

Style packs enforce visual consistency across all clips in a batch by appending
a shared style description to every prompt and merging a base set of negative
prompts.

---

## How They Work

When you pass `--style-pack <name>`, the pipeline modifies each clip before
sending it to the API:

1. **Style suffix** — appended to the clip's `prompt` (skipped if already present)
2. **Negative prompt base** — merged with the clip's `negative_prompt` (deduplication applied)

The original clips in your JSON file are never modified.

---

## Built-in Pack

If `style_packs.json` is not found, a single built-in pack is available:

| Pack | Description |
|------|-------------|
| `corporate_clean` | Clean, modern, professional cinematography |

---

## Creating Custom Packs

### 1. Copy the example

```bash
cp examples/style_packs.example.json style_packs.json
```

### 2. Edit or add packs

```json
{
  "my_brand": {
    "style_suffix": "Consistent brand identity. Blue and white colour palette. Premium editorial quality.",
    "negative_prompt_base": "text on screen, watermark, low quality, blurry, amateur look"
  }
}
```

### 3. Use it

```bash
python main.py --style-pack my_brand --variants 1
```

---

## Example Packs

### `corporate_clean`

Good for: B2B videos, product demos, corporate narratives.

```json
{
  "style_suffix": "Consistent corporate visual identity throughout. Clean, modern, professional cinematography. No amateur or stock-footage feel.",
  "negative_prompt_base": "text on screen, subtitles, watermark, face distortion, morphing, warping, inconsistent branding, wrong logo, misspelled text, low quality, blurry, amateur look"
}
```

### `tech_futuristic`

Good for: Tech showcases, AI/data product videos, software demos.

```json
{
  "style_suffix": "Futuristic tech company aesthetic. Dark backgrounds with holographic data visualizations. Neon accents in blue and green.",
  "negative_prompt_base": "text on screen, subtitles, watermark, face distortion, morphing, warping, low quality, blurry, bright daylight"
}
```

### `warm_documentary`

Good for: Brand stories, human-interest content, behind-the-scenes.

```json
{
  "style_suffix": "Warm cinematic documentary look. Natural lighting with golden hour tones. Handheld feel but steady. Authentic, human, inspirational.",
  "negative_prompt_base": "text on screen, subtitles, watermark, face distortion, morphing, warping, neon colors, sci-fi elements"
}
```

---

## Tips

- **Keep style suffixes short** (1–3 sentences). Overly long suffixes can dilute the per-clip prompt.
- **Negative prompts are additive** — the pack's base is merged with each clip's existing negative prompt, never replacing it.
- **Style packs are local** — `style_packs.json` is gitignored so you can maintain brand-specific packs privately.
- **Combine with `--dry-run`** to preview the final merged prompts before spending API credits:

```bash
python main.py --dry-run --style-pack corporate_clean
```
