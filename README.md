# Amazon ASIN → 8-Image Compliant Bundle (Playwright + Gemini web)

Give it ASINs. Get back, per ASIN: scraped product data, every base image from the
listing, 8 Amazon-compliant generated images, organised in folders and tracked in a sheet.

**No paid APIs required** — Amazon and Gemini are both driven through a real browser.

```
ASIN list ──► Playwright ──► product.json + base_images/ ──► prompt builder (8 slots)
                                                                     │
               output/<ASIN>/generated/   ◄── auto-download ◄── Playwright drives
               01_hero_white.png ... 08_product_guide.png        gemini.google.com
                                                                     │
                                               tracking.csv / Google Sheet (status per ASIN)
```

**Key features:**
- 🎯 **Fully local prompt gallery** (~280 curated prompts) — no external API keys needed
- 🎨 **Fresh model casting per ASIN** — gallery model-variation prompts select personas
- 🧹 **Automatic watermark removal** — Veo/Gemini sparkle detector + inpainting
- 🔄 **Resumable pipeline** — manifest tracks every slot; re-runs skip completed work
- 📊 **CSV / Google Sheets tracking** — zero-setup CSV backend, optional Sheets
- 🛡️ **Amazon policy compliance baked in** — white background, no text, product fidelity

---

## 1. Install

```bash
cd amazon-image-automation
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium

cp config.example.yaml config.yaml                    # edit to taste
```

## 2. One-time login (important)

Gemini's web UI needs a signed-in Google session. That session is stored in a
persistent Chrome profile (`.browser-profile/`), so you only do this once:

```bash
python run.py login
```

A browser opens → sign in to Google (and Amazon, if you want logged-in pricing/variants)
→ come back to the terminal and press **Enter**. Everything after that runs headless.

## 3. Run

```bash
# dry run first: scrape nothing yet, just prove prompt generation on existing data
python run.py generate --asins data/asins.sample.txt --dry-run

# full pipeline over a whole list
python run.py all --asins data/asins.txt

# single ASIN, watch the browser
python run.py one --asin B0DEMO1234 --headed

# stage by stage
python run.py scrape   --asins data/asins.txt
python run.py generate --asins data/asins.txt

# pass already-generated images through the watermark remover again
python run.py clean --asins data/asins.txt
```

`data/asins.txt` accepts bare ASINs, comma/newline lists, or full Amazon URLs
(`/dp/`, `/gp/product/`), `#` comments ignored.

Useful flags: `--limit 5`, `--force` (regenerate slots already marked ok),
`--notes "keep the brand colour #0B5FFF in callouts"` (appended to every prompt),
`--config other.yaml`.

## 3b. Watermark cleanup (automatic)

Every generated image passes through the local Veo/Gemini watermark remover
(`G:\veo-watermark-remover\...\local_app`, configured in `config.yaml` under
`watermark:`) **before** it counts as final:

- the sparkle mark is detected and inpainted, and the cleaned image **replaces
  the slot file in place** (same path — the download location stays canonical);
- the pre-clean pixels are kept next to it in `generated/_with_watermark/`;
- if no mark is found the image is left untouched (`no-mark`), and any engine
  error never breaks a run — the image is simply kept as generated;
- `run.py clean` retro-cleans existing bundles and writes `clean_report.json`
  plus the per-slot `watermark` record in the manifest.

The remnant QA is two-level: the detector's own gate (IoU ≥ 0.70) re-checks the
output and a wider re-fill runs if the mark still re-detects; the engine's
faint-family verifier only raises a "possible ghost" advisory when the residual
is genuinely visible (> 3 grey levels above the surroundings), so featureless
white hero shots don't produce false alarms.

## 4. What you get

```
output/
└── B0DEMO1234/
    ├── product.json          # title, brand, price, rating, bullets, attributes, variants
    ├── base_images/          # 01.jpg 02.jpg ... hi-res (≥1500px) gallery images, deduped
    ├── prompts/
    │   ├── prompts.json      # all 8 prompts, machine readable
    │   └── prompts.md        # same, readable/reviewable
    ├── generated/            # 01_hero_white.png ... 08_product_guide.png
    ├── manifest.json         # per-slot status → resumable
    └── README.md             # upload checklist for the operator
data/tracking.csv             # one row per ASIN: status, slot count, folder, error
```

## 5. The 8 slots (AIIE studio pack)

| # | File | Purpose |
|---|------|---------|
| 1 | `01_hero_white.png` | Amazon MAIN image — fresh-cast model on pure white, no text (policy-critical, always the built-in AIIE template) |
| 2 | `02_back_view.png` | Complete back view on a styled commercial background |
| 3 | `03_side_view.png` | 45° profile / drape view |
| 4 | `04_craft_story.png` | ONE wide crafted-work/fabric story scene — **never close-up crops** |
| 5 | `05_lifestyle.png` | Aspirational real-world lifestyle scene |
| 6 | `06_styling_lookbook.png` | One premium styling scenario |
| 7 | `07_usp_infographic.png` | USP showcase (text only where the template allows) |
| 8 | `08_product_guide.png` | Size/fit/care guide — this is the one slot that may use a macro detail prompt |

## 5b. Prompt gallery (default ON — fully local, no NIM)

Panel bodies come from the compiled prompt library
`DOCUMENTATION/all_prompts_compilation.json` (~280 curated prompts) instead of the
fixed template text, for richer posing/scenes:

- **Local model selection**: picks persona from gallery's `FEMALE MODEL` / `MALE MODEL`
  variation prompts based on audience (Indian/South Asian for amazon.in)
- **Heuristic slot picking**: scores gallery scene prompts (MEN, WOMEN, GIRL, S-series)
  against slot rules — no external API calls
- **Local adapter**: swaps garment references → this product, injects selected model
  persona, normalizes 1600x2100→1600x1920, strips reference-lock clauses
  ("same person as reference", "background identical")
- **Sanitized**: clauses that pin "same person as the reference" or "background:
  identical" are rewritten/removed — the FRESH-CASTING rule (never copy the humans
  in the base images) and premium-background rules always win
- **Compliance wrapper unchanged**: product ground truth, reference rules, identity
  lock and the locked 3:4 output spec wrap every gallery body
- **Guardrails**: SYSTEM TASK CODE (utility scripts) excluded; craft-story
  slot can never take a close-up prompt; at most ONE panel (`08_product_guide`)
  may be macro; `01_hero_white` falls back to AIIE pure-white template
- **Fail-safe**: any failure returns that slot to its classic AIIE body —
  a run is never blocked by the gallery
- **Plans cached** per ASIN in `data/nim/<ASIN>.gallery.json`

Disable or re-balance in `config.yaml → gallery:` (`enabled: false` restores the
pure AIIE template everywhere).

## 6. Google Sheets tracking

Default backend is CSV (`data/tracking.csv`) so it runs with zero setup. To use a Sheet:

1. Create a Google Cloud service account, enable the **Google Sheets API**, download the JSON key
   → save as `service-account.json` in the project root.
2. Create a sheet, share it with the service-account email (`...iam.gserviceaccount.com`) as **Editor**.
3. In `config.yaml`:

```yaml
sheet:
  backend: "gspread"
  spreadsheet_id: "1AbC...yourSheetId"
  worksheet_name: "ASIN Jobs"
```

Rows are upserted by ASIN (status, title, brand, base image count, `n/8` slots done,
folder path, error). Safe to re-run: rows update instead of duplicating.

## 7. How it survives the messy parts

- **Amazon blocks**: captcha/interstitial detection (`scrape.captcha_markers`) → raises,
  retries with exponential backoff + jitter, human-like pacing between ASINs.
  For volume, add residential proxies in `browser.proxy`.
- **Hi-res images**: thumbnails are rewritten to `_AC_SL2000_` → `_SL1500_` → `_SL1200_` →
  original ladder; each download is validated (content-type, min pixels, size) and
  deduplicated by SHA-256 so you never store the same photo twice.
- **Resumable**: `manifest.json` records each slot. Re-running skips finished slots
  (`--force` overrides). A failed slot doesn't kill the ASIN.
- **Gemini UI changes**: every selector lives in `config.yaml → gemini.selectors`.
  When Google ships a UI change and a selector stops matching, run
  `python run.py probe --interactive` (headed) and fix the selector from the dumped
  `logs/gemini/probe_*.json` (button/file-input inventory + DOM + screenshot) instead
  of guesswork. If `create_image_option` breaks, the code automatically falls back to
  clicking the `div.gem-menu-item-label` matching `gemini.image_model_hints`.
  Two download strategies (`dom_fetch` default, `button` fallback) because Google
  reworks that DOM regularly. A fresh chat is started explicitly via
  `selectors.new_chat_button` so a batch never lands on the previous chat.
- **Generated-image accuracy gate** (`gemini.image_check`): every captured image is
  verified before its slot counts as ok — decodable, portrait, aspect within
  tolerance of 3:4 (UI) or 1600×1920 (panel spec), longest side ≥ 1000 px (Amazon
  minimum), not an unchanged echo of an uploaded reference, not a duplicate of an
  earlier panel in the same chat. Rejections raise and go through the normal slot
  retry path (fresh chat + re-upload). The composer is also checked to have actually
  received the prompt text before sending, and uploads report the *verified* preview
  count (zero attachments = hard error, never a silent text-only send).
- **No key, no cost**: uses your own Gemini session. Trade-off: slower and
  UI-dependent — if you later get an API key, the pipeline is structured so
  `src/gemini_web.py` is the only file that has to change to a `generateContent` call.

## 8. Before you scale — read this

- Scraping Amazon is against their **Conditions of Use**; use conservative volumes,
  your own proxy/rate strategy, and check Amazon's image/listing policies before uploading.
- Google may flag abnormal automated usage of the Gemini web UI. Keep pacing humane
  (`gemini.between_slots_sec`), run modest batches, and prefer a real API key for
  production volume.
- **Always human-review slot 1** against Amazon's main-image policy, and check
  infographic text and dimension numbers — AI text can still hallucinate.
  Slot 1–2 are policy-critical; 3–8 are creative.
- Generated files are 1:1; Amazon wants ≥1600px on the longest side (we ask for 3000×3000).

## 9. Layout of the code

```
run.py                  CLI (login | scrape | generate | all | one | clean)
src/config.py           YAML config + ${ENV} expansion + .env
src/scraper.py          Playwright Amazon scraper, hi-res URL rewriting
src/downloader.py       base image download, validation, dedupe
src/prompts.py          slot loader + prompt builder (compliance baked in)
src/prompt_gallery.py   gallery sourcing: local model pick + heuristic adapt + cache
src/nim_client.py       NVIDIA NIM client (optional via nim.enabled + NIM_API_KEY; local heuristic fallback otherwise)
src/gemini_web.py       Gemini web driver: upload, prompt, wait, auto-download
src/pipeline.py         orchestration, manifest, resume, per-ASIN reports
src/wm_worker.py        watermark remover worker (near-match fallback included)
src/wm_clean.py         clean/sweep wrappers for generated images
src/tracker.py          CSV / Google Sheets upsert
prompts/aiie_studio.yaml  AIIE 8P master + 8 slot templates (fallback bodies)
prompts/slots.yaml        legacy generic pack
tests/test_offline.py   no-network test: parsing, prompts, gallery, manifest, tracking
```

## 10. Testing

Offline check (no network, no browser needed):

```bash
python tests/test_offline.py
```

## 11. Next steps available

- Swap the Gemini web driver for the official API (`gemini-2.5-flash-image`) for speed/reliability
- Post-process generated images: verify white-background compliance, resize to 2000×2000,
  auto-reject text on slot 1
- Add a comparison-chart slot or a variant-swap loop
- Optional local dashboard (Flask) to review bundles before upload