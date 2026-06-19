#!/usr/bin/env python3
"""
analyze_image.py -- Stage 0 + Stage 1 pixel-evidence extractor for the
Comprehensive Image Evaluation Protocol.

Purpose: produce AUDITABLE, measured signals from real pixels so that every
later interpretive claim can be traced to a number on this page. It deliberately
emits NO adjectives and NO subject guesses -- only measurements.

Usage:
    python3 analyze_image.py <image_path> [--json out.json] [--quiet]

Outputs a human-readable evidence table to stdout and, with --json, a machine
readable dump. Each metric carries a `method` note so the reader knows how it
was derived and how much to trust it. Heuristic/proxy metrics are labelled as
such -- do not present them as ground truth.

Dependencies: Pillow, numpy. scikit-learn is used for the palette if present,
otherwise a numpy k-means fallback runs. Nothing else is required, so the script
stays portable across sandboxes.
"""

import sys
import os
import io
import json
import argparse
import math

import numpy as np
from PIL import Image, ImageChops

try:
    from PIL import ExifTags
    _EXIF_TAGS = {v: k for k, v in ExifTags.TAGS.items()}
    _TAGS = ExifTags.TAGS
except Exception:  # pragma: no cover
    _TAGS = {}

try:
    from sklearn.cluster import KMeans
    _HAVE_SK = True
except Exception:
    _HAVE_SK = False


# ----------------------------------------------------------------------------
# small helpers
# ----------------------------------------------------------------------------
def _r(x, n=2):
    """Round, tolerating None/NaN so the JSON never breaks."""
    try:
        if x is None:
            return None
        if isinstance(x, (int,)):
            return x
        f = float(x)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, n)
    except Exception:
        return None


def _rgb_to_hex(c):
    return "#{:02X}{:02X}{:02X}".format(int(c[0]), int(c[1]), int(c[2]))


def _srgb_to_linear(a):
    a = a / 255.0
    return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)


def _luma(rgb):
    """Rec.709 luma in 0-255 from an HxWx3 uint8/float array."""
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


# ----------------------------------------------------------------------------
# Stage 0 -- ingest & metadata
# ----------------------------------------------------------------------------
def stage0(path, im):
    fmt = im.format
    mode = im.mode
    w, h = im.size
    fsize = os.path.getsize(path)
    icc = "present" if im.info.get("icc_profile") else "absent"
    bits = {"1": 1, "L": 8, "P": 8, "RGB": 8, "RGBA": 8, "CMYK": 8,
            "I;16": 16, "I": 32, "F": 32}.get(mode, 8)

    # very rough JPEG "quality" proxy via bytes-per-pixel; only meaningful for JPEG
    bpp = (fsize * 8.0) / (w * h)
    comp = None
    if fmt == "JPEG":
        # heuristic banding: <1.0 bpp ~ heavily compressed, >3 ~ light
        if bpp < 1.0:
            comp = "high compression (proxy bpp=%.2f)" % bpp
        elif bpp < 2.5:
            comp = "moderate compression (proxy bpp=%.2f)" % bpp
        else:
            comp = "light compression (proxy bpp=%.2f)" % bpp
    elif fmt in ("PNG", "TIFF", "BMP"):
        comp = "lossless/container (bpp=%.2f)" % bpp

    out = {
        "filename": os.path.basename(path),
        "format": fmt,
        "mode": mode,
        "bit_depth_per_channel": bits,
        "width_px": w,
        "height_px": h,
        "megapixels": _r((w * h) / 1e6, 2),
        "aspect_ratio": _r(w / h, 3),
        "file_size_bytes": fsize,
        "file_size_human": _human_bytes(fsize),
        "bytes_per_pixel_x8": _r(bpp, 2),
        "icc_profile": icc,
        "estimated_compression": comp,
    }
    return out


def _human_bytes(n):
    for u in ["B", "KB", "MB", "GB"]:
        if n < 1024:
            return "%.1f %s" % (n, u)
        n /= 1024.0
    return "%.1f TB" % n


def exif(im):
    data = {}
    try:
        raw = im.getexif()
    except Exception:
        raw = None
    if not raw:
        return {"present": False}
    wanted = ["Make", "Model", "LensModel", "FocalLength", "FNumber",
              "ExposureTime", "ISOSpeedRatings", "PhotographicSensitivity",
              "DateTimeOriginal", "DateTime", "Orientation", "Software"]
    name_map = {v: k for k, v in _TAGS.items()} if _TAGS else {}
    for nm in wanted:
        tagid = name_map.get(nm)
        if tagid is None:
            continue
        val = raw.get(tagid)
        if val is None:
            continue
        try:
            if isinstance(val, tuple) and len(val) == 2:
                val = val[0] / val[1] if val[1] else val[0]
            data[nm] = val
        except Exception:
            data[nm] = str(val)
    data["present"] = len(data) > 0
    return data


# ----------------------------------------------------------------------------
# Stage 1.1 -- tonal & dynamic range
# ----------------------------------------------------------------------------
def tonal(rgb):
    out = {}
    chans = {"R": rgb[..., 0], "G": rgb[..., 1], "B": rgb[..., 2], "Luma": _luma(rgb)}
    for nm, ch in chans.items():
        c = ch.ravel()
        out[nm] = {
            "mean": _r(c.mean(), 1),
            "median": _r(np.median(c), 1),
            "sd": _r(c.std(), 1),
            "p01": _r(np.percentile(c, 1), 1),
            "p99": _r(np.percentile(c, 99), 1),
        }
    luma = chans["Luma"]
    n = luma.size
    shadow_clip = float((luma <= 1).sum()) / n * 100.0
    high_clip = float((luma >= 254).sum()) / n * 100.0
    p005 = np.percentile(luma, 0.5)
    p995 = np.percentile(luma, 99.5)
    # effective DR in stops over the usable 0.5-99.5 pct span (proxy)
    dr_stops = math.log2((p995 + 1) / (p005 + 1)) if p995 > p005 else 0
    out["clipping"] = {
        "shadow_clip_pct": _r(shadow_clip, 3),
        "highlight_clip_pct": _r(high_clip, 3),
    }
    out["dynamic_range"] = {
        "luma_p0.5": _r(p005, 1),
        "luma_p99.5": _r(p995, 1),
        "usable_span_0_255": _r(p995 - p005, 1),
        "effective_stops_proxy": _r(dr_stops, 2),
        "method": "log2((p99.5+1)/(p0.5+1)) on luma; proxy for tonal spread, not sensor DR",
    }
    return out


# ----------------------------------------------------------------------------
# Stage 1.2 -- color: palette, white balance, saturation
# ----------------------------------------------------------------------------
def _kmeans_palette(pixels, k=6, seed=0):
    if _HAVE_SK:
        km = KMeans(n_clusters=k, n_init=4, random_state=seed)
        labels = km.fit_predict(pixels)
        centers = km.cluster_centers_
    else:
        rng = np.random.default_rng(seed)
        centers = pixels[rng.choice(len(pixels), k, replace=False)].astype(float)
        for _ in range(12):
            d = ((pixels[:, None, :] - centers[None, :, :]) ** 2).sum(2)
            labels = d.argmin(1)
            for i in range(k):
                m = labels == i
                if m.any():
                    centers[i] = pixels[m].mean(0)
    counts = np.bincount(labels, minlength=k).astype(float)
    share = counts / counts.sum() * 100.0
    order = np.argsort(-share)
    pal = []
    for i in order:
        pal.append({"hex": _rgb_to_hex(centers[i]),
                    "rgb": [int(centers[i][0]), int(centers[i][1]), int(centers[i][2])],
                    "share_pct": _r(share[i], 1)})
    return pal


def _mccamy_cct(rgb_mean):
    """Correlated colour temperature (K) from average RGB via McCamy's formula."""
    r, g, b = [v / 255.0 for v in rgb_mean]
    rl, gl, bl = _srgb_to_linear(np.array([r * 255, g * 255, b * 255]))
    X = 0.4124 * rl + 0.3576 * gl + 0.1805 * bl
    Y = 0.2126 * rl + 0.7152 * gl + 0.0722 * bl
    Z = 0.0193 * rl + 0.1192 * gl + 0.9505 * bl
    s = X + Y + Z
    if s <= 0:
        return None, None
    x = X / s
    y = Y / s
    if (y - 0.1858) == 0:
        return None, None
    nn = (x - 0.3320) / (0.1858 - y)
    cct = 449 * nn ** 3 + 3525 * nn ** 2 + 6823.3 * nn + 5520.33
    # green-magenta tint proxy: + = green excess
    tint = _r((gl - (rl + bl) / 2) / 255.0 * 100, 1)
    return _r(cct, 0), tint


def color(rgb):
    flat = rgb.reshape(-1, 3)
    # subsample for speed/determinism
    if len(flat) > 60000:
        idx = np.linspace(0, len(flat) - 1, 60000).astype(int)
        sample = flat[idx]
    else:
        sample = flat
    pal = _kmeans_palette(sample.astype(float), k=6)
    rgb_mean = flat.mean(0)
    cct, tint = _mccamy_cct(rgb_mean)
    # saturation via HSV S channel
    mx = rgb.max(2).astype(float)
    mn = rgb.min(2).astype(float)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0) * 100
    return {
        "palette_kmeans6": pal,
        "avg_rgb": [int(rgb_mean[0]), int(rgb_mean[1]), int(rgb_mean[2])],
        "white_balance": {"cct_kelvin_proxy": cct, "tint_green_magenta": tint,
                          "method": "McCamy CCT on mean RGB; whole-frame average, not a grey-card reading"},
        "saturation": {"mean_pct": _r(sat.mean(), 1), "p95_pct": _r(np.percentile(sat, 95), 1)},
    }


# ----------------------------------------------------------------------------
# Stage 1.3 -- geometry & layout
# ----------------------------------------------------------------------------
def _gradients(luma):
    gx = np.zeros_like(luma)
    gy = np.zeros_like(luma)
    gx[:, 1:-1] = luma[:, 2:] - luma[:, :-2]
    gy[1:-1, :] = luma[2:, :] - luma[:-2, :]
    return gx, gy


def geometry(rgb):
    luma = _luma(rgb).astype(float)
    h, w = luma.shape
    gx, gy = _gradients(luma)
    mag = np.hypot(gx, gy)

    # horizon likelihood: row with the largest mean horizontal-edge energy
    row_energy = np.abs(gy).mean(1)
    horizon_row = int(np.argmax(row_energy))
    horizon_strength = float(row_energy[horizon_row] / (row_energy.mean() + 1e-6))

    # saliency centroid via gradient magnitude as a cheap saliency proxy
    m = mag / (mag.sum() + 1e-6)
    ys, xs = np.mgrid[0:h, 0:w]
    cx = float((m * xs).sum()) / w
    cy = float((m * ys).sum()) / h

    # rule-of-thirds occupancy: salient energy share in the 9 cells
    thirds = np.zeros((3, 3))
    for i in range(3):
        for j in range(3):
            thirds[i, j] = mag[i * h // 3:(i + 1) * h // 3,
                               j * w // 3:(j + 1) * w // 3].sum()
    thirds = thirds / (thirds.sum() + 1e-6) * 100
    # intersection (power-point) occupancy = mean of the 4 cells touching thirds lines centre
    center_share = float(thirds[1, 1])

    # symmetry: correlation of left half with mirrored right half
    half = w // 2
    left = luma[:, :half]
    right = np.fliplr(luma[:, w - half:])
    sym = float(np.corrcoef(left.ravel(), right.ravel())[0, 1]) if half > 1 else None

    # leading-line orientation summary: histogram of strong-edge angles
    strong = mag > np.percentile(mag, 95)
    ang = (np.degrees(np.arctan2(gy, gx)) % 180)
    if strong.any():
        hist, _ = np.histogram(ang[strong], bins=6, range=(0, 180))
        dom_bin = int(np.argmax(hist))
        dom_angle = dom_bin * 30 + 15
        line_conc = float(hist.max() / (hist.sum() + 1e-6))
    else:
        dom_angle, line_conc = None, None

    return {
        "horizon": {"likely_row_frac": _r(horizon_row / h, 3),
                    "strength_vs_mean": _r(horizon_strength, 2),
                    "method": "row of peak horizontal-edge energy; strength>~3 suggests a real horizon/strong horizontal"},
        "saliency_centroid_frac": {"x": _r(cx, 3), "y": _r(cy, 3),
                                   "method": "gradient-magnitude weighted centroid (proxy saliency)"},
        "rule_of_thirds_grid_pct": [[_r(thirds[i, j], 1) for j in range(3)] for i in range(3)],
        "center_cell_pct": _r(center_share, 1),
        "symmetry_lr_corr": _r(sym, 3),
        "dominant_edge_angle_deg": dom_angle,
        "edge_angle_concentration": _r(line_conc, 3),
    }


# ----------------------------------------------------------------------------
# Stage 1.4 -- coarse segmentation (colour/position HEURISTIC proxies)
# ----------------------------------------------------------------------------
def segmentation(rgb):
    h, w, _ = rgb.shape
    R = rgb[..., 0].astype(float)
    G = rgb[..., 1].astype(float)
    B = rgb[..., 2].astype(float)
    luma = _luma(rgb)
    total = h * w

    ys = np.mgrid[0:h, 0:w][0]
    top_third = ys < h / 3

    sky = ((B > R) & (B > 90) & (luma > 110) & top_third)
    veg = ((G > R + 8) & (G > B + 8))
    water = ((B > R) & (B >= G) & (luma <= 150) & (~top_third))
    # skin: simple normalized-rgb rule
    skin = ((R > 95) & (G > 40) & (B > 20) & (R > G) & (R > B) &
            ((R - np.minimum(G, B)) > 15) & (np.abs(R - G) > 5))
    # rock/ground: low-saturation mid-tone browns/greys not already claimed
    mx = rgb.max(2).astype(float)
    mn = rgb.min(2).astype(float)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0)
    lowsat_mid = (sat < 0.18) & (luma > 40) & (luma < 200)

    claimed = sky | veg | water | skin
    rock_ground = lowsat_mid & (~claimed)

    def pct(mask):
        return _r(float(mask.sum()) / total * 100, 1)

    other = total - (sky | veg | water | skin | rock_ground).sum()
    return {
        "_note": "colour/position heuristics, NOT a trained segmenter; treat as weak priors only",
        "sky_pct": pct(sky),
        "vegetation_pct": pct(veg),
        "water_pct": pct(water),
        "skin_pct": pct(skin),
        "rock_ground_lowsat_pct": pct(rock_ground),
        "unclassified_pct": _r(float(other) / total * 100, 1),
    }


# ----------------------------------------------------------------------------
# Stage 1.5 -- focus & blur
# ----------------------------------------------------------------------------
def _laplacian_var(luma):
    k = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], float)
    lh, lw = luma.shape
    # manual valid convolution via shifts (avoids scipy/cv2 dependency)
    lap = (-4 * luma[1:-1, 1:-1]
           + luma[:-2, 1:-1] + luma[2:, 1:-1]
           + luma[1:-1, :-2] + luma[1:-1, 2:])
    return lap


def focus(rgb):
    luma = _luma(rgb).astype(float)
    lap = _laplacian_var(luma)
    gvar = float(lap.var())

    # local sharpness over a tile grid
    h, w = luma.shape
    gh, gw = 6, 6
    tiles = []
    for i in range(gh):
        for j in range(gw):
            t = lap[i * (h - 2) // gh:(i + 1) * (h - 2) // gh,
                    j * (w - 2) // gw:(j + 1) * (w - 2) // gw]
            if t.size:
                tiles.append(t.var())
    tiles = np.array(tiles)
    sharp_share = float((tiles > gvar).mean()) * 100

    # DOF hint: compare sharpness top band vs bottom band
    band = (h - 2) // 4
    top_v = lap[:band].var()
    bot_v = lap[-band:].var()
    grad = _r((bot_v - top_v) / (bot_v + top_v + 1e-6), 3)

    return {
        "global_sharpness_lapvar": _r(gvar, 1),
        "sharpness_label_proxy": _sharp_label(gvar),
        "tile_sharpness_min": _r(tiles.min(), 1),
        "tile_sharpness_max": _r(tiles.max(), 1),
        "share_tiles_above_global_pct": _r(sharp_share, 1),
        "dof_topbottom_gradient": grad,
        "method": "variance of Laplacian (global + 6x6 tiles). Absolute value scales with resolution/content; compare tiles, not absolutes, across images.",
    }


def _sharp_label(v):
    # rough banding for full-res-ish photos; explicitly a proxy
    if v < 30:
        return "very low (soft/blurred or small image)"
    if v < 120:
        return "low-moderate"
    if v < 500:
        return "moderate-high"
    return "high"


# ----------------------------------------------------------------------------
# Stage 1.6 -- noise & artifacts
# ----------------------------------------------------------------------------
def noise_artifacts(rgb):
    luma = _luma(rgb).astype(float)
    h, w = luma.shape

    # noise: std of high-frequency residual within the flattest tiles
    gh, gw = 8, 8
    flat_stds = []
    for i in range(gh):
        for j in range(gw):
            t = luma[i * h // gh:(i + 1) * h // gh, j * w // gw:(j + 1) * w // gw]
            if t.size < 16:
                continue
            # residual = tile minus its mean-smoothed self (cheap highpass)
            hp = t - t.mean()
            flat_stds.append((t.std(), hp.std()))
    flat_stds.sort(key=lambda x: x[0])
    quiet = [hp for _, hp in flat_stds[:max(1, len(flat_stds) // 4)]]
    noise_sigma = float(np.mean(quiet)) if quiet else None

    # blockiness: discontinuity at 8-px JPEG block boundaries vs in-between
    def boundary_score(arr, axis):
        if axis == 1:
            diffs = np.abs(np.diff(arr, axis=1))
            cols = diffs.shape[1]
            bnd = diffs[:, 7::8].mean() if cols >= 8 else 0
            inner = diffs.mean()
        else:
            diffs = np.abs(np.diff(arr, axis=0))
            rows = diffs.shape[0]
            bnd = diffs[7::8, :].mean() if rows >= 8 else 0
            inner = diffs.mean()
        return bnd / (inner + 1e-6)
    block = _r((boundary_score(luma, 1) + boundary_score(luma, 0)) / 2, 3)

    # chromatic aberration: R-B fringe energy at strong edges
    gx = np.zeros_like(luma)
    gx[:, 1:-1] = luma[:, 2:] - luma[:, :-2]
    edges = np.abs(gx) > np.percentile(np.abs(gx), 97)
    rb = (rgb[..., 0].astype(float) - rgb[..., 2].astype(float))
    ca = float(np.abs(rb)[edges].mean()) if edges.any() else None

    return {
        "luma_noise_sigma_proxy": _r(noise_sigma, 2),
        "noise_label_proxy": _noise_label(noise_sigma),
        "blockiness_8px_ratio": block,
        "blockiness_flag": (block is not None and block > 1.15),
        "chromatic_aberration_edge_rb": _r(ca, 1),
        "method": "noise = highpass std in quietest 25% of tiles; blockiness = 8px-boundary diff / inner diff (>~1.15 hints JPEG blocking); CA = mean |R-B| on strongest 3% vertical edges",
    }


def _noise_label(s):
    if s is None:
        return None
    if s < 2:
        return "very low"
    if s < 5:
        return "low"
    if s < 10:
        return "moderate"
    return "high"


# ----------------------------------------------------------------------------
# Stage 1.7 -- lighting
# ----------------------------------------------------------------------------
def lighting(rgb):
    luma = _luma(rgb).astype(float)
    h, w = luma.shape
    mean_l = float(luma.mean())
    p5 = np.percentile(luma, 5)
    p95 = np.percentile(luma, 95)
    contrast_ratio = _r((p95 + 1) / (p5 + 1), 2)

    if mean_l < 85:
        key = "low-key"
    elif mean_l > 170:
        key = "high-key"
    else:
        key = "normal-key"

    # overall shading direction: gradient of a heavily downsampled luminance
    small = np.array(Image.fromarray(luma.astype(np.uint8)).resize((16, 16)))
    sgx = small[:, 1:].astype(float) - small[:, :-1].astype(float)
    sgy = small[1:, :].astype(float) - small[:-1, :].astype(float)
    az = _r((math.degrees(math.atan2(sgy.mean(), sgx.mean())) % 360), 0)

    # shadow hardness: acutance (edge slope) at darker-side transitions
    gx = luma[:, 1:] - luma[:, :-1]
    acut = float(np.abs(gx).mean())

    # haze: lifted blacks + low local contrast
    haze = (p5 > 40) and (contrast_ratio < 3.0)

    return {
        "scene_key": key,
        "mean_luma": _r(mean_l, 1),
        "contrast_ratio_p95_p5": contrast_ratio,
        "key_light_azimuth_deg_proxy": az,
        "shadow_acutance_proxy": _r(acut, 2),
        "haze_indicator": haze,
        "method": "azimuth from 16x16 luminance-gradient mean (0=light from left); acutance=mean |dL/dx|; haze if blacks lifted (p5>40) and contrast<3",
    }


# ----------------------------------------------------------------------------
# Stage 1.8 -- texture & detail
# ----------------------------------------------------------------------------
def texture(rgb):
    luma = _luma(rgb).astype(float)
    h, w = luma.shape
    lap = _laplacian_var(luma)
    gh, gw = 10, 10
    energies = []
    th = np.percentile(np.abs(lap), 75)
    for i in range(gh):
        for j in range(gw):
            t = lap[i * (h - 2) // gh:(i + 1) * (h - 2) // gh,
                    j * (w - 2) // gw:(j + 1) * (w - 2) // gw]
            if t.size:
                energies.append(float((np.abs(t) > th).mean()))
    energies = np.array(energies)
    detail_cov = float((energies > 0.25).mean()) * 100
    return {
        "fine_detail_coverage_pct": _r(detail_cov, 1),
        "texture_tile_uniformity_sd": _r(energies.std(), 3),
        "method": "share of 10x10 tiles whose high-frequency pixel fraction exceeds 25%; uniformity = sd of tile detail (low sd = even texture)",
    }


# ----------------------------------------------------------------------------
# driver
# ----------------------------------------------------------------------------
def analyze(path):
    im = Image.open(path)
    im.load()
    s0 = stage0(path, im)
    ex = exif(im)

    rgb_im = im.convert("RGB")
    # cap working resolution for speed but keep enough detail
    MAXW = 1400
    if rgb_im.width > MAXW:
        scale = MAXW / rgb_im.width
        work = rgb_im.resize((MAXW, int(rgb_im.height * scale)))
        s0["analysis_resized_to"] = list(work.size)
    else:
        work = rgb_im
    rgb = np.asarray(work)

    return {
        "stage0_ingest": s0,
        "exif": ex,
        "tonal_dr": tonal(rgb),
        "color": color(rgb),
        "geometry": geometry(rgb),
        "segmentation_proxy": segmentation(rgb),
        "focus_blur": focus(rgb),
        "noise_artifacts": noise_artifacts(rgb),
        "lighting": lighting(rgb),
        "texture_detail": texture(rgb),
    }


def print_table(d):
    def line(k, v=""):
        print(f"{k:<34} {v}")
    print("=" * 70)
    print("STAGE 0 -- INGEST & METADATA")
    print("=" * 70)
    for k, v in d["stage0_ingest"].items():
        line(k, v)
    print()
    print("EXIF")
    if d["exif"].get("present"):
        for k, v in d["exif"].items():
            if k != "present":
                line("  " + k, v)
    else:
        line("  exif", "absent")
    print()
    print("=" * 70)
    print("STAGE 1 -- MEASURED EVIDENCE (no interpretation)")
    print("=" * 70)

    print("\n[1.1 TONAL & DYNAMIC RANGE]")
    for ch in ["R", "G", "B", "Luma"]:
        s = d["tonal_dr"][ch]
        line(f"  {ch}", f"mean={s['mean']} med={s['median']} sd={s['sd']} p1={s['p01']} p99={s['p99']}")
    cl = d["tonal_dr"]["clipping"]
    line("  shadow_clip%", cl["shadow_clip_pct"])
    line("  highlight_clip%", cl["highlight_clip_pct"])
    dr = d["tonal_dr"]["dynamic_range"]
    line("  usable_span(0-255)", dr["usable_span_0_255"])
    line("  effective_stops_proxy", dr["effective_stops_proxy"])

    print("\n[1.2 COLOR]")
    for p in d["color"]["palette_kmeans6"]:
        line(f"  {p['hex']}", f"{p['share_pct']}%  rgb={p['rgb']}")
    wb = d["color"]["white_balance"]
    line("  CCT_proxy(K)", wb["cct_kelvin_proxy"])
    line("  tint(g/m)", wb["tint_green_magenta"])
    line("  saturation mean/p95 %", f"{d['color']['saturation']['mean_pct']} / {d['color']['saturation']['p95_pct']}")

    print("\n[1.3 GEOMETRY & LAYOUT]")
    g = d["geometry"]
    line("  horizon row frac", f"{g['horizon']['likely_row_frac']} (strength {g['horizon']['strength_vs_mean']})")
    line("  saliency centroid", f"x={g['saliency_centroid_frac']['x']} y={g['saliency_centroid_frac']['y']}")
    line("  center cell %", g["center_cell_pct"])
    line("  symmetry L-R corr", g["symmetry_lr_corr"])
    line("  dominant edge angle", g["dominant_edge_angle_deg"])

    print("\n[1.4 SEGMENTATION PROXY]")
    for k, v in d["segmentation_proxy"].items():
        if k != "_note":
            line("  " + k, v)

    print("\n[1.5 FOCUS & BLUR]")
    f = d["focus_blur"]
    line("  global sharpness(lapvar)", f"{f['global_sharpness_lapvar']} ({f['sharpness_label_proxy']})")
    line("  tile sharp min/max", f"{f['tile_sharpness_min']} / {f['tile_sharpness_max']}")
    line("  share tiles>global %", f["share_tiles_above_global_pct"])
    line("  DOF top-bottom grad", f["dof_topbottom_gradient"])

    print("\n[1.6 NOISE & ARTIFACTS]")
    n = d["noise_artifacts"]
    line("  noise sigma proxy", f"{n['luma_noise_sigma_proxy']} ({n['noise_label_proxy']})")
    line("  blockiness ratio", f"{n['blockiness_8px_ratio']} (flag={n['blockiness_flag']})")
    line("  CA edge R-B", n["chromatic_aberration_edge_rb"])

    print("\n[1.7 LIGHTING]")
    l = d["lighting"]
    line("  scene key", f"{l['scene_key']} (mean luma {l['mean_luma']})")
    line("  contrast ratio p95/p5", l["contrast_ratio_p95_p5"])
    line("  key azimuth deg", l["key_light_azimuth_deg_proxy"])
    line("  shadow acutance", l["shadow_acutance_proxy"])
    line("  haze indicator", l["haze_indicator"])

    print("\n[1.8 TEXTURE & DETAIL]")
    t = d["texture_detail"]
    line("  fine detail coverage %", t["fine_detail_coverage_pct"])
    line("  texture uniformity sd", t["texture_tile_uniformity_sd"])
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--json", default=None)
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    if not os.path.exists(a.image):
        print("ERROR: file not found:", a.image, file=sys.stderr)
        sys.exit(2)
    d = analyze(a.image)
    if not a.quiet:
        print_table(d)
    if a.json:
        def _ser(o):
            if hasattr(o, "item"):
                return o.item()
            if isinstance(o, (np.bool_,)):
                return bool(o)
            return str(o)
        with open(a.json, "w") as fh:
            json.dump(d, fh, indent=2, default=_ser)
        if not a.quiet:
            print("JSON written ->", a.json)
    return d


if __name__ == "__main__":
    main()
