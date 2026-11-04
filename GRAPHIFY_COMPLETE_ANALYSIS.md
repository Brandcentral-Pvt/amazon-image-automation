# Complete Graphify Analysis - amazon-image-automation Project

**Project**: amazon-image-automation  
**Analysis Date**: 2026-11-04  
**Analysis Type**: Code-only AST extraction (no LLM required)  
**Graphify Version**: 0.9.102

## Extraction Summary

- **Code files analyzed**: 116
- **Total nodes**: 1,327
- **Total edges**: 2,594
- **Communities detected**: 96 (82 shown, 14 thin omitted)
- **Extraction quality**: 94% EXTRACTED, 6% INFERRED, 0% AMBIGUOUS
- **Token cost**: 0 input · 0 output (pure AST extraction, no API calls)

## God Nodes (Most Connected - Core Abstractions)

| Rank | Node | Edges |
|------|------|-------|
| 1 | `Config` | 82 |
| 2 | `cn()` | 51 |
| 3 | `GeminiWeb` | 46 |
| 4 | `ProductData` | 40 |
| 5 | `Pipeline` | 30 |
| 6 | `react` | 26 |
| 7 | `gemini` | 26 |
| 8 | `gemini` | 26 |
| 9 | `clean_generated_image()` | 25 |
| 10 | `main()` | 25 |

**Interpretation**: `Config` is the central hub connecting nearly all components of the system. The `cn()` function and `GeminiWeb` are the next most critical connectors, highlighting the importance of Claude Code naming conventions and the Gemini AI integration.

## Surprising Connections (Inferred Relationships)

The graph discovered 161 inferred edges (avg confidence: 0.89):

1. **`make_gem()` → `GeminiWeb`** [INFERRED]
   - `tests/test_gemini_health.py` → `src/gemini_web.py`

2. **`write_manifest()` → `Config`** [INFERRED]
   - `tests/test_bot_commands.py` → `src/config.py`

3. **`main()` → `ConfigError`** [INFERRED]
   - `bot.py` → `src/config.py`

4. **`main()` → `ProductData`** [INFERRED]
   - `tests/test_offline.py` → `src/models.py`

5. **`make_cfg()` → `Config`** [EXTRACTED]
   - `tests/test_bot_commands.py` → `src/config.py`

## Community Structure (Key Communities)

### Core Functional Communities

| Community | Name | Nodes | Cohesion | Focus |
|-----------|------|-------|----------|-------|
| 0 | `cn` | 91 | 0.05 | Claude Code naming utility functions |
| 17 | `slots` | 19 | 0.10 | Image generation slot management |
| 18 | `Config` | 9 | 0.19 | Configuration system |
| 24 | `tracker.py` | 4 | 0.24 | CSV/Google Sheets job tracking |
| 58-71 | Image outputs | 3-6 nodes each | 0.33 | Generated images (01_hero_white through 07_usp_infographic) |
| 72 | `download_base_images` | 3 | 0.47 | Base image downloading logic |
| 73-76 | `image_spec` / `studio` | 5 nodes each | 0.40 | Image specifications and AIIE studio prompts |

### Infrastructure Communities

- **Community 1**: `.get` / `GeminiError` / `ensure_dir()` - 3 nodes
- **Community 4**: `types/index.ts` - 28 nodes (TypeScript types for API)
- **Community 5**: `Pipeline` - 14 nodes (orchestration: scrape → generate → clean)
- **Community 6**: `api_server.py` - 29 nodes (FastAPI/Starlette server)
- **Community 21**: `dependencies` - 17 nodes (package.json deps)
- **Community 22**: `devDependencies` - 17 nodes (dev deps)
- **Community 26**: `package.json` - 10 nodes
- **Community 36**: `amazon` - 9 nodes (Amazon scraper config)
- **Community 37**: `browser` - 9 nodes (Playwright browser config)
- **Community 38-39**: `amazon` / `browser` (duplicate communities)

### Weakly Interconnected (Low Cohesion)

- **Community 0 "cn"**: Cohesion 0.05 - nodes are weakly interconnected, suggesting this utility module could be split
- **Community 1 ".get"**: Cohesion 0.06 - small group of Gemini-related utilities
- **Community 10 "gemini"**: Cohesion 0.06 - another Gemini-related community

## Knowledge Gaps

- **1 isolated node**: `next` - has ≤1 connection, possible missing edges
- **14 thin communities** (<3 nodes) omitted from report - can be explored with `graphify query`

## Suggested Questions (Graph Is Uniquely Positioned to Answer)

1. **Why does `Config` connect `Config` to `.get`, `browser.py`, `Pipeline`, `utils.py`, `download_base_images`, `prompt_gallery.py`, `prompts.py`, `clean_generated_image`, `json`, `test_bot_commands.py`, `test_gemini_health.py`, `tracker.py`, `scrape_asin`?**
   - High betweenness centrality (0.031) - this node is a cross-community bridge

2. **Are the 39 inferred relationships involving `Config` actually correct?**
   - `Config` has 39 INFERRED edges - model-reasoned connections that need verification

3. **What connects `next` to the rest of the system?**
   - 1 weakly-connected node found - possible missing edges

4. **Should `cn` be split into smaller, more focused modules?**
   - Cohesion score 0.0517 - nodes in this community are weakly interconnected

5. **Why does `GeminiWeb` connect `.get` to `utils.py`, `Config`, `Pipeline`, `test_gemini_health.py`?**
   - High betweenness centrality (0.025) - this node is a cross-community bridge

6. **Are the 3 inferred relationships involving `GeminiWeb` actually correct?**
   - `GeminiWeb` has 3 INFERRED edges - model-reasoned connections that need verification

7. **Should `.get` be split into smaller, more focused modules?**
   - Cohesion score 0.0587 - nodes in this community are weakly interconnected

## Key Findings

### 1. **Configuration is the Central Hub**
The `Config` class is the most connected node (82 edges), serving as the primary integration point between all major subsystems: scraping, browser management, Gemini AI, prompt generation, watermark cleaning, and tracking.

### 2. **Two Distinct Codebases Merged**
The graph reflects both:
- **Python backend** (`src/` directory): scraper, pipeline, models, config, utils, browser, downloader
- **Frontend/TypeScript** (`frontend/` directory): React components, Tailwind config, TypeScript config, ESLint/Prettier setup

Cross-community edges between `types/index.ts`, `package.json`, and `dependencies` show integration points.

### 3. **Gemini AI is the Primary Integration Point**
`GeminiWeb` (46 edges) and related `gemini` nodes serve as major bridges between the Python pipeline and the AI image generation process. The graph reveals the full flow: prompt building → batch management → image generation → watermark cleanup.

### 4. **Slot-Based Image Generation Pattern**
Communities 17, 27, 35, 66, etc. all center around "slots" - the 8-slot panel system (AIIE PANEL N/8) for generating the 8 different product images. The graph captures the slot lifecycle: pending → generation → watermark → status tracking.

### 5. **Watermark Processing is a Distinct Concern**
Multiple communities (2, 44, 45, 53, 54, 58-64, 72) are dedicated to watermark detection/removal/sweeping, indicating this is a significant operational concern in the pipeline.

### 6. **Testing Infrastructure is Well-Integrated**
Test files (`test_bot_commands.py`, `test_gemini_health.py`, `test_offline.py`, `test_config.py`, `test_pipeline.py`, `test_scraper.py`, `test_watermark.py`) are deeply interconnected with the production code they test, suggesting strong test-driven development.

### 7. **No Import Cycles Detected**
The graph analysis found no import cycles, indicating good modular design boundaries between components.

## Output Files Generated

```
graphify-out/
├── graph.json              # 1327 nodes, 2594 edges, full graph data
├── graph.html              # Interactive D3.js graph visualization
├── GRAPH_REPORT.md         # This comprehensive analysis report
├── .graphify_analysis.json # Internal analysis state
├── .graphify_root          # Scan root path reference
├── manifest.json           # Extraction manifest
└── cache/                  # Cached extraction results
    ├── ast/                # AST extraction cache (116 code files)
    └── semantic/           # Semantic extraction (skipped - no LLM backend)
```

## Recommendations

1. **Investigate `Config` centrality**: Consider whether `Config` should be further decomposed or if its broad connectivity is intentional (configuration-as-center pattern).

2. **Address `cn` community cohesion**: The very low cohesion (0.05) suggests `cn` utility functions could be split into more focused modules (e.g., `date_utils`, `string_utils`, `asin_utils`).

3. **Verify inferred edges**: The 161 inferred edges, while having high average confidence (0.89), should be manually verified - particularly the `Config` connections (39 inferred edges) and `GeminiWeb` connections (3 inferred edges).

4. **Explore the `next` isolated node**: This node has weak connections - check if `next` (likely Next.js related) should have edges to `types/index.ts`, `package.json`, or other modules.

5. **Run `graphify query`**: Use the interactive query capability to explore specific relationships, e.g., `graphify query "How does Config affect Pipeline?"` or `graphify path "Config" "GeminiWeb"`.

6. **Enable semantic extraction**: To add LLM-based semantic relationships (function descriptions, docstring links, etc.), set `OPENAI_API_KEY` or `GEMINI_API_KEY` and re-run `graphify extract .` (will re-infer edges and community names).

## How to Explore Further

```bash
# Shortest path between two nodes
graphify path "Config" "GeminiWeb"

# Explain a node and its neighbors
graphify explain "Config"

# BFS traversal for a question
graphify query "What is the data flow from scraping to image generation?"

# God nodes analysis
graphify god-nodes --top 20

# Community analysis
graphify cluster-only  # Regenerate report with community names
```