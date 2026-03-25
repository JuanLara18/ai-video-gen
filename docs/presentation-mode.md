# Presentation Mode

Presentation mode lets you maintain a large pool of clips in your `prompts.json`
while curating a focused subset for a final, narratively ordered output — without
duplicating prompt definitions.

---

## How It Works

Mark any clip with a `presentation_order` integer to include it in presentation mode:

```json
{
  "clip_id": "clip_2_1a",
  "block": "Block 2 - Data",
  "scene": "Scene 2.1 - Opening data shot",
  "prompt": "...",
  "duration": 8,
  "presentation_order": 1,
  "presentation_section": "INTRO"
}
```

When you run with `--presentation`, only clips that have `presentation_order`
are selected, sorted by that number:

```bash
python main.py --presentation --style-pack corporate_clean --variants 1
```

Clips **without** `presentation_order` are ignored in this mode and can still
be generated independently.

---

## Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `presentation_order` | integer | Yes (to include) | Sort position in the final sequence. Lower = earlier. |
| `presentation_section` | string | No | Section label shown in `--list` output (e.g. `"INTRO"`, `"MAIN"`, `"CLOSING"`) |
| `presentation_adjustments` | string | No | Human notes for last-minute prompt changes before regeneration |

---

## Listing the Presentation Sequence

```bash
python main.py --list --presentation
```

Sample output:

```
======================================================================
PRESENTATION: 3 clips (narrative order)
======================================================================
  # 1 [         INTRO] clip_2_1a                  8s            Scene 2.1 - Opening data shot
  # 2 [  DIGITAL_TWIN] clip_3_1a                  8s *ADJUSTMENTS*  Scene 3.1 - Digitization
  # 3 [       CLOSING] clip_5_1a                  8s [IMG] OK    Scene 5.1 - The future

  Total clip duration: 24s (0.4 min)
```

---

## Dry-Run Before Generating

Always preview the presentation before spending API credits:

```bash
python main.py --dry-run --presentation --style-pack corporate_clean --variants 2
```

This shows the final merged prompts (after style pack) and validates reference images.

---

## Dependency-Aware Generation

Some clips look better if they start from the last frame of the previous clip,
creating a visual continuation. To achieve this:

1. Generate clip N
2. Extract its last frame with ffmpeg:
   ```bash
   ffmpeg -sseof -0.1 -i output/clip_N.mp4 -frames:v 1 input/images/clip_N_lastframe.png
   ```
3. Set that image as the `reference_image_path` for clip N+1 in `prompts.json`
4. Generate clip N+1

This manual step is the most reliable way to chain clips visually.

---

## Full Presentation Workflow

```bash
# 1. Review the curated sequence
python main.py --list --presentation

# 2. Dry-run to validate
python main.py --dry-run --presentation --style-pack corporate_clean

# 3. Generate with 2 variants to pick from
python main.py --presentation --style-pack corporate_clean --variants 2

# 4. (optional) Apply logo overlay to all generated clips
python main.py --presentation --style-pack corporate_clean --variants 1 --logo-overlay

# 5. Find the output files
ls output/
```

Generated files follow the naming pattern `output/{clip_id}[_vN][_logo].mp4`.
Rename and assemble them in your video editor for the final cut.
