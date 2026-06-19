---
name: quality-review
description: >
  Step 2 of 5 in the photo intake pipeline. Assesses each candidate photo against technical,
  editorial, and print-readiness criteria before the image moves to legal review. Produces a
  PASS / CONDITIONAL PASS / FAIL verdict per image. On FAIL, surfaces specific reasons and
  waits for user instruction — takes no destructive action. Mandatory 2048px downscale before
  the model views any image, plus a deterministic measurement pass (bundled Pillow/numpy
  extractor) that grounds the technical and print-readiness verdicts in real metrics.
  USE WHEN: quality check, quality gate, review photos before publishing,
  are these good enough, editorial review, technical review, print-ready check, assess photos.
  NOT FOR: metadata tagging (use /Photo-Metadata-Helper), rights audits (use
  /property-release-review and /model-release-review), final publishing (use /reviewed-photo-publish).
effort: medium
---

# Quality Review

Step 2 of 5 in the photo intake pipeline. Reviews each photo for technical quality, editorial
merit, and print-readiness before committing time to legal review and publishing.

## Intake Sequence (Step 2 of 5)

1. **Photo-Metadata-Helper** — metadata, naming, subject-name embed
2. **quality-review** (this skill) — technical, editorial, print-readiness gate
3. **property-release-review** — depicted-object audit
4. **model-release-review** — depicted-person audit
5. **reviewed-photo-publish** — catalog entry, Stripe listing, remove from queue

**If a photo fails quality review, do not proceed to steps 3–5 for that photo.** Surface
the failure and wait for user instruction.

## 🚨 MANDATORY FIRST ACTIONS: the visual gate AND the measurement pass

Two things happen before any verdict, and they are deliberately different.

### (a) Visual gate — downscale to 2048px for the model's eyes

Before the model *views* any image, downscale to 2048px on the long edge and view only that
copy. If resize fails, HALT and prompt the user.

```bash
magick "$FILE" -resize "2048x2048>" "/tmp/qr_$(basename "$FILE")"
```

Read the downscaled file from `/tmp/qr_*` using the Read tool — never the full-res original.
Clean up `/tmp/qr_*` after the review is complete.

This stage uses 2048px rather than the pipeline's default 1024px on purpose: a print gate has
to tell "soft" from "tack-sharp," and 1024px is too coarse to judge critical focus or fine
detail. The visual copy is now for composition, subject, and editorial merit — the hard
technical numbers come from the measurement pass below. The cross-cutting
`[[downscale-images-before-processing]]` rule still governs the model's *viewing*; this is a
deliberate per-stage override, not a relaxation of it.

### (b) Measurement pass — run the extractor on the ORIGINAL file

A *script* reading the file is not the *model* reading the file: it computes numbers and prints
a few lines, it never pours megapixels into context. This is exactly why `exiftool` and
`magick` already run on the original here. Run the bundled extractor once per image:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/quality-review/scripts/analyze_image.py" "$FILE" \
  --json "/tmp/qr_$(basename "$FILE").json"
```

(If `${CLAUDE_PLUGIN_ROOT}` isn't set, use this skill's own `scripts/analyze_image.py`.) It
needs only Pillow + numpy. It returns measured **focus** (variance of Laplacian, global +
per-tile), **exposure** (clip %, dynamic-range span), **noise**, **colour cast** (per-channel
means + tint), **true pixel dimensions / aspect ratio**, and **scene key** — the evidence that
grounds the Technical and Print-Readiness verdicts below.

These measurements are deterministic facts, not opinions. Use them as the source of truth for
the technical criterion; reserve the model's eyes for what only eyes can judge (composition,
subject, "does this work"). If the script genuinely can't run, say so and fall back to
visual-only technical judgement, marking those calls *estimated*.

## The Three Criteria

### 1. Technical Quality

| Factor | PASS | CONDITIONAL PASS | FAIL |
|--------|------|-----------------|------|
| **Focus** | Primary subject sharp | Soft but subject identifiable; blur reads as intentional | Primary subject out of focus; unrecoverable |
| **Exposure** | Full tonal range; highlights and shadows retain detail | Mild clipping in non-critical areas | Blown highlights or crushed blacks in subject |
| **Noise** | Clean at expected print sizes | Visible noise; acceptable at smaller sizes only | Noise destroys detail; print unusable |
| **Colour** | Accurate or clearly intentional | Minor cast; correctable in post | Severe uncorrected cast that misrepresents the scene |
| **Artefacts** | None | Mild CA or minor vignetting | Heavy CA, banding, diffraction softness, JPEG blocking |

Intentional creative choices (motion blur, grain film simulation, high contrast B&W) are
not failures — read the image as a whole before flagging.

**Ground each Technical factor in the measurement-pass numbers** (`/tmp/qr_*.json`). The
metrics map onto the table above as follows — let the measured value drive the verdict, and use
your eyes only to decide whether a flagged miss is *intentional*:

| Factor | Measured signal | Read it as |
|--------|-----------------|-----------|
| **Focus** | `focus_blur.global_sharpness_lapvar` + `tile_sharpness_max` / `share_tiles_above_global_pct` + `dof_topbottom_gradient` | A low global value with a *high* tile max = a sharp subject on soft surroundings (shallow DOF → fine, not a FAIL). A low global value with a *low* tile max = nothing is sharp → soft capture. |
| **Exposure** | `tonal_dr.clipping.highlight_clip_pct` / `shadow_clip_pct` + `dynamic_range.usable_span_0_255` | Clipping in the *subject* is the FAIL case; crushed blacks in a deliberately low-key background are not. Judge against the genre profile thresholds (below), not a fixed number. |
| **Noise** | `noise_artifacts.luma_noise_sigma_proxy` (+ `noise_label_proxy`) | Compare to the profile's `noise.warn` / `noise.high`. High ISO grain in documentary work can be intentional — eyes decide. |
| **Colour** | largest `tonal_dr.*.mean` channel difference + `color.white_balance.tint` / `cct_kelvin_proxy` | A cast only fails if it misrepresents the scene *and* the profile penalizes casts (B&W / night / abstract set the penalty to 0). |
| **Artefacts** | `noise_artifacts.blockiness_flag` + `chromatic_aberration_edge_rb` + `stage0.estimated_compression` | Blockiness flag true + low bytes-per-pixel = heavy recompression. High CA on contrasty edges → lens artefact. |

**Use the genre profile for fair thresholds.** Read `references/profiles.json` (an exact
snapshot of the project's 14-genre `PROFILE_CONFIG`). Infer the genre from the image as a
confidence-gated hypothesis; if you can't land it confidently, fall back to
`studio_photography` (strictest). Then judge sharpness / clipping / noise / cast against *that
profile's* numbers, so a low-key night frame isn't failed for the very darkness that defines it.
This keeps the technical verdict auditable: "highlight_clip 6% exceeds landscape warn_pct 8%? no
→ PASS on exposure" beats "looks a bit bright."

### 2. Editorial Merit

| Factor | Questions to ask |
|--------|-----------------|
| **Subject interest** | Is there something worth stopping for? Is there a clear subject? |
| **Composition** | Does the framing serve the subject? Are there distracting elements that can't be cropped away? |
| **Emotional / aesthetic impact** | Rate as **Strong**, **Adequate**, or **Weak** |
| **Catalog differentiation** | Is this too similar to an existing entry in the same series? If so, which is stronger? |

A photo needs at minimum **Adequate** on all four to PASS. **Weak** on two or more = FAIL.

### 3. Print-Readiness

All offered sizes (20×30, 40×60, 60×90 cm) share a **2:3 aspect ratio**. Two checks are
required: resolution and aspect ratio alignment.

#### 3a. Aspect Ratio Check

Use the **true pixel dimensions** — the measurement pass already has them in
`/tmp/qr_*.json` (`stage0_ingest.width_px` / `height_px` / `aspect_ratio` / `megapixels`),
which is the source of truth here because it reads the actual pixel grid, not a possibly-stale
EXIF tag. `exiftool` is a fine cross-check:

```bash
exiftool -ImageWidth -ImageHeight /root/Portraiture/inbox/My-Photo.jpg
```

Compute AR = width ÷ height (landscape) or height ÷ width (portrait — always use the
longer edge in the numerator).

**Tolerance: ±10% of 1.5 → acceptable range 1.364–1.636 (landscape), 0.606–0.733 (portrait).**

Images outside this range require >10% linear crop to fit a 2:3 print — a material loss
of content buyers are not told about. Restrict their sizes accordingly.

For images outside tolerance, compute the **effective long edge** after a 2:3 crop:

| Image AR (L = long, S = short edge) | Effective long edge |
|-------------------------------------|---------------------|
| Landscape, AR > 1.636 (wider than 2:3) | S × 1.5 |
| Portrait, AR < 0.606 (taller than 2:3) | S × 1.5 (where S is the short/narrow edge) |
| Within tolerance 1.364–1.636 | L (no crop penalty) |

Use the effective long edge — not the raw pixel count — in the resolution check below.

#### 3b. Resolution Check (viewing-distance-aware — DPI is NOT fixed)

Required DPI is not constant. Bigger prints are viewed from farther away, so the per-inch
demand drops as the print grows (rule of thumb: required ppi ≈ 3438 ÷ viewing-distance-in-inches).
A flat 240-dpi-everywhere floor rejects large prints for resolution they don't actually need —
a 60×90 cm wall piece seen from 1.5 m does not need the same ppi as an 8×12 held at arm's
length. Check the **effective long edge** against the floor *for that size*:

| Print size | Typical viewing dist | Ideal dpi | Floor dpi | Floor long-edge px | Ideal long-edge px |
|-----------|----------------------|-----------|-----------|--------------------|--------------------|
| 20 × 30 cm (8 × 12 in)  | ~40 cm  | 300 | 240 | 2 835 px | 3 543 px |
| 40 × 60 cm (16 × 24 in) | ~1 m    | 240 | 180 | 4 252 px | 5 670 px |
| 60 × 90 cm (24 × 36 in) | ~1.5 m  | 200 | 150 | 5 315 px | 7 087 px |

A size is **supported** when the effective long edge meets that size's **floor**. At/above the
**ideal** it is comfortably print-sharp; between floor and ideal is acceptable and worth a note
in the listing.

If the effective long edge falls below the smallest size's floor (2 835 px for 20×30), it is a
FAIL. If it clears some sizes but not all, note the maximum supportable size — a CONDITIONAL
PASS with a size restriction the listing must honour. (Note the floors now scale with size: an
8 256 px file clears all three sizes here, where the old flat-240 rule would have capped it at
40×60.)

## Verdicts

| Verdict | Meaning | Next step |
|---------|---------|-----------|
| ✅ **PASS** | Meets all three criteria | Proceed to step 3 (property-release-review) |
| ⚠️ **CONDITIONAL PASS** | Meets minimum bar; noted reservations | Proceed to step 3; carry reservations into listing notes |
| ❌ **FAIL** | Does not meet the bar | Stop; surface reasons; wait for user instruction |

## Workflow

1. **Scope** — list the files under review; note pixel dimensions for each
2. **Downscale & Measure** — `magick` each file to `/tmp/qr_*` at 2048px (HALT on any resize
   failure); and run `scripts/analyze_image.py` on each **original** to `/tmp/qr_*.json` for the
   deterministic technical evidence. Both happen before any verdict.
3. **Duplicate Check** — before assigning any verdict, check for duplicates in two passes:

   **Pass A — byte-identical (within batch):**
   ```bash
   md5sum /tmp/qr_*.jpg | sort | awk 'seen[$1]++ { print "DUPLICATE:", $2 }'
   ```
   If any match: identify primary (earliest timestamp or highest resolution), report clearly,
   delete the duplicate from the batch, and proceed with only unique files.

   **Pass B — semantic near-duplicates (within batch + against published catalog):**
   After viewing the downscaled images in step 4, flag any pair where:
   - Same subject / same scene with near-identical framing (different angle or moment alone is not enough)
   - Same shoot, same prop, same model in essentially the same pose
   - Both images cover the same catalog slot without adding meaningfully different value

   For catalog-sweep reviews, also compare against existing entries by same-series keyword
   overlap + visual similarity.

   **On detection:** HALT and present both candidates to the user with titles, IDs, current
   Stripe/size state, and a one-sentence distinction. Do NOT remove either entry until the user
   explicitly confirms which to drop.

4. **Assess** — for each image, work through the three criteria in order: drive **Technical**
   and **Print-Readiness** from the measured JSON (`/tmp/qr_*.json`) against the genre profile,
   and use the 2048px visual copy for **Editorial** merit and to confirm whether any flagged
   technical miss is intentional rather than a defect
5. **Verdict** — assign PASS / CONDITIONAL PASS / FAIL; write one-line reasons for every
   CONDITIONAL or FAIL criterion
6. **Report** — structured table, one row per photo
7. **Decision** — for FAIL photos, surface options to the user:
   - Delete from inbox
   - Keep in inbox for re-edit / reshoot
   - Move to `/root/Portraiture/rejected/` for later review
8. **Proceed** — PASS and CONDITIONAL PASS photos continue to property-release-review; FAIL photos wait

## Report Format

```
Quality Review — {n} photos

| File | Technical | Editorial | Print-ready | Verdict | Notes |
|------|-----------|-----------|-------------|---------|-------|
| my-photo.jpg | PASS | Strong | 40×60 max | ⚠️ CONDITIONAL | Noise limits to 40×60cm and below |
| another.jpg  | PASS | Adequate | All sizes  | ✅ PASS | — |
| third.jpg    | FAIL | Weak     | All sizes  | ❌ FAIL | Subject out of focus; composition has no clear anchor |
```

For every ❌ FAIL row, follow with a short paragraph explaining the specific issue and what,
if anything, could be done to recover it (crop, resend for re-edit, discard).

## Calibrated Judgment

Do not fail a photo for stylistic choices you personally dislike. The question is whether
the image meets a reasonable commercial fine-art standard — not whether you would have
made the same creative decisions.

When uncertain, lean toward CONDITIONAL PASS with explicit notes rather than FAIL. The
user has the final call on every FAIL.

## Gotchas

- **Duplicate check is mandatory at step 3 — both byte-identical (MD5) and semantic near-duplicates (same shoot, same subject).** Do not assign verdicts until the duplicate scan is complete. Never remove an entry without explicit user confirmation of which to drop.
- **No Stripe changes without explicit permission.** Quality review produces verdicts and recommendations only. Do not archive products, deactivate prices, or modify any Stripe objects — not even as a "logical next step" after a sweep. Wait for the user to confirm before touching Stripe.
- Motion blur is often intentional in travel and documentary work — look at the whole image
  before flagging focus.
- Grain / high ISO noise in a documentary street photo may be a deliberate aesthetic.
- Check composition for both portrait and landscape crop potential — a photo that looks
  tight in one orientation may work in the other.
- Print dimensions are orientation-agnostic (20×30cm works for both 20 wide × 30 tall and
  the reverse) — use the longer pixel dimension vs. the longer print dimension.
- **Aspect ratio matters for resolution.** A wide-panoramic image (AR > 1.636) loses resolution
  when cropped to 2:3 — use the effective long edge (short edge × 1.5), not the raw long edge,
  when checking against the dpi thresholds.
- A photo that cannot support 60×90cm but supports 40×60cm and 20×30cm is a CONDITIONAL
  PASS, not a FAIL — note the maximum size in the listing.

## When to invoke

- "quality review these photos"
- "are these good enough to sell"
- "check the photos before legal review"
- "editorial gate"
- "print-ready check"
- "quality check on the inbox"
- Any photo intake run after Photo-Metadata-Helper completes
