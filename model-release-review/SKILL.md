---
name: model-release-review
description: "Audits a commercial-photography catalog for entries that require a signed model release. Four-tier classification (HARD-FLAG / SOFT-FLAG / OK / EXEMPT) keyed to identifiability-to-the-general-public, not facial recognition alone. Stricter bar for children (parental release) and workers at workplaces. Mandatory 1024px-long-edge downscale before viewing any image — pixels falsify description-only assumptions every time. Pairs with property-release-review for the rights side of the same catalog. USE WHEN model release review, person release, can I sell this print, identifiable person audit, candid model audit, child in catalog, worker in catalog, portrait release audit. NOT FOR property/architecture/artwork rights (use property-release-review)."
effort: medium
---

## 🚨 MANDATORY FIRST ACTION: Downscale Every Image to 1024px Long Edge

**Before reading or classifying ANY image, downscale to 1024px on the long edge. Process only the downscaled copy. If resize fails, HALT and prompt the user.**

```typescript
import sharp from "sharp";
await sharp(srcPath)
  .resize({ width: 1024, height: 1024, fit: "inside", withoutEnlargement: true })
  .jpeg({ quality: 82, mozjpeg: true })
  .toFile(outPath);
```

`magick "$FILE" -resize "1024x1024>" "$OUT"` is an acceptable ImageMagick fallback.

Output location: a scratch dir scoped to the active audit (e.g. `<workdir>/downscaled/`). Originals are never modified. If any resize fails, stop and ask — do NOT skip and continue.

This rule exists because description-only judgments (carry-over notes from prior sessions, captions, IPTC metadata) lie. Pixels don't. The gate has demonstrably caught description-only HARD-FLAGs that the actual frame falsified — back-turned subjects mislabeled as frontal, glass-distorted faces mislabeled as identifiable.

## Intake Sequence (Step 3 of 3)

For new-photo intake, this skill is **step 3 of 3** in the pipeline:

1. **Photo-Metadata-Helper** — metadata, naming, subject-name embed
2. **property-release-review** — depicted-object audit
3. **model-release-review** (this skill) — depicted-person audit

If property review flagged a photo as Bucket 1 (remove entirely), skip model review for that photo — the property concern is already dispositive.

For audit-only passes on an already-published catalog, this skill can be invoked standalone.

## The Question

For each non-exempt catalog entry: **does the image require a signed model release before commercial sale?**

Answer = HARD-FLAG (yes) / SOFT-FLAG (judgment call) / OK (no) / EXEMPT (skipped per catalog owner's declaration).

## Identifiability Standard

**The legal bar is identifiable to the general public, NOT identifiable to close friends.** Personality / privacy rights protect against being recognized by the public from the image alone.

This is the most common over-flagging mistake: assuming a four-attribute "fingerprint" (coat + bag + hair + hat) of generic items in a public place makes someone identifiable. It almost never does — the bar is what a stranger could match against social media or someone's general appearance.

| Factor | Pushes toward HARD-FLAG | Pushes toward OK |
|--------|------------------------|------------------|
| Face | Visible, in focus, frontal or 3/4 | Back-turned, silhouette, deep shadow, glass distortion |
| Distance | Subject occupies significant frame | Small/distant figure, not the subject |
| Subject vs incidental | Person is what the photo is about | Person is compositional element only |
| Clothing | Branded, uniformed, singular | Generic, mass-retail |
| Body / posture | Distinctive (tattoos, gait, public-known build) | Generic |
| Setting | Workplace (worker depicted at work) | Public space, anonymous context |

**Strict cases — always HARD-FLAG even with face partially obscured:**
- **Children** — parental release required regardless of identifiability nuance
- **Workers at workplace** — cook at food stall, driver in cab (when face IS visible — glass distortion is dispositive otherwise), performer on stage. Selling prints of someone doing their job is a stricter standard than editorial use.

**Permissive cases — usually OK even though a person is in frame:**
- Pure back-turn + generic clothing + public space (archetypal/anonymous framing)
- Heavy glass distortion or reflection over the face
- Silhouettes against strong backlight
- Crowd shots where no individual is the subject
- Distance great enough that features cannot be discerned at print scale

## Tiers

| Tier | Action | Trigger |
|------|--------|---------|
| 🟥 **HARD-FLAG** | Release required before sale | Identifiable face/features, person is subject; OR child; OR worker at workplace |
| 🟧 **SOFT-FLAG** | Judgment call — surface to user | Framing/distance ambiguous; reasonable people could disagree |
| 🟩 **OK** | No release needed | Unidentifiable per the table above |
| 🚫 **EXEMPT** | Skip entirely | Categories the catalog owner has declared exempt (e.g. macro, abstract, in-studio) |

## Portraits — Audit, Not New Ask

Posed/commissioned portraits are HARD-FLAG by series convention, but a working photographer typically already has releases on file. Treat the portraits pass as **audit-confirmation** (list them so the owner can verify the signed release exists for each subject), not as a flag for new acquisition.

## Calibrated Debate, Not Capitulation

When the user challenges a flag, debate it honestly:
1. Re-apply the 1024-gate (downscale + view the actual pixels)
2. State the strongest counter-argument you can find
3. Test it against the identifiability standard
4. Concede when the argument is dispositive; name residual risk when not

The downscale gate exists because pixels routinely falsify carry-over notes — view first, opine second.

## Workflow

1. **Scope** — read the catalog, count entries, separate exempt category(ies) from non-exempt
2. **Preliminary classification from descriptions/series** — portraits HARD-FLAG (audit), architecture-only OK by default, anything with humans → needs visual
3. **Visual verification (1024-gate MANDATORY)** — downscale every non-OK candidate, view, classify
4. **Spot-check** — pick ≥2 OK-by-description entries, downscale + view, confirm
5. **Structured report** — HARD-FLAG / SOFT-FLAG / OK / EXEMPT tiers; every HARD/SOFT has one-line reason; OK count tallied by exclusion
6. **Surface decision points** — dispositions per HARD-FLAG (release file lookup, delist, or remove); flag any portraits where release status is uncertain

## Dispositions (mirror of `property-release-review`)

| Bucket | Action | When |
|--------|--------|------|
| **Bucket 1** | Remove entirely | Release impossible AND image too risky to keep even unsold |
| **Bucket 2** | Delist from sales platform; keep in portfolio | Release impossible but image acceptable as portfolio |
| **Bucket 3** | Keep on sale, release confirmed on file | Release exists, audit-confirmed |

Implementation depends on your catalog architecture — see `property-release-review` for the generic remediation pipeline.

Originals of removed photos go to an archive dir, not deletion. Restoration must remain possible.

## Distinction from `property-release-review`

| Concern | This skill | Sibling |
|---------|-----------|---------|
| Faces / persons | ✓ | — |
| Buildings / interiors | — | ✓ |
| Permanent artwork (sculpture, murals) | — | ✓ |
| Branded venues, trademarks | — | ✓ |
| Child protection | ✓ | — |
| Worker-at-workplace | ✓ (model release) | partial (where branded uniform / workplace property) |
| Freedom-of-Panorama analysis | — | ✓ |
| Owner-declared exempt category | ✓ | ✓ |
| 1024-gate | ✓ | ✓ |
| Debate-don't-capitulate | ✓ | ✓ |

When a photo trips both — escalate via the sibling skill first (property) since trademark/permanent-artwork concerns are usually dispositive of the sale decision regardless of model release.

## Lessons Encoded From Live Reviews

- **Pixels falsify descriptions.** Description-only HARD-FLAGs routinely break under inspection — back-turned subjects misremembered as frontal, glass-distorted faces misremembered as visible. The downscale gate exists because of these failure modes.
- **Glass distortion is dispositive.** Heavy slanted/reflective glass over a face = OK, not HARD-FLAG, even if the person is a worker at workplace.
- **Back-turn + generic clothing + public space = OK.** Even with a four-attribute "fingerprint" (coat, bag, hat, hair), the public-identifiability bar is rarely met.
- **A model-release OK doesn't restore a photo already off-sale for property/trademark reasons.** The two reviews are independent; resolve property first.

## Gotchas

- Do not enumerate the exempt category in the report — it's EXEMPT en bloc.
- Do not flag based on description alone — always downscale + view first.
- Do not auto-bucket HARD-FLAGs — present to the catalog owner and let them decide.
- Children require parental release; "child looks happy / parents nearby" is not a substitute.
- Worker-at-workplace HARD-FLAG persists even if the worker is part of a brand the photo glorifies — selling prints of someone doing their job is not editorial.

## When to invoke

- "review the catalog for model releases"
- "do I need a release for [photo]"
- "model release audit"
- "can I sell this print" (person in frame)
- "person release", "candid release"
- "review portraits for release on file"
- Adding catalog entries that contain people other than commissioned subjects
