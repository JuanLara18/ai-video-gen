# AI Video Generation Pipeline

**Batch video generation from structured prompts — multi-provider, CLI-driven, production-ready.**

Define your video as a sequence of clips in a JSON file. The pipeline handles batch generation, style consistency, logo overlays, and multi-variant output — no video editor needed until final assembly.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/JuanLara18/ai-video-gen/pulls)

---

<table>
  <tr>
    <td align="center"><img src="assets/demo_1.gif" width="340"/><br/><sub>🌸 Spring — Cherry blossom rain</sub></td>
    <td align="center"><img src="assets/demo_2.gif" width="340"/><br/><sub>⛈️ Summer — Storm at the edge of the world</sub></td>
  </tr>
  <tr>
    <td align="center"><img src="assets/demo_3.gif" width="340"/><br/><sub>🍂 Autumn — Mirror lake at dawn</sub></td>
    <td align="center"><img src="assets/demo_4.gif" width="340"/><br/><sub>❄️ Winter — Aurora over the frozen forest</sub></td>
  </tr>
</table>

*All four clips generated with this pipeline using Google Veo 3.1 via Vertex AI.*

---

## Features

- **JSON-driven** — describe each clip's camera, subject, action, setting and audio in a structured file
- **Multi-provider** — pluggable architecture; ships with Google Veo, more providers coming
- **Style packs** — enforce visual consistency across all clips with reusable style presets
- **Variants** — generate up to 4 options per clip and pick the best
- **Logo overlay** — burn a PNG logo onto every video via ffmpeg post-processing
- **Dry-run mode** — preview cost and config before spending API credits

---

## Supported Providers

| Provider | Flag | Status |
|----------|------|--------|
| Google Veo 3.1 (Vertex AI) | `--provider veo` | ✅ Available |
| Runway Gen-3 / Gen-4 | `--provider runway` | 🔜 Coming soon |
| Kling | `--provider kling` | 🔜 Coming soon |
| MiniMax / Hailuo | `--provider minimax` | 🔜 Coming soon |
| OpenAI Sora | `--provider sora` | 🔜 Coming soon |

Want to add a provider? See [docs/providers.md](docs/providers.md).

---

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/JuanLara18/ai-video-gen.git
cd ai-video-gen
pip install -e ".[veo]"

# 2. Configure
cp .env.example .env          # add your PROJECT_ID, LOCATION, GCS_BUCKET
cp examples/prompts.example.json input/prompts.json   # edit with your clips

# 3. Generate
python main.py --dry-run      # preview without API calls
python main.py --clips clip_1_1a --variants 2
python main.py --presentation --style-pack corporate_clean --variants 4 --audio
```

→ Full setup (GCP auth, buckets, options reference): [docs/getting-started.md](docs/getting-started.md)

---

## Documentation

| | |
|---|---|
| [Getting started](docs/getting-started.md) | Setup, auth, all CLI options |
| [Prompt engineering](docs/prompt-engineering.md) | Writing prompts that get better results |
| [Style packs](docs/style-packs.md) | Visual consistency across clips |
| [Presentation mode](docs/presentation-mode.md) | Curated narrative sequences |
| [Adding a provider](docs/providers.md) | Extend to any video generation API |

---

## Contributing

Contributions are welcome — especially new provider implementations.
See [docs/providers.md](docs/providers.md) for the step-by-step guide and open a pull request.

---

## License

MIT — see [LICENSE](LICENSE).
