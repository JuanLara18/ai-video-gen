# Prompt Engineering

Well-structured prompts make a significant difference in output quality. This
guide covers the prompt formula used in the example clips and general tips for
each supported provider.

---

## The 5-Part Formula

Every prompt in the examples follows this structure:

```
[Camera movement] + [Subject] + [Action] + [Context/Setting] + [Style & Audio]
```

### Examples

**Aerial establishing shot:**
> Wide aerial crane shot slowly descending over a massive distribution center viewed from above.
> Long aisles with multi-level shelving packed with products stretch in every direction.
> Forklifts circulate between aisles, workers in high-visibility vests walk with order sheets.
> Industrial high-bay lighting, constant movement across the floor.
> Corporate documentary style, 1080p. Audio: Deep ambient hum of machinery, distant forklift beeps.

**Abstract/data visualisation:**
> Slow dolly-in on an elegant dark background with softly glowing data particles floating like dust.
> Subtle green and white light points drift gently through the frame.
> Minimalist, futuristic corporate atmosphere. Calm, sophisticated mood, 1080p.
> Audio: Low ambient electronic hum, soft crystalline chimes.

---

## General Tips

### Camera movement first
Lead with a specific camera movement. Vague descriptions produce generic results.

| Instead of | Try |
|------------|-----|
| "A shot of..." | "Slow dolly-in on..." |
| "Showing the facility" | "Wide aerial crane shot descending over..." |
| "Camera moving through" | "Smooth tracking shot at ground level moving through..." |

**Good camera movements:**
- `Slow dolly-in`, `Slow dolly-out`
- `Wide aerial crane shot descending`
- `Smooth tracking shot at ground level`
- `Handheld close-up`, `Tight close-up with shallow depth of field`
- `Static wide shot`, `Medium shot, locked off`

### One dominant action per clip
A single clear action produces more coherent motion than a list. Reserve scene
complexity for the still composition, not the motion.

### Prompt length
- **Optimal: 80–150 words** (3–5 sentences)
- Too short: model fills gaps with random choices
- Too long: model blends conflicting instructions

### Audio description
Veo can generate matching audio. Include an explicit `Audio:` line at the end:

```
Audio: Deep mechanical hum, distant conveyor belts, faint beeping scanners.
```

Even if you're not using `--audio`, describing audio helps anchor the mood.

### Negative prompts
Always include a negative prompt for stable results:

```
"text on screen, subtitles, watermark, face distortion, morphing, warping, amateur look"
```

Common additions per use case:
- **People shots**: `duplicate people, deformed hands, extra limbs`
- **Product shots**: `clutter, busy backgrounds, lens flare`
- **Data/abstract**: `text, numbers, dashboards, UI elements`

### Reference images
Providing a `reference_image_path` anchors the visual look and reduces variance.
Use real photographs for maximum effect — the model uses it as a style and
composition reference, not a template to replicate exactly.

---

## Provider-Specific Notes

### Google Veo (Vertex AI)

- **Language**: English only (other languages may produce unpredictable results)
- **Durations**: 4, 6, or 8 seconds per clip
- **Aspect ratios**: `16:9` (landscape) or `9:16` (portrait/vertical)
- **Variants**: up to 4 per prompt — generate several and pick the best
- **On-screen text**: not reliable. Add text in post-production
- **Rate limit**: ~50 requests/min/model

### Tips specific to Veo

- **Cinematic terms work well**: "shallow depth of field", "anamorphic lens", "film grain",
  "golden hour", "volumetric lighting"
- **Specify resolution in the prompt**: ending with "1080p" slightly improves sharpness
- **Avoid abstract nouns without visual anchors**: "innovation", "transformation" need
  a concrete visual metaphor to be rendered well
- **Safety policy**: avoid prompts that depict violence, explicit content, or real people
  by name. The API will filter these and return no video (counted against your quota)

---

## Iterating on Results

1. Start with `--variants 2` to see two interpretations of the same prompt
2. Pick the better result and note what visual elements worked
3. Reinforce those elements in the prompt on the next generation
4. Use `--dry-run` to inspect final merged prompts (after style pack) before spending credits

```bash
# Preview what will be sent to the API
python main.py --dry-run --style-pack corporate_clean --presentation
```
