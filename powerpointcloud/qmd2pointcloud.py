#!/usr/bin/env python3
"""qmd2pointcloud.py — Convert a Quarto (reveal.js) deck into per-slide point clouds
for OpenSpace.

Pipeline:
  1. Stage  — copy the deck + _quarto.yml + small support dirs (slidelets/, partials/,
              _extensions/, css/, library/) into a temp dir, plus ONLY the asset files
              actually referenced by the deck/slidelets/theme (avoids copying a
              multi-GB assets/ dir full of unused video).
  2. Render — `quarto render <deck>.qmd` in the staging dir (keeps Dropbox out of the
              render/sync loop).
  3. Shot   — Playwright + headless Chromium (1920x1080, deviceScaleFactor=1); navigate
              each slide with Reveal.slide(h, v) and screenshot the active <section>
              -> slides/slide_NNN.png, plus background-only, text-less, media-only, and
              text-only captures (slide_NNN_{bg,notext,media,text}.png).
  4. CSV    — split each slide into background, media, and text layers -> one CSV point
              cloud (x,y,z,r,g,b,size) per slide, 1 point per covered pixel and layer.
              The media and text layers move towards the camera and shrink by the same
              fraction, so the slide looks flat from the prime spot but has depth when
              seen from the side.
  5. Asset  — generate <deck>.asset: one RenderablePointCloud node + Next/Prev slide
              OpenSpace Actions that swap its File property.

Usage:
  python qmd2pointcloud.py <deck.qmd> [--width 1920 --height 1080] [--out DIR]
                           [--keep-png] [--slide-width 10] [--unit Km] [--depth 0.075,0.15]
                           [--point-size 1.5] [--jobs 8] [--browsers 2]
                           [--project DIR]
                           [--parent Root] [--position X,Y,Z] [--from-png | --asset-only]
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image

# --- Defaults ---------------------------------------------------------------
DEFAULT_WIDTH = 1920
DEFAULT_HEIGHT = 1080
DEFAULT_SLIDE_WIDTH_M = 10.0   # slide width in CSV units (1 px = 10/1920 units)
# Distance unit of the CSV coordinates. Kilometers make the 1:1 viewing distance (~6 km)
# much larger than OpenSpace's default minimum camera distance of 10 m
DEFAULT_UNIT = "Km"
UNIT_IN_METERS = {"m": 1.0, "Km": 1000.0}
DEFAULT_PARENT = "Root"
# 1 AU from the solar system barycenter, away from the Sun and the planets. The slide lies
# in the z = 0 plane of the node, facing +z (i.e. towards the barycenter)
DEFAULT_POSITION = (0.0, 0.0, -1.495978707e11)
# How far the media and text layers move towards the camera, as fractions of the
# prime-spot distance
DEFAULT_DEPTH = (0.075, 0.15)
# Point size in pixel pitches; see generate_asset
DEFAULT_POINT_SIZE = 1.5
# The layers of a slide, back to front
LAYERS = ("bg", "media", "text")
CSV_HEADER = "x,y,z,r,g,b,size"
CHUNK_ROWS = 200_000           # CSV write chunk size (rows)
# Parallel CSV writers; beyond ~8 the disk is the bottleneck
DEFAULT_JOBS = min(8, os.cpu_count() or 1)
# Parallel browsers for the screenshots. Every slide waits a fixed time for its transition,
# so browsers competing for the CPU risk capturing unfinished transitions; kept low on
# purpose (1 captures the slides one after the other)
DEFAULT_BROWSERS = 2
SMALL_DIRS = ["slidelets", "partials", "_extensions", "css", "library"]

# --- Asset-reference extraction --------------------------------------------
ASSET_PATTERNS = [
    re.compile(r'!\[[^\]]*\]\(\s*([^)\s]+)'),                          # markdown img/video
    re.compile(r'background-image\s*=\s*["\']?([^"\'}\s]+)'),          # reveal bg attr
    re.compile(r'<img[^>]*\bsrc\s*=\s*["\']([^"\']+)["\']', re.I),     # <img src>
    re.compile(r'<video[^>]*\bsrc\s*=\s*["\']([^"\']+)["\']', re.I),   # <video src>
    re.compile(r'<source[^>]*\bsrc\s*=\s*["\']([^"\']+)["\']', re.I),  # <source src>
    re.compile(r'url\(\s*["\']?([^"\')\s]+)["\']?\s*\)'),              # css url()
    re.compile(r'[\w./\\-]+\.(?:webp|png|jpe?g|svg|mp4|gif|scss|css|js|woff2?)\b'),
]


def log(msg):
    print(f"[qmd2pointcloud] {msg}", flush=True)


def error(msg):
    print(f"[qmd2pointcloud] ERROR: {msg}", file=sys.stderr, flush=True)
    sys.exit(1)


def sanitize_identifier(name):
    """Scene-graph-safe node identifier: alphanumerics only, runs of other chars -> _."""
    s = re.sub(r'[^A-Za-z0-9]+', '_', name).strip('_')
    return s or "Deck"


def is_url(ref):
    # scheme: (http:, https:, data:, mailto:, ...) — not a local file
    return bool(re.match(r'^[a-zA-Z][a-zA-Z0-9+.\-]*:', ref))


def extract_asset_refs(text):
    refs = set()
    for pat in ASSET_PATTERNS:
        for m in pat.finditer(text):
            r = (m.group(1) if m.lastindex else m.group(0)).strip()
            # strip fragment / query
            r = r.split('#', 1)[0].split('?', 1)[0]
            if r:
                refs.add(r)
    return refs


def is_within(path, root):
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except (ValueError, OSError):
        return False


INCLUDE_PATTERN = re.compile(r'\{\{<\s*include\s+([^>]+?)\s*>\}')


def resolve_ref(ref, project_root, fallback_dir):
    """Resolve an asset/include ref to an existing file under project_root.

    Tries the project root first, then the fallback dir (e.g. the containing
    file's dir). A leading '/' is treated as project-root-relative (site-root).
    """
    ref_clean = ref.lstrip('/')
    for base in (project_root, fallback_dir):
        cand = base / ref_clean
        try:
            cand_res = cand.resolve()
        except OSError:
            continue
        if cand_res.is_file() and is_within(cand_res, project_root):
            return cand_res
    return None


def collect_include_tree(deck_path, project_root):
    """Recursively collect all .qmd files in the deck's include tree."""
    seen = set()
    stack = [Path(deck_path)]
    while stack:
        f = stack.pop()
        if f in seen:
            continue
        seen.add(f)
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in INCLUDE_PATTERN.finditer(text):
            inc = m.group(1).strip()
            if not inc.lower().endswith(".qmd"):
                continue
            resolved = resolve_ref(inc, project_root, f.parent)
            if resolved is not None:
                stack.append(resolved)
    return seen


def find_theme_paths(deck_text):
    """Extract custom theme .scss/.css paths from the deck frontmatter."""
    m = re.match(r'^---\s*\n(.*?)\n---\s*\n', deck_text, re.S)
    fm = m.group(1) if m else ""
    themes = set()
    tm = re.search(r'theme\s*:\s*\[([^\]]*)\]', fm)
    if tm:
        for part in tm.group(1).split(","):
            part = part.strip().strip("\"'")
            if part and part.lower() not in ("default", "none"):
                themes.add(part)
    else:
        tm2 = re.search(r'theme\s*:\s*([^\[\n]+)', fm)
        if tm2:
            part = tm2.group(1).strip().strip("\"'")
            if part and part.lower() not in ("default", "none"):
                themes.add(part)
    return themes


# --- Phase 1: stage ---------------------------------------------------------
def stage_project(deck_path, project_root, staging_dir):
    project_root = Path(project_root)
    staging_dir = Path(staging_dir)
    staging_dir.mkdir(parents=True, exist_ok=True)

    # 1. deck + project config
    shutil.copy2(deck_path, staging_dir / deck_path.name)
    qy = project_root / "_quarto.yml"
    if qy.exists():
        shutil.copy2(qy, staging_dir / "_quarto.yml")

    # 2. small support dirs in full
    for d in SMALL_DIRS:
        src = project_root / d
        if src.is_dir():
            shutil.copytree(src, staging_dir / d, dirs_exist_ok=True)

    # 3. collect the deck's include tree (transitively included .qmd files) and
    #    the custom theme file(s) — only these are scanned for asset refs, so we
    #    don't copy large assets referenced by unrelated slidelets.
    include_tree = collect_include_tree(deck_path, project_root)
    deck_text = deck_path.read_text(encoding="utf-8", errors="replace")
    theme_files = []
    for tp in find_theme_paths(deck_text):
        resolved = resolve_ref(tp, project_root, deck_path.parent)
        if resolved is not None:
            theme_files.append(resolved)

    # 4. extract asset refs from the include tree + theme files
    refs_per_file = {}
    for f in include_tree:
        try:
            refs_per_file[f] = extract_asset_refs(f.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            pass
    for tf in theme_files:
        try:
            refs_per_file[tf] = extract_asset_refs(tf.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            pass

    # 5. copy the referenced asset files that exist
    copied, missing = 0, []
    seen = set()
    for f, refs in refs_per_file.items():
        for ref in refs:
            if ref in seen or is_url(ref) or ref.startswith('#'):
                continue
            resolved = resolve_ref(ref, project_root, f.parent)
            if resolved is None:
                missing.append(ref)
                continue
            rel = resolved.relative_to(project_root)
            dest = staging_dir / rel
            if not dest.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(resolved, dest)
                copied += 1
            seen.add(ref)

    log(f"Include tree: {len(include_tree)} slide(s); theme: {len(theme_files)} file(s)")
    log(f"Staged {copied} referenced asset files"
        + (f" ({len(missing)} not found: {missing[:5]}{'...' if len(missing) > 5 else ''})"
           if missing else ""))
    return staging_dir


# --- Phase 2: render --------------------------------------------------------
def render_quarto(staging_dir, deck_name):
    log(f"Rendering {deck_name} with quarto ...")
    result = subprocess.run(
        ["quarto", "render", deck_name],
        cwd=str(staging_dir),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        error(f"quarto render failed (exit {result.returncode}):\n"
              f"--- STDOUT ---\n{result.stdout}\n--- STDERR ---\n{result.stderr}")
    stem = Path(deck_name).stem
    candidates = []
    for d in (staging_dir / "output", staging_dir):
        if d.is_dir():
            candidates.extend(d.glob("*.html"))
    html_path = next((c for c in candidates if c.stem == stem), None)
    if html_path is None and candidates:
        html_path = candidates[0]
    if html_path is None:
        error(f"Rendered HTML not found for {deck_name}")
    log(f"Rendered HTML: {html_path}")
    return html_path


# --- Phase 3: screenshot ----------------------------------------------------
def _slide_positions_js():
    # NOTE: Reveal.getSlides() returns an array of DOM nodes (not [h,v] pairs),
    # so enumerate slides from the DOM instead. A horizontal slide's direct-child
    # <section> elements are its vertical sub-slides (reveal.js convention).
    return """
    () => {
      const out = [];
      const hSections = document.querySelectorAll('.slides > section');
      for (let h = 0; h < hSections.length; h++) {
        const vSections = hSections[h].querySelectorAll(':scope > section');
        if (vSections.length > 0) {
          for (let v = 0; v < vSections.length; v++) out.push([h, v]);
        } else {
          out.push([h, 0]);
        }
      }
      return out;
    }
    """


_NO_TRANSITIONS = ("*, *::before, *::after { transition: none !important; "
                   "animation-play-state: paused !important; }")
# Makes all text invisible while keeping its layout, so that only the media remains
_HIDE_TEXT = ("*, *::before, *::after, *::marker { color: transparent !important; "
              "-webkit-text-fill-color: transparent !important; "
              "text-decoration-color: transparent !important; "
              "text-shadow: none !important; caret-color: transparent !important; } "
              # List bullets are often drawn as colored boxes; they belong to the text
              "li::before, li::after { visibility: hidden !important; }")
# opacity instead of visibility, as reveal.js makes the present slide (background)
# visible again, and that overrides an inherited visibility: hidden
_HIDE_BACKGROUND = (".reveal > .backgrounds { opacity: 0 !important; } "
                    "html, body, .reveal-viewport, .reveal { "
                    "background: transparent !important; }")
# Makes everything except the text invisible
_ONLY_TEXT = ("*, *:not(li)::before, *:not(li)::after { "
              "background: transparent !important; "
              "border-color: transparent !important; outline-color: transparent !important; "
              "box-shadow: none !important; } "
              "img, video, canvas, svg, iframe, object, embed, picture { "
              "opacity: 0 !important; }")

# PNG suffix, extra CSS, and whether the page background is transparent for each capture
LAYER_CAPTURES = [
    ("", "", False),                    # the slide as shown in the browser
    ("_bg", ".reveal > :not(.backgrounds) { opacity: 0 !important; }", False),
    ("_notext", _HIDE_TEXT, False),     # background + media
    ("_media", _HIDE_TEXT + " " + _HIDE_BACKGROUND, True),
    ("_text", _ONLY_TEXT + " " + _HIDE_BACKGROUND, True),
]

_SET_LAYER_CSS_JS = """
(css) => {
  let style = document.getElementById('qmd2pc-layer');
  if (!style) {
    style = document.createElement('style');
    style.id = 'qmd2pc-layer';
    document.head.appendChild(style);
  }
  style.textContent = css;
  return new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
}
"""


def _open_deck(playwright, html_url, width, height):
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(
        viewport={"width": width, "height": height},
        device_scale_factor=1,
    )
    page.goto(html_url, wait_until="networkidle", timeout=60000)
    page.wait_for_function(
        "() => window.Reveal && typeof Reveal.isReady === 'function' && Reveal.isReady() === true",
        timeout=30000,
    )
    # Remove the reveal.js margin so the active slide fills the viewport exactly.
    page.evaluate("() => { if (window.Reveal) Reveal.configure({ margin: 0 }); }")
    page.wait_for_timeout(300)
    return browser, page


def _capture_slides(page, slides, out_dir, captures, n):
    """Screenshots the `slides`, a list of (index, (h, v)), and returns the PNG paths."""
    png_paths = []
    for idx, (h, v) in slides:
        page.evaluate(f"() => Reveal.slide({h}, {v})")
        page.wait_for_timeout(1000)  # slidechanged + fade transition settle
        # Freeze videos so that all captures of this slide show the same frame
        page.evaluate("() => document.querySelectorAll('video').forEach(v => v.pause())")
        box = page.evaluate(
            "() => { const ps = document.querySelectorAll('.slides section.present');"
            " const r = ps[ps.length - 1].getBoundingClientRect();"
            " return { x: r.x, y: r.y, width: r.width, height: r.height }; }"
        )
        stem = f"slide_{idx + 1:03d}"
        for suffix, css, transparent in captures:
            page.evaluate(_SET_LAYER_CSS_JS, (_NO_TRANSITIONS + " " + css) if css else "")
            png_path = out_dir / f"{stem}{suffix}.png"
            # A page screenshot clipped to the slide, as the slide element itself is
            # hidden for some of the captures
            page.screenshot(path=str(png_path), clip=box, omit_background=transparent)
            png_paths.append(png_path)
        page.evaluate(_SET_LAYER_CSS_JS, "")
        log(f"  slide {idx + 1}/{n} ({h},{v}) -> {stem}.png")
    return png_paths


def _capture_in_new_browser(html_url, width, height, slides, out_dir, captures, n):
    # Playwright's sync API is not thread-safe, so every thread has its own instance
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser, page = _open_deck(p, html_url, width, height)
        try:
            return _capture_slides(page, slides, out_dir, captures, n)
        finally:
            browser.close()


def screenshot_slides(html_path, out_dir, width, height, layered,
                      browsers=DEFAULT_BROWSERS):
    """Screenshots every slide to slide_NNN.png. With `layered`, the background-only,
    text-less, media-only, and text-only versions of every slide are captured as well
    (see LAYER_CAPTURES). Up to `browsers` browsers capture consecutive runs of slides in
    parallel."""
    from playwright.sync_api import sync_playwright

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    html_url = Path(html_path).resolve().as_uri()
    captures = LAYER_CAPTURES if layered else LAYER_CAPTURES[:1]

    with sync_playwright() as p:
        browser, page = _open_deck(p, html_url, width, height)
        slides = [(idx, (int(h), int(v)))
                  for idx, (h, v) in enumerate(page.evaluate(_slide_positions_js()))]
        n = len(slides)
        # Consecutive runs, so that every slide is entered from the slide before it like
        # in the presentation (as far as possible)
        k = max(1, min(browsers, n))
        runs = [slides[i * n // k:(i + 1) * n // k] for i in range(k)]
        log(f"Found {n} slides; capturing with {len(runs)} browser(s)")
        # This thread captures the first run with the browser that is already open
        with ThreadPoolExecutor(max_workers=max(1, len(runs) - 1)) as pool:
            futures = [pool.submit(_capture_in_new_browser, html_url, width, height, run,
                                   out_dir, captures, n)
                       for run in runs[1:]]
            png_paths = _capture_slides(page, runs[0], out_dir, captures, n)
            browser.close()
            for future in futures:
                png_paths += future.result()

    if png_paths:
        with Image.open(png_paths[0]) as im:
            w, h = im.size
            status = "OK" if (w, h) == (width, height) else "MISMATCH (will resize)"
            log(f"First slide screenshot: {w}x{h} (expected {width}x{height}) [{status}]")
    return png_paths


# --- Phase 4: PNG -> layers -> CSV --------------------------------------------
def _fmt(values, fmt="%.6f"):
    """`values` formatted with `fmt` as a fixed-width bytes array."""
    return np.char.mod(fmt, values).astype("S")


def _load_png(path, width, height, mode="RGB"):
    with Image.open(path) as im:
        im = im.convert(mode)
        if im.size != (width, height):
            im = im.resize((width, height), Image.LANCZOS)
        return np.asarray(im, dtype=np.float64)


def _psnr(a, b):
    mse = np.mean((a - b) ** 2)
    return 10.0 * np.log10(255.0 ** 2 / mse) if mse > 0 else float("inf")


def split_layers(slides_dir, stem, width, height, depths):
    """Returns {layer: (mask, rgb)} for the slide `stem`, back to front, and a summary line
    for the log (None for a flat slide).

    Each pixel belongs to the background and, if covered, to the media and/or text layer.
    The front-most layer of a pixel takes the color of the full slide so that the slide
    looks unchanged from the prime spot; covered pixels take the color of the render of
    their own layer, so that the layers are complete when seen from the side. Layers with
    a depth of 0 are part of the layer behind them.
    """
    full = _load_png(slides_dir / f"{stem}.png", width, height)
    everything = np.ones(full.shape[:2], dtype=bool)
    if not any(depths.values()):
        return {"bg": (everything, full)}, None

    paths = {s: slides_dir / f"{stem}{s}.png" for s, _, _ in LAYER_CAPTURES[1:]}
    bg = _load_png(paths["_bg"], width, height)
    notext = _load_png(paths["_notext"], width, height)
    media = _load_png(paths["_media"], width, height, "RGBA")
    text = _load_png(paths["_text"], width, height, "RGBA")

    media_mask = media[:, :, 3] > 0
    text_mask = text[:, :, 3] > 0

    # The media composited over the background must give the text-less slide, otherwise
    # the theme paints something that none of the captures separate cleanly
    alpha = media[:, :, 3:] / 255.0
    psnr = _psnr(alpha * media[:, :, :3] + (1.0 - alpha) * bg, notext)
    note = "" if psnr > 30.0 else "  WARNING: layers do not composite to the slide"
    summary = (f"  {stem}: media {media_mask.mean():5.1%}, text {text_mask.mean():5.1%}, "
               f"composite PSNR {psnr:.1f} dB{note}")

    if not depths["media"]:
        media_mask = np.zeros_like(media_mask)
    if not depths["text"]:
        text_mask = np.zeros_like(text_mask)
    top_media = media_mask & ~text_mask
    top_bg = ~(media_mask | text_mask)
    return {
        "bg": (everything, np.where(top_bg[:, :, None], full, bg)),
        "media": (media_mask, np.where(top_media[:, :, None], full, notext)),
        "text": (text_mask, full),
    }, summary


def write_slide_csv(csv_path, layers, depths, slide_width):
    """Writes one point for every pixel of every layer, colored by the layer's `rgb`
    (0-255).

    A layer with the depth f is shrunk by 1 - f about the slide center and moved
    f * slide_width / 2 towards the camera. The asset stretches z by 1 / tan(hfov / 2),
    which puts the layer at f times the prime-spot distance, where it covers the same
    screen pixels as a flat slide. The size column shrinks its points by the same factor.
    """
    # x only depends on the pixel column, y on the row, and r, g, b take 256 values, so
    # every value is formatted once and the rows are assembled from these lookup tables
    color = _fmt(np.arange(256) / 255.0)
    with open(csv_path, "wb") as f:
        f.write((CSV_HEADER + "\n").encode())
        for layer, (mask, rgb) in layers.items():
            H, W = mask.shape
            depth = depths[layer]
            scale = 1.0 - depth
            s = slide_width / W * scale
            # Points sit at pixel centers so that, with the slide origin in the middle of
            # the screen (a pixel boundary), each point covers exactly one screen pixel
            xs = _fmt((np.arange(W) + 0.5 - W / 2.0) * s)
            ys = _fmt((H / 2.0 - np.arange(H) - 0.5) * s)
            z = ("," + "%.6f" % (depth * slide_width / 2.0)).encode()
            size = ("," + "%g" % scale + "\n").encode()
            rgb = rgb.astype(np.uint8)
            v, u = np.nonzero(mask)
            for start in range(0, v.size, CHUNK_ROWS):
                vv, uu = v[start:start + CHUNK_ROWS], u[start:start + CHUNK_ROWS]
                lines = np.strings.add(np.strings.add(xs[uu], b","), ys[vv])
                lines = np.strings.add(lines, z)
                for c in range(3):
                    lines = np.strings.add(np.strings.add(lines, b","), color[rgb[vv, uu, c]])
                lines = np.strings.add(lines, size)
                # The fixed-width array pads the shorter lines with NUL bytes
                f.write(lines.tobytes().replace(b"\0", b""))


def _slide_to_csv(slides_dir, stem, width, height, depths, slide_width):
    """Writes the CSV of one slide; runs in a worker process. Returns the digest of the
    slide's points, the layers with points, and the log summary."""
    layers, summary = split_layers(slides_dir, stem, width, height, depths)
    layers = {layer: (mask, rgb) for layer, (mask, rgb) in layers.items() if mask.any()}
    digest = hashlib.sha1()
    for layer, (mask, rgb) in layers.items():
        digest.update(layer.encode())
        digest.update(np.packbits(mask).tobytes())
        digest.update(rgb.astype(np.uint8).tobytes())
    write_slide_csv(slides_dir / f"{stem}.csv", layers, depths, slide_width)
    return digest.hexdigest(), list(layers), summary


def slides_to_csv(slides_dir, n_slides, width, height, slide_width, depth,
                  jobs=DEFAULT_JOBS):
    """Writes slide_NNN.csv with the points of all layers for every slide, `jobs` slides
    in parallel, and returns the number of slides. Identical slides are hard links to the
    first copy to save disk space."""
    for old in slides_dir.glob("slide_*.csv"):
        old.unlink()
    depths = dict(zip(LAYERS, (0.0, *depth)))
    stems = [f"slide_{idx:03d}" for idx in range(1, n_slides + 1)]
    if any(depths.values()):
        missing = [f"{stem}{suffix}.png" for stem in stems for suffix, _, _ in LAYER_CAPTURES
                   if not (slides_dir / f"{stem}{suffix}.png").exists()]
        if missing:
            error(f"Missing layer PNGs {missing[:5]}{'...' if len(missing) > 5 else ''}; "
                  f"re-render the deck or use --depth 0")

    jobs = max(1, min(jobs, n_slides))
    args = [(slides_dir, stem, width, height, depths, slide_width) for stem in stems]
    pool = ProcessPoolExecutor(max_workers=jobs) if jobs > 1 else None
    try:
        results = (pool.map(_slide_to_csv, *zip(*args)) if pool
                   else (_slide_to_csv(*a) for a in args))
        written = {}
        counts = dict.fromkeys(LAYERS, 0)
        for stem, (key, layers, summary) in zip(stems, results):
            if summary:
                log(summary)
            for layer in layers:
                counts[layer] += 1
            csv_path = slides_dir / f"{stem}.csv"
            if key not in written:
                written[key] = csv_path
                continue
            # The workers cannot know about duplicates, so replace the copy with a link
            csv_path.unlink()
            try:
                os.link(written[key], csv_path)
            except OSError:
                shutil.copy2(written[key], csv_path)
    finally:
        if pool:
            pool.shutdown()
    log(f"  {n_slides} slides ({len(written)} distinct), media on {counts['media']}, "
        f"text on {counts['text']}")
    return n_slides


# --- Phase 5: generate .asset ----------------------------------------------
def _step_command(identifier, n_slides, step):
    """Lua for an Action that moves `step` slides (clamped) by swapping the File property.

    Action `Command`s are static Lua strings, so the current slide index is recovered
    from the File property value (".../slide_NNN.csv").
    """
    return "\n".join([
        f'local uri = "Scene.{identifier}.Renderable.File"',
        'local cur = openspace.propertyValue(uri) or ""',
        'local i = tonumber(string.match(cur, "slide_(%d+)%.csv$")) or 1',
        f'local j = math.max(1, math.min({n_slides}, i + ({step})))',
        'if j ~= i then',
        '  local dir = string.match(cur, "^(.*)slide_%d+%.csv$") or ""',
        '  openspace.setPropertyValueSingle(uri, dir .. string.format("slide_%03d.csv", j))',
        'end',
    ])


def _distance_lua(slide_width_m):
    """Lua that computes `d`, the camera distance at which the slide fills the horizontal
    FOV, i.e. one point per screen pixel when the window is as wide as the slide (in px)."""
    return (
        f'local fov = openspace.propertyValue(\n'
        f'  "RenderEngine.Windowing.Window_0.HorizFieldOfView"\n'
        f') or 80.0\n'
        f'local d = {slide_width_m / 2.0!r} / math.tan(math.rad(fov / 2.0))'
    )


def _place_layers_lua(identifier, slide_width_m):
    """Lua that stretches z by d / (w / 2) = 1 / tan(hfov / 2), which moves every layer to
    its fraction of `d` in front of the background (see write_slide_csv)."""
    return (
        f'openspace.setPropertyValueSingle(\n'
        f'  "Scene.{identifier}.Scale.Scale",\n'
        f'  {{ 1.0, 1.0, d / {slide_width_m / 2.0!r} }}\n'
        f')'
    )


def _frame_command(identifier, parent, slide_width_m):
    """Lua for an Action that places the camera at the prime spot, where the slide fills
    the horizontal FOV, and moves the layers so that the slide looks flat from there."""
    # The navigation state applies the scale of its reference frame to the camera
    # position, so it uses the unscaled parent rather than the z-stretched slide node
    return "\n".join([
        _distance_lua(slide_width_m),
        _place_layers_lua(identifier, slide_width_m),
        f'openspace.navigation.setNavigationState({{\n'
        f'  Anchor = "{identifier}", ReferenceFrame = "{parent}",\n'
        f'  Position = {{ 0.0, 0.0, d }}, Up = {{ 0.0, 1.0, 0.0 }}\n'
        f'}})',
    ])


def _lua_string(s):
    return json.dumps(s, ensure_ascii=False)


def generate_asset(out_dir, deck_name, n_slides, identifier, slide_width, unit, width,
                   parent, position, point_size=DEFAULT_POINT_SIZE):
    out_dir = Path(out_dir)
    slide_width_m = slide_width * UNIT_IN_METERS[unit]
    pitch = slide_width_m / width
    pos = ", ".join(repr(float(c)) for c in position)

    actions = [
        ("NextSlide", "Next slide", "PAGEDOWN",
         _step_command(identifier, n_slides, +1), "Show the next slide"),
        ("PrevSlide", "Previous slide", "PAGEUP",
         _step_command(identifier, n_slides, -1), "Show the previous slide"),
        ("FirstSlide", "First slide", "HOME",
         _step_command(identifier, n_slides, -n_slides), "Show the first slide"),
        ("LastSlide", "Last slide", "END",
         _step_command(identifier, n_slides, n_slides), "Show the last slide"),
        ("FrameSlide", "Frame slide", "SHIFT+HOME",
         _frame_command(identifier, parent, slide_width_m),
         "Move the camera in front of the slide so that it fills the horizontal field of "
         "view"),
    ]

    action_defs = []
    for key, name, _, command, doc in actions:
        action_defs.append(f"""local {key} = {{
  Identifier = "{identifier}.{key}",
  Name = {_lua_string(name + " (" + deck_name + ")")},
  Command = [[
{command}
  ]],
  Documentation = {_lua_string(doc)},
  GuiPath = "/Presentations/" .. deck,
  IsLocal = false
}}""")
    register = "\n".join(
        f"  openspace.action.registerAction({key})\n  openspace.bindKey(\"{binding}\", {key})"
        for key, _, binding, _, _ in actions)
    unregister = "\n".join(
        f"  openspace.clearKey(\"{binding}\")\n  openspace.action.removeAction({key})"
        for key, _, binding, _, _ in reversed(actions))
    exports = "\n".join(f"asset.export(\"{key}\", {key}.Identifier)"
                        for key, _, _, _, _ in actions)

    place_layers = "\n".join(
        "  " + line
        for line in (_distance_lua(slide_width_m) + "\n"
                     + _place_layers_lua(identifier, slide_width_m)).split("\n"))

    lua = f"""-- Generated by qmd2pointcloud.py -- one point per slide pixel and layer, swapped per
-- slide through the File property of the Renderable. The background, media, and text of
-- the slides are layers at different depths that look flat from the prime spot.
--   PageDown / PageUp: next / previous slide,  Home / End: first / last slide,
--   Shift+Home: move the camera to the prime spot in front of the slide (1 point per
--   screen pixel when the rendering is {width} px wide)

local deck = {_lua_string(deck_name)}
local unit = "{unit}"

local Slides = {{
  Identifier = "{identifier}",
  Parent = "{parent}",
  Transform = {{
    Translation = {{
      Type = "StaticTranslation",
      Position = {{ {pos} }}
    }},
    -- The media and text layers lie in front of the background at fractions of half the
    -- slide width; placeLayers stretches z to make them fractions of the prime-spot
    -- distance for the current field of view
    Scale = {{
      Type = "NonUniformStaticScale",
      Scale = {{ 1.0, 1.0, 1.0 }}
    }}
  }},
  Renderable = {{
    Type = "RenderablePointCloud",
    File = asset.resource("slides/slide_001.csv"),
    Unit = unit,
    -- The slide is opaque; additive blending would brighten overlapping points
    UseAdditiveBlending = false,
    Coloring = {{
      Rgb = {{ R = "r", G = "g", B = "b" }},
      -- Square instead of round points so that neighboring pixels tile without gaps.
      -- An outline width of 0 never draws an outline
      EnableOutline = true,
      OutlineStyle = "Square",
      OutlineWidth = 0.0
    }},
    -- With a scale exponent of 0, the point size is the scale factor in meters: here
    -- {point_size!r} pixel pitches of {slide_width_m!r} m / {width} px. Points larger than a
    -- pixel leave no gaps when the layers are seen at an angle; below two pixels, every
    -- screen pixel at the prime spot still only shows its own point
    SizeSettings = {{
      ScaleExponent = 0.0,
      ScaleFactor = {point_size * pitch!r},
      -- The size column shrinks the points of the media and text layers like the layers
      -- themselves
      SizeMapping = {{ ParameterOptions = {{ "size" }}, Parameter = "size" }}
    }}
  }},
  GUI = {{
    Name = deck,
    Path = "/Presentations",
    Description = "Slides of the presentation " .. deck .. " ({n_slides} slides)"
  }}
}}

-- Moves the layers to their depth for the current field of view
local function placeLayers()
{place_layers}
end

{chr(10).join(action_defs)}


asset.onInitialize(function()
  openspace.addSceneGraphNode(Slides)
  placeLayers()
{register}
end)

asset.onDeinitialize(function()
{unregister}
  openspace.removeSceneGraphNode(Slides)
end)

asset.export(Slides)
{exports}
"""
    asset_path = out_dir / f"{deck_name}.asset"
    asset_path.write_text(lua, encoding="utf-8")
    log(f"Wrote {asset_path}")
    return asset_path


# --- main -------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("deck", help="Path to the deck .qmd file")
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH)
    parser.add_argument("--height", type=int, default=DEFAULT_HEIGHT)
    parser.add_argument("--out", default=None,
                        help="Output dir (default: <script_dir>/output/<deck>)")
    parser.add_argument("--keep-png", action="store_true", help="Keep slide PNGs")
    parser.add_argument("--slide-width", type=float, default=DEFAULT_SLIDE_WIDTH_M,
                        help="Slide width in CSV units (default 10)")
    parser.add_argument("--unit", default=DEFAULT_UNIT, choices=sorted(UNIT_IN_METERS),
                        help="Distance unit of the CSV coordinates (default Km)")
    parser.add_argument("--depth", default=",".join(str(f) for f in DEFAULT_DEPTH),
                        help="MEDIA,TEXT: how far the media and text layers move towards "
                             "the camera, as fractions of the prime-spot distance "
                             "(default %(default)s; 0 gives a flat slide). Baked into "
                             "the CSVs, so --asset-only ignores it")
    parser.add_argument("--point-size", type=float, default=DEFAULT_POINT_SIZE,
                        help="Point size in pixel pitches (default %(default)s); larger "
                             "than 1 closes the gaps between the points of the layers "
                             "seen at an angle, below 2 keeps the prime-spot view exact")
    parser.add_argument("--jobs", type=int, default=DEFAULT_JOBS,
                        help="Number of slides whose CSVs are written in parallel "
                             "(default %(default)s)")
    parser.add_argument("--browsers", type=int, default=DEFAULT_BROWSERS,
                        help="Number of browsers that take the screenshots in parallel "
                             "(default %(default)s)")
    parser.add_argument("--project", default=None,
                        help="Quarto project root (default: dir containing the deck)")
    parser.add_argument("--parent", default=DEFAULT_PARENT,
                        help="Scene graph parent of the slide node (default: Root)")
    parser.add_argument("--position", default=",".join(str(c) for c in DEFAULT_POSITION),
                        help="Slide position relative to the parent in meters, as X,Y,Z "
                             "(default: 1 AU from the solar system barycenter)")
    parser.add_argument("--from-png", action="store_true",
                        help="Rebuild the CSVs and the .asset from existing slide PNGs "
                             "(from an earlier --keep-png run) without rendering")
    parser.add_argument("--asset-only", action="store_true",
                        help="Only regenerate the .asset from the existing slide CSVs "
                             "(e.g. for another --point-size, --parent, or --position)")
    args = parser.parse_args()

    try:
        position = [float(c) for c in args.position.split(",")]
    except ValueError:
        position = []
    if len(position) != 3:
        error(f"--position must be X,Y,Z, got {args.position!r}")
    try:
        depth = [float(f) for f in args.depth.split(",")]
    except ValueError:
        depth = []
    if depth == [0.0]:
        depth = [0.0, 0.0]
    if len(depth) != 2 or not all(0.0 <= f < 1.0 for f in depth):
        error(f"--depth must be MEDIA,TEXT with values in [0, 1), got {args.depth!r}")
    layered = any(f > 0.0 for f in depth)
    if not 0.0 < args.point_size < 2.0:
        error(f"--point-size must be in (0, 2), got {args.point_size!r}")
    if args.jobs < 1 or args.browsers < 1:
        error("--jobs and --browsers must be at least 1")

    deck_path = Path(args.deck).resolve()
    if not deck_path.exists():
        error(f"Deck not found: {deck_path}")
    project_root = Path(args.project).resolve() if args.project else deck_path.parent

    deck_name = deck_path.stem
    identifier = "Presentation_" + sanitize_identifier(deck_name)
    out_dir = (Path(args.out) if args.out
               else Path(__file__).parent / "output" / deck_name).resolve()
    slides_dir = out_dir / "slides"
    slides_dir.mkdir(parents=True, exist_ok=True)

    log(f"Deck:         {deck_name}")
    log(f"Project root: {project_root}")
    log(f"Output:       {out_dir}")

    def finish(n_slides):
        generate_asset(out_dir, deck_name, n_slides, identifier, args.slide_width,
                       args.unit, args.width, args.parent, position, args.point_size)
        log(f"Done: {n_slides} slides -> {out_dir}")

    if args.asset_only:
        n_slides = len([p for p in slides_dir.glob("slide_*.csv")
                        if re.fullmatch(r"slide_\d+\.csv", p.name)])
        if n_slides == 0:
            error(f"No slide CSVs found in {slides_dir}")
        finish(n_slides)
        return

    if args.from_png:
        n_slides = len([p for p in slides_dir.glob("slide_*.png")
                        if re.fullmatch(r"slide_\d+\.png", p.name)])
        if n_slides == 0:
            error(f"No slide PNGs found in {slides_dir}")
        finish(slides_to_csv(slides_dir, n_slides, args.width, args.height,
                             args.slide_width, depth, args.jobs))
        return

    staging_dir = Path(tempfile.mkdtemp(prefix="qmd2pc_"))
    try:
        stage_project(deck_path, project_root, staging_dir)
        html_path = render_quarto(staging_dir, deck_path.name)
        for old in slides_dir.glob("slide_*.png"):
            old.unlink()
        png_paths = screenshot_slides(html_path, slides_dir, args.width, args.height,
                                      layered, args.browsers)
        if not png_paths:
            error("No slides captured")
        n_slides = len(png_paths) // (len(LAYER_CAPTURES) if layered else 1)
        finish(slides_to_csv(slides_dir, n_slides, args.width, args.height,
                             args.slide_width, depth, args.jobs))
        if not args.keep_png:
            for png in png_paths:
                png.unlink()
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
