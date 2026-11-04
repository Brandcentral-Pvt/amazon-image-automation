"use client";

import { MainLayout } from "@/components/layout";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card";
import { Tabs, TabPanel } from "@/components/ui/Tabs";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Search, ChevronRight, ExternalLink, Copy, CheckCircle, AlertCircle, Info, FileText, Zap, Shield, Settings, Database, Image, Bell, HelpCircle, ArrowRight, Code, Terminal, Github, Twitter, Mail, Discord } from "lucide-react";

const docs = {
  gettingStarted: `
# Getting Started

Welcome to Amazon Image Automation! This guide will help you set up and run your first image generation pipeline.

## Prerequisites

- Python 3.10+
- Node.js 18+ (for the dashboard)
- Google Chrome installed
- A Google account for Gemini access
- Amazon ASINs to process

## Installation

### Backend (Python)

\`\`\`bash
cd amazon-image-automation
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
python -m playwright install chromium
\`\`\`

### Frontend (Dashboard)

\`\`\`bash
cd frontend
npm install
npm run dev
\`\`\`

## Configuration

Copy the example config and customize:

\`\`\`bash
cp config.example.yaml config.yaml
\`\`\`

Edit \`config.yaml\` with your settings:
- Chrome profile name
- Watermark engine path
- Output directory
- Gemini settings

## First Run

1. **Login to Gemini**: Run \`python run.py login --headed\` and sign in to Google
2. **Test with sample ASINs**: \`python run.py generate --asins data/asins.sample.txt --dry-run\`
3. **Run full pipeline**: \`python run.py all --asins data/asins.txt\`

## Directory Structure

\`\`\`
amazon-image-automation/
├── src/                 # Backend source code
├── frontend/            # Next.js dashboard
├── prompts/             # AIIE prompt templates
├── config.yaml          # Main configuration
├── run.py               # CLI entry point
├── data/                # ASIN lists, tracking, NIM cache
├── output/              # Generated images per ASIN
└── logs/                # Logs and diagnostics
\`\`\`
  `,
  cliReference: `
# CLI Reference

\`\`\`bash
python run.py [COMMAND] [OPTIONS]
\`\`\`

## Commands

### login
One-time Google login to establish persistent session.

\`\`\`bash
python run.py login [--headed] [--gemini]
\`\`\`

Options:
- \`--headed\`: Show browser window (required for first login)
- \`--gemini\`: Log into Gemini profile instead of shared scraper profile

### scrape
Scrape Amazon product data and download base images.

\`\`\`bash
python run.py scrape --asins FILE|ASIN [--limit N] [--force]
\`\`\`

Options:
- \`--asins\`: Path to ASIN list file or comma-separated ASINs
- \`--limit N\`: Process only first N ASINs
- \`--force\`: Re-scrape even if product.json exists

### generate
Generate images from scraped data using Gemini.

\`\`\`bash
python run.py generate --asins FILE|ASIN [--dry-run] [--force] [--notes "..."]
\`\`\

Options:
- \`--dry-run\`: Generate prompts only, no Gemini calls
- \`--force\`: Regenerate slots already marked complete
- \`--notes\`: Additional instructions appended to every prompt

### clean
Run watermark removal on already-generated images.

\`\`\`bash
python run.py clean --asins FILE|ASIN
\`\`\

### all
Run full pipeline: scrape → generate → clean.

\`\`\`bash
python run.py all --asins FILE|ASIN
\`\`\

### one
Single ASIN full pipeline with browser visible.

\`\`\`bash
python run.py one --asin B0XXXXXXXX --headed
\`\`\

## Global Options

- \`--config FILE\`: Use custom config file (default: config.yaml)
- \`--dry-run\`: Generate prompts only (generate command)
- \`--headed\`: Show browser window
- \`--force\`: Overwrite existing results
- \`--limit N\`: Limit number of ASINs processed
- \`--notes TEXT\`: Additional prompt instructions
  `,
  architecture: `
# Architecture Overview

## System Components

\`\`\`
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Amazon        │     │   Prompt        │     │   Gemini Web    │
│   Scraper       │────▶│   Builder       │────▶│   Automation    │
│   (Playwright)  │     │   (AIIE +       │     │   (Playwright)  │
│                 │     │   Gallery)      │     │                 │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                                                         ▼
                                              ┌─────────────────┐
                                              │  Watermark      │
                                              │  Removal        │
                                              │  (LaMa ONNX)    │
                                              └────────┬────────┘
                                                       │
                                                       ▼
                                              ┌─────────────────┐
                                              │  Output &       │
                                              │  Tracking       │
                                              │  (CSV/Sheets)   │
                                              └─────────────────┘
\`\`\`

## Core Modules

### src/scraper.py
Playwright-based Amazon scraper with:
- Hi-res image URL rewriting (\`_AC_SL2000_\` → \`_SL1500_\`)
- CAPTCHA detection and retry logic
- Product data extraction (title, price, bullets, attributes, A+ content)
- Image deduplication by SHA-256

### src/prompts.py + src/prompt_gallery.py
Prompt generation system:
- **AIIE Studio Pack** (\`prompts/aiie_studio.yaml\`): 8-slot Amazon-compliant templates
- **Gallery Integration** (\`src/prompt_gallery.py\`): 280 curated prompts with local model selection, heuristic slot picking, and automatic sanitization
- **Compliance Wrapper**: Product truth, FRESH CASTING, 3:4/1600×1920 lock

### src/gemini_web.py
Playwright Gemini web automation:
- Persistent Chrome profile (your "Chirag" profile)
- Chat-based batch sessions (one chat per ASIN)
- Strict sequence: upload refs → select "Create image" → set 3:4 → generate
- Lightbox dismissal after each generation
- Download routing to \`output/<ASIN>/generated/\`

### src/wm_worker.py + src/wm_clean.py
Watermark removal pipeline:
- LaMa ONNX inpainting (local, no API keys)
- Sparkle template matcher (IoU ≥ 0.70)
- Near-match fallback (probe 0.55-0.70 → preset box → evidence refinement)
- Residual QA: re-detect → re-fill (pad 14) → ghost detection (>3 grey levels)
- Provenance: original saved to \`generated/_with_watermark/\`

### src/pipeline.py
Orchestration layer:
- Per-ASIN manifest (\`manifest.json\`) for resumability
- Slot retry logic (fresh chat + re-seeded master)
- Final watermark sweep pass
- CSV/Google Sheets tracking

### src/tracker.py
Tracking backends:
- CSV (\`data/tracking.csv\`) - zero setup
- Google Sheets (gspread) - optional

## Data Flow

1. **Input**: ASIN list (file or CLI)
2. **Scrape**: \`product.json\` + \`base_images/\` per ASIN
3. **Prompts**: \`prompts/prompts.json\` + \`prompts.md\` per ASIN
3. **Generate**: Gemini chat → 8 images → \`generated/\`
4. **Watermark**: Clean each image in-place, provenance copy
5. **Manifest**: \`manifest.json\` updated per slot
6. **Tracking**: Row upserted in \`tracking.csv\`
7. **Report**: \`README.md\` per ASIN for operator review

## Key Design Decisions

- **No paid APIs**: Uses your Chrome session for Gemini
- **Resumable**: Manifest tracks every slot; re-runs skip completed
- **Compliance baked in**: White background, no text, product fidelity, 3:4 aspect
- **Local watermark**: No cloud API; runs in remover's own venv
- **Config-driven selectors**: Update \`config.yaml\` when Google changes UI
- **Local gallery**: 280 prompts, no NIM API needed
  `,
  faq: `
# Frequently Asked Questions

## General

### Does this require API keys?
No! The system uses your existing Chrome session for both Amazon scraping and Gemini web UI. No API keys required.

### Is this compliant with Amazon/Google ToS?
- **Amazon**: Scraping is against Amazon's Conditions of Use. Use conservative volumes, your own proxies, and review policies before uploading generated images.
- **Google**: Automated Gemini web UI usage may be flagged. Keep pacing humane, run modest batches.

### What image specifications does it produce?
- **Aspect ratio**: 3:4 (portrait)
- **Dimensions**: 1600×1920 pixels
- **Format**: PNG
- **Background**: Pure white for slot 1, styled commercial for others
- **No text/watermarks**: Amazon main-image policy compliant

## Setup Issues

### "Chrome profile already in use" error
Close all Chrome windows using the "Chirag" profile, or set \`recopy_chrome_profile: true\` in config to force a fresh copy.

### "Could not find Generate button" on images page
Run \`python run.py probe --images --headed\` to inspect the DOM and update \`gemini.selectors\` in config.yaml with current selectors.

### Watermark remover "model not found"
Ensure \`G:\\veo-watermark-remover\\veo-watermark-remover\\local_app\\models\\lama_fp32.onnx\` exists. The model is ~198 MB.

### "CUDA out of memory" or slow CPU inference
Set \`watermark.device: cpu\` in config.yaml, or reduce \`watermark.threads\`.

## Generation Issues

### Gemini returns text instead of images
- Ensure \`gemini.ensure_image_model: true\` in config
- Run \`python run.py probe --interactive\` and manually select "Create image" model
- Check \`gemini.image_model_hints\` matches your UI model names

### Generation quota exceeded
Gemini web UI has daily limits. Wait for reset or slow down with \`gemini.between_slots_sec: [30, 60]\`.

### Generated image doesn't match product
- Base images are the single source of truth
- Check \`product.json\` attributes match the actual product
- Gallery prompts are sanitized but may need manual review for unusual products

### Watermark not removed
- Check \`logs/wm/\` for diagnostics
- Run \`python run.py clean --asins ASIN\` to retry
- Some faint marks need near-match fallback (probe 0.55-0.70)

### Lightbox blocks next generation
The dashboard includes \`_dismiss_lightbox()\` that tries close button, backdrop click, and Escape key. If it fails, update \`gemini.selectors.lightbox_close\` in config.

## Performance

### Speed up generation
- Reduce \`gemini.between_slots_sec\` (but risk quota blocks)
- Use \`--limit\` for testing
- Run multiple instances with different Chrome profiles

### Watermark removal is slow
- Use GPU: \`watermark.device: cuda\` (requires onnxruntime-gpu)
- Reduce \`watermark.timeout_sec\` if images are small
- Batch process with \`python run.py clean --asins data/asins.txt\`

## Output Structure

\`\`\`
output/
└── B0XXXXXXXX/
    ├── product.json          # Scraped product data
    ├── base_images/          # Downloaded hi-res images
    ├── prompts/
    │   ├── prompts.json      # All 8 prompts + master (machine readable)
    │   └── prompts.md        # Human-readable prompts
    ├── generated/
    │   ├── 01_hero_white.png
    │   ├── 02_back_view.png
    │   ├── 03_side_view.png
    │   ├── 04_craft_story.png
    │   ├── 05_lifestyle.png
    │   ├── 06_styling_lookbook.png
    │   ├── 07_usp_infographic.png
    │   └── 08_product_guide.png
    ├── generated/_with_watermark/  # Provenance copies
    ├── manifest.json         # Per-slot status, watermark results
    └── README.md             # Upload checklist for operator
\`\`\`

## Tracking CSV Columns

\`\`\`
asin, status, product_title, brand, base_images_found, slots_done, bundle_path, error, updated_at
\`\`\`

## Advanced Configuration

### Custom Prompt Templates
Edit \`prompts/aiie_studio.yaml\` for custom slot definitions. The compliance wrapper is applied automatically.

### Custom Gallery Prompts
Replace \`DOCUMENTATION/all_prompts_compilation.json\` with your own curated prompts (same structure).

### Custom Chrome Profile
Set \`gemini.chrome_profile_name\` in config.yaml. Profile must exist in Chrome.

### Proxy Support
Set \`browser.proxy\` in config.yaml: \`http://user:pass@host:port\`

### Google Sheets Tracking
1. Create service account, enable Sheets API
2. Share sheet with service account email as Editor
3. Set in config.yaml:
\`\`\`yaml
sheet:
  backend: "gspread"
  spreadsheet_id: "1AbC..."
  worksheet_name: "ASIN Jobs"
  credentials_file: "service-account.json"
\`\`\`

## Support

- **GitHub Issues**: Report bugs with diagnostics from \`python run.py probe --interactive\`
- **Documentation**: See \`README.md\` and \`DOCUMENTATION/\`
- **Logs**: Check \`logs/\` directory for detailed diagnostics
  `,
  troubleshooting: `
# Troubleshooting Guide

## Common Errors & Solutions

### 1. Browser/Playwright Issues

#### "BrowserType.launch_persistent_context: Opening in existing browser session"
**Cause**: Chrome profile already open in another window.
**Fix**: Close all Chrome windows using the profile, or set \`recopy_chrome_profile: true\`.

#### "Timeout 30000ms exceeded" waiting for element
**Cause**: Page load timeout or selector changed.
**Fix**: 
- Increase \`gemini.generation_timeout_sec\`
- Run \`python run.py probe --interactive\` to get current selectors
- Update \`gemini.selectors\` in config.yaml

#### "Target page, context or browser has been closed"
**Cause**: Browser crashed or quota exceeded.
**Fix**: Check Gemini quota; reduce batch size; increase \`gemini.between_slots_sec\`.

### 2. Gemini Generation Issues

#### "Gemini replied without an image"
**Cause**: Text-only model selected or quota exceeded.
**Fix**:
- Set \`gemini.ensure_image_model: true\`
- Run \`python run.py probe --interactive\` and select "Create image"
- Verify \`gemini.image_model_hints\` matches your UI

#### "I can create more images as soon as your limit resets"
**Cause**: Daily Gemini quota exceeded.
**Fix**: Wait for reset (usually midnight PST) or slow down batching.

#### Generated image is wrong product/person
**Cause**: Prompt leakage or gallery prompt mismatch.
**Fix**:
- Check \`product.json\` matches actual product
- Gallery prompts are sanitized but review \`prompts.md\`
- Ensure \`FRESH CASTING\` lock is in prompts

### 3. Watermark Removal Issues

#### "wm: model not found"
**Cause**: LaMa model file missing.
**Fix**: Verify \`G:\\veo-watermark-remover\\...\\models\\lama_fp32.onnx\` exists (198 MB).

#### "wm: cleaner timed out"
**Cause**: Large image or CPU-only inference too slow.
**Fix**:
- Set \`watermark.device: cuda\` (requires onnxruntime-gpu)
- Increase \`watermark.timeout_sec\`
- Reduce \`watermark.threads\` if OOM

#### "wm: no sparkle found" but mark visible
**Cause**: Mark too faint for IoU ≥ 0.70 gate.
**Fix**: Near-match fallback should catch (probe 0.55-0.70). Check \`logs/wm/\` for \`near-match\` status.

#### "wm: possible ghost" warning
**Cause**: Residual mark-like pattern >3 grey levels after inpainting.
**Fix**: Usually harmless (texture similarity). Check output visually.

#### "wm: mark still visible after fill"
**Cause**: Mark re-detected at full gate after inpainting.
**Fix**: Auto re-fill with wider mask (pad 14) runs automatically. Check \`passes\` in output.

### 4. Scraping Issues

#### "Captcha detected"
**Cause**: Amazon served captcha page.
**Fix**: 
- Wait and retry (exponential backoff configured)
- Add residential proxies in \`browser.proxy\`
- Reduce \`amazon.delay_between_asins\`

#### "No base images found"
**Cause**: Hi-res URL ladder failed or images blocked.
**Fix**: Check \`product.json\` image URLs; verify \`scraper.min_image_px\`.

#### "Product data incomplete"
**Cause**: A+ content or variant selectors changed.
**Fix**: Run \`python run.py probe --interactive\` on product page.

### 5. Pipeline/Orchestration Issues

#### "Slot X attempt Y failed: ... retrying"
**Cause**: Transient Gemini error or timeout.
**Fix**: Automatic retry with fresh chat (up to \`gemini.slot_retries\` times).

#### "Manifest.json corrupted"
**Cause**: Disk full or process killed during write.
**Fix**: Delete \`output/<ASIN>/manifest.json\` and re-run.

#### "Tracking CSV permission denied"
**Cause**: File locked by another process (Excel open?).
**Fix**: Close Excel; ensure \`data/tracking.csv\` writable.

### 6. Diagnostic Commands

\`\`\`bash
# Interactive DOM inspection (chat page)
python run.py probe --interactive

# Interactive DOM inspection (images page)
python run.py probe --images --interactive

# Test watermark on single image
python run.py clean --asin B0XXXXXXXX

# Dry run prompt generation
python run.py generate --asin B0XXXXXXXX --dry-run

# Full pipeline with browser visible
python run.py one --asin B0XXXXXXXX --headed

# Check logs
ls logs/
cat logs/run.log
cat logs/gemini/*.json
\`\`\`

## Log Locations

- \`logs/run.log\`: Main pipeline log
- \`logs/gemini/*.json\`: Gemini DOM dumps from probe
- \`logs/wm/*.json\`: Watermark worker output
- \`output/<ASIN>/manifest.json\`: Per-slot status
- \`data/tracking.csv\`: Overall tracking

## Getting Help

When reporting issues, include:
1. Command that failed
2. Relevant log excerpt (\`logs/run.log\`)
3. Config (sanitized) from \`config.yaml\`
4. Probe JSON from \`logs/gemini/\` if UI-related
5. OS/Python/Node versions
  `,
};

export default function HelpPage() {
  const [activeTab, setActiveTab] = useState("gettingStarted");
  const [searchQuery, setSearchQuery] = useState("");

  const tabs = [
    { key: "gettingStarted", label: "Getting Started", icon: <Play className="w-4 h-4" /> },
    { key: "cliReference", label: "CLI Reference", icon: <Terminal className="w-4 h-4" /> },
    { key: "architecture", label: "Architecture", icon: <Settings className="w-4 h-4" /> },
    { key: "faq", label: "FAQ", icon: <HelpCircle className="w-4 h-4" /> },
    { key: "troubleshooting", label: "Troubleshooting", icon: <AlertCircle className="w-4 h-4" /> },
  ];

  const filteredContent = (content: string) => {
    if (!searchQuery) return content;
    const lines = content.split("\n");
    const filtered = lines.filter(line => 
      line.toLowerCase().includes(searchQuery.toLowerCase())
    );
    return filtered.length > 0 ? filtered.join("\n") : "No matches found.";
  };

  return (
    <MainLayout title="Documentation" subtitle="Complete guide to Amazon Image Automation">
      <div className="space-y-6">
        {/* Search */}
        <Card className="mb-6">
          <CardContent className="p-4">
            <div className="relative max-w-xl">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-surface-400" />
              <Input
                placeholder="Search documentation..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>
          </CardContent>
        </Card>

        {/* Tabs */}
        <Tabs tabs={tabs} onChange={setActiveTab} className="mb-6">
          {tabs.map(tab => (
            <TabPanel key={tab.key} active={activeTab === tab.key}>
              <div className="prose prose-surface max-w-none">
                {filteredContent(docs[activeTab as keyof typeof docs] || "").split("\n").map((line, i) => {
                  if (line.startsWith("# ")) return <h1 key={i} className="heading-xl mt-8 mb-4">{line.slice(2)}</h1>;
                  if (line.startsWith("## ")) return <h2 key={i} className="heading-lg mt-6 mb-3">{line.slice(3)}</h2>;
                  if (line.startsWith("### ")) return <h3 key={i} className="heading-md mt-4 mb-2">{line.slice(4)}</h3>;
                  if (line.startsWith("#### ")) return <h4 key={i} className="heading-sm mt-3 mb-2">{line.slice(5)}</h4>;
                  if (line.startsWith("```")) return <div key={i} className="bg-surface-900 text-surface-50 p-4 rounded-lg font-mono text-body-sm overflow-x-auto whitespace-pre-wrap">{line.slice(3)}</div>;
                  if (line.startsWith("`") && line.endsWith("`")) return <code key={i} className="bg-surface-100 px-1.5 py-0.5 rounded text-body-sm font-mono">{line.slice(1, -1)}</code>;
                  if (line.startsWith("- ")) return <li key={i} className="ml-4 mb-1">{line.slice(2)}</li>;
                  if (line.startsWith("* ")) return <li key={i} className="ml-4 mb-1">{line.slice(2)}</li>;
                  if (line.match(/^\d+\. /)) return <li key={i} className="ml-4 mb-1">{line}</li>;
                  if (line.trim() === "") return <br key={i} />;
                  return <p key={i} className="text-surface-600 mb-2">{line}</p>;
                })}
              </div>
            </TabPanel>
          ))}
        </Tabs>

        {/* Footer Links */}
        <Card className="mt-8">
          <CardContent className="pt-6">
            <h3 className="heading-sm font-semibold mb-4">Resources</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <a href="https://github.com/Brandcentral-Pvt/amazon-image-automation" target="_blank" rel="noopener noreferrer" className="flex items-center gap-3 p-4 bg-surface-50 rounded-lg hover:bg-surface-100 transition-colors">
                <Github className="w-6 h-6 text-surface-500" />
                <div>
                  <p className="font-medium text-surface-900">GitHub Repository</p>
                  <p className="text-body-sm text-surface-500">Source code, issues, releases</p>
                </div>
              </a>
              <a href="#" className="flex items-center gap-3 p-4 bg-surface-50 rounded-lg hover:bg-surface-100 transition-colors">
                <FileText className="w-6 h-6 text-surface-500" />
                <div>
                  <p className="font-medium text-surface-900">API Documentation</p>
                  <p className="text-body-sm text-surface-500">REST API reference (coming soon)</p>
                </div>
              </a>
              <a href="#" className="flex items-center gap-3 p-4 bg-surface-50 rounded-lg hover:bg-surface-100 transition-colors">
                <Discord className="w-6 h-6 text-surface-500" />
                <div>
                  <p className="font-medium text-surface-900">Community Discord</p>
                  <p className="text-body-sm text-surface-500">Chat with other users</p>
                </div>
              </a>
              <a href="mailto:support@brandcentral.example.com" className="flex items-center gap-3 p-4 bg-surface-50 rounded-lg hover:bg-surface-100 transition-colors">
                <Mail className="w-6 h-6 text-surface-500" />
                <div>
                  <p className="font-medium text-surface-900">Email Support</p>
                  <p className="text-body-sm text-surface-500">support@brandcentral.example.com</p>
                </div>
              </a>
            </div>
          </CardContent>
        </Card>
      </div>
    </MainLayout>
  );
}

import { useState } from "react";
import { Minus, TrendingUp, TrendingDown } from "lucide-react";