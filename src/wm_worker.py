"""Watermark-remover worker - runs INSIDE the wm remover's own venv.

Called by `src/wm_clean.py` as a subprocess:

    <remover venv python> src/wm_worker.py <image> <engine_dir> <model> <orig_dir> <device> <threads>

It imports `wm_core` from the engine dir (cv2/onnxruntime live there), detects
the Gemini 4-point sparkle, inpaints it and OVERWRITES the image in place.
The result is printed as ONE JSON line on stdout (parsed by the caller).

Residual QA (mirrors the engine's own smoke-test tolerance of <4 grey levels):
  * the primary detector gate (IoU >= 0.70) re-checks the output; if the mark
    re-detects, the fill is retried once with a wider mask (pad 14).
  * the engine's faint-family verifier can misfire on featureless backgrounds
    (a smooth fill bounce of 1-2 grey levels still template-matches), so a
    "ghost" is only reported when the residual window is genuinely visible
    (> 3 grey levels above its surroundings).

Exit codes: 0 ok (removed or no-mark), 2 error.

NEAR-MATCH FALLBACK: when the sparkle is too faint/degraded for the shape gate
(probe 0.55-0.70 - the GUI's own "use the fallback box" range), a deterministic
bottom-right preset box is shrunk to the *pale-overlay evidence* inside it and
only that evidence mask is inpainted. If the evidence is implausible (none, or
the whole box lit up) the image is left untouched, so a clean photo can never be
damaged by the fallback.
"""
import json
import os
import shutil
import sys
import tempfile
import time

NEAR_GATE = 0.55    # GUI guidance: 0.55-0.70 => mark present but degraded


def main(argv: list[str]) -> int:
    if len(argv) < 7:
        print(json.dumps({"status": "error", "detail": "worker: wrong arguments"}))
        return 2
    image_path, engine_dir, model_path = argv[1], argv[2], argv[3]
    orig_dir, device, threads = argv[4], argv[5], int(argv[6])
    t0 = time.time()

    sys.path.insert(0, engine_dir)
    try:
        import cv2            # noqa: E402  (comes from the remover venv)
        import numpy as np    # noqa: E402
        import wm_core as wc  # noqa: E402
        import onnxruntime    # noqa: F401,E402
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"status": "error", "detail": f"engine import failed: {exc}"}))
        return 2

    img = wc.imread_color(image_path)
    if img is None:
        print(json.dumps({"status": "error", "detail": "could not read image"}))
        return 2

    mask, method = wc.detect_for_image(img, mode="sparkle", allow_preset=False, verbose=False)
    near_match = ""
    if mask is None:
        probe = wc.sparkle_probe(img)
        if probe >= NEAR_GATE:
            mask, near_match = _near_match_mask(wc, img)
            if mask is not None:
                method = f"near-match preset ({near_match})"
        if mask is None:
            if probe >= NEAR_GATE:
                detail = (f"near-match sparkle (probe {probe:.2f}) but no plausible pale "
                          "evidence in the fallback box - image left untouched")
            else:
                detail = "no sparkle found - image left untouched"
            print(json.dumps({
                "status": "no-mark",
                "probe": float(round(probe, 3)),
                "detail": detail,
            }))
            return 0

    # onnx provider selection (mirrors the GUI app's load_inpainter)
    try:
        import onnxruntime as ort  # noqa: PLC0415
        providers = _providers(device, ort.get_available_providers())
        inp = wc.Inpainter(model_path, providers=providers, threads=threads, verbose=False)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"status": "error", "detail": f"model load failed: {exc}"}))
        return 2

    res = wc.adaptive_fill(img, mask, inp, verbose=False)

    # ---- residual QA -------------------------------------------------------
    # Pass 1 fill, then re-detect on the OUTPUT at the engine's normal gate.
    v = wc.verify_sparkle_removal(img, res, verbose=False)
    p_after = float(wc.sparkle_probe(res))
    passes = 1
    if p_after >= 0.70:
        # the mark still re-detects at full gate: fill again with a wider mask
        wider = wc.detect_sparkle_mask(res, pad=14, verbose=False)
        if wider is not None:
            res = wc.adaptive_fill(res, wider, inp, verbose=False)
            v = wc.verify_sparkle_removal(img, res, verbose=False)
            p_after = float(wc.sparkle_probe(res))
            passes = 2

    verdict = "clean - sparkle removed (no star-shaped mark left)"
    ghost = False
    if v.get("found_after") and p_after >= 0.70:
        ghost = True
        verdict = "mark still visible after fill - inspect the output"
    elif v.get("found_after"):
        bounce = _ghost_bounce(wc, cv2, np, res)
        if bounce is not None and bounce > 3.0:
            ghost = True
            verdict = f"possible faint ghost ({bounce:.1f} grey levels) - inspect the output"

    # write to a temp file first, then swap in - the slot file is never half-written
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=os.path.splitext(image_path)[1].lower() or ".png",
                                        dir=os.path.dirname(image_path))
    os.close(tmp_fd)
    ext = os.path.splitext(image_path)[1].lower()
    params = [cv2.IMWRITE_JPEG_QUALITY, 97] if ext in (".jpg", ".jpeg") else []
    cv2.imwrite(tmp_path, res, params)

    # provenance: keep the pre-clean pixels next to the slot (only when a mark
    # is actually being removed - untouched images are never copied here)
    try:
        os.makedirs(orig_dir, exist_ok=True)
        shutil.copy2(image_path, os.path.join(orig_dir, os.path.basename(image_path)))
    except OSError:
        pass

    os.replace(tmp_path, image_path)

    out = {
        "status": "removed",
        "method": method,
        "near_match": bool(near_match),
        "mask_px": int((np.asarray(mask) > 0).sum()),
        "passes": passes,
        "probe_before": float(round(wc.sparkle_probe(img), 3)),
        "probe_after": float(round(p_after, 3)),
        "ghost": ghost,
        "verdict": verdict,
        "engine_verdict": str(v.get("verdict", "")),
        "iou_after": v.get("iou_after"),
        "seconds": round(time.time() - t0, 2),
    }
    print(json.dumps(out))
    return 0


def _near_match_mask(wc, img):
    """GUI's own fallback for degraded real marks (probe in the near-match band).

    A deterministic bottom-right corner preset box, shrunk by the engine to the
    pale-overlay evidence inside it. The mask can only SHRINK from the box, never
    relocate; we refuse to inpaint unless the evidence-based refinement produced
    a plausible small mask (never the full box), so clean corners stay intact.
    Returns (mask | None, refinement-note).
    """
    try:
        box = wc.preset_mask(img, "gemini_sparkle", refine=False, verbose=False)
        if box is None or int((box > 0).sum()) == 0:
            return None, ""
        refined, how = wc.refine_mask_to_evidence(img, box, pad=6, verbose=False)
        if "kept the full box" in str(how):      # implausible evidence -> refuse
            return None, str(how)
        if int((refined > 0).sum()) < 20:
            return None, str(how)
        return refined, str(how)
    except Exception:  # noqa: BLE001 - QA fallback must never break the run
        return None, ""


def _ghost_bounce(wc, cv2, np, res) -> "float | None":
    """Peak-to-ring grey-level contrast of the residual window (engine semantics)."""
    try:
        hits = wc.detect_sparkle_all(res, verbose=False)
    except Exception:  # noqa: BLE001 - QA helper must never break the run
        return None
    if not hits:
        return None
    hit = hits[0]
    x, y, s = int(hit["x"]), int(hit["y"]), int(hit["size"])
    h, w = res.shape[:2]
    s = max(8, min(s, w - x, h - y))
    gray = cv2.cvtColor(res, cv2.COLOR_BGR2GRAY).astype(np.float32)
    r = max(s // 2, 12)
    y0, y1 = max(y - r, 0), min(y + s + r, h)
    x0, x1 = max(x - r, 0), min(x + s + r, w)
    if y1 - y0 <= s or x1 - x0 <= s:
        return None
    patch = gray[y:y + s, x:x + s]
    ring = np.ones((y1 - y0, x1 - x0), bool)
    ring[y - y0:y - y0 + s, x - x0:x - x0 + s] = False
    if not ring.any():
        return None
    return float(np.percentile(patch, 90) - np.median(gray[y0:y1, x0:x1][ring]))


def _providers(device: str, avail: list[str]) -> list[str]:
    device = (device or "auto").lower()
    if device == "cpu":
        return ["CPUExecutionProvider"]
    if device == "cuda":
        if "CUDAExecutionProvider" not in avail:
            raise RuntimeError("CUDAExecutionProvider not available - install onnxruntime-gpu "
                               "or set watermark.device: cpu")
        return ["CUDAExecutionProvider", "CPUExecutionProvider"]
    return [p for p in ("CUDAExecutionProvider", "CPUExecutionProvider") if p in avail]


if __name__ == "__main__":
    code = 0
    try:
        code = main(sys.argv)
    except Exception as exc:  # noqa: BLE001 - last-resort guard for the caller
        print(json.dumps({"status": "error", "detail": str(exc)[:300]}))
        code = 2
    sys.stdout.flush()
    raise SystemExit(code)
