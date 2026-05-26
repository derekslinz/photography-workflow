---
name: property-release-review
description: "Audits a commercial-photography catalog for entries that require property releases, trademark clearance, or copyright analysis on depicted subjects (buildings, interiors, permanent public artwork, branded venues, signage, vehicles). Four-bucket disposition (remove / delist / SOFT-FLAG / OK / EXEMPT). Mandatory 1024px-long-edge downscale before viewing any image. Sibling skill: model-release-review for the persons-in-frame side. USE WHEN property release, image rights, can I sell this print, trademark in catalog, copyright in catalog, freedom-of-panorama question, sculpture in frame, venue in frame, branded building, catalog rights audit. NOT FOR persons / model releases (use model-release-review)."
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

The gate exists because description-only judgments (carry-over notes, captions, IPTC metadata, prior-session classifications) lie. Pixels don't.

## Intake Sequence (Step 2 of 3)

For new-photo intake, this skill is **step 2 of 3** in the pipeline:

1. **Photo-Metadata-Helper** — metadata, naming, subject-name embed
2. **property-release-review** (this skill) — depicted-object audit
3. **model-release-review** — depicted-person audit

This skill runs before model-release-review because property/trademark concerns are usually dispositive of the sale decision regardless of model release status.

For audit-only passes on an already-published catalog, this skill can be invoked standalone.

## The Question

For each non-exempt catalog entry: **is there anything in the depicted scene (building, interior, sculpture, mural, trademarked livery, signage, vehicle, named venue) that requires a property/trademark/copyright release before commercial sale?**

## Jurisdictional Note — Freedom of Panorama (FOP)

FOP rules vary by country. The framework below is conservative enough to work in most jurisdictions but you must confirm the rule that applies to **the country where you intend to sell**, not just where the photo was taken.

Selected examples (verify before relying on these):
- **Netherlands (Auteurswet Art. 18):** broad commercial FOP for works *permanently installed in public space* — outdoor sculpture, mural, architecture.
- **Germany (§59 UrhG, Panoramafreiheit):** similar but only from public ways; interior FOP narrower.
- **France:** very restrictive — limited to non-commercial reproductions of works permanently in public space; architects' rights persist.
- **USA:** architecture covered by AWCPA (limited); sculpture/visual art generally NOT covered.

**Permanence is the universal test.** Temporary installations, traveling exhibitions, indoor museum pieces almost never qualify regardless of jurisdiction. When in doubt, treat as flagged.

## Trademark vs Copyright

| Concern | Type | Typical disposition |
|---------|------|---------------------|
| Branded logos / signage on buildings | Trademark | Delist from sale, keep as portfolio if desired |
| Distinctive corporate livery (vehicles, trains) | Trademark | Delist |
| Permanent outdoor sculpture, mural | Copyright + FOP | Often OK where FOP applies; verify |
| Temporary or indoor artwork | Copyright | Flag / remove |
| Building exteriors (vernacular architecture) | Generally clear | Usually OK |
| Interiors of paid-entry venues | Property right | Flag / remove |
| Installation art (mixed-media, mannequins, etc.) | Copyright | Flag / remove |

## What Is and Isn't Sensitive Metadata

For audits that include metadata scrub steps:

**Sensitive (consider scrubbing from filename, IPTC Keywords/Subject/Caption/Location/Sublocation):**
- Paid-entry named venue identifiers (specific museums, named gardens with admission, ticketed festival names tied to depicted installations)
- Specific artist/installation names where those names invite a takedown letter

**NOT sensitive (keep as-is):**
- Cities, neighborhoods, districts, towns
- GPS coordinates
- Artist, Copyright, DateTimeOriginal, Make, Model EXIF fields — these are the photographer's provenance, not sensitive metadata; **never strip them**

## Buckets

| Bucket | Action | When |
|--------|--------|------|
| **Bucket 1** | Remove entirely (catalog + sales platform + file + originals archived) | Copyright flag with no FOP defense (installation art, indoor museum, temporary work) |
| **Bucket 2** | Delist from sales platform; keep in gallery/portfolio | Trademark-only concern (branded livery, signage) |
| **SOFT-FLAG** | Surface to user — judgment call | Ambiguous; reasonable people could disagree |
| **OK** | Keep on sale | Cleared under FOP or no rights issue |
| **EXEMPT** | Skip entirely | Categories the catalog owner has declared exempt (e.g. macro, abstract, in-studio) |

## Remediation Pipeline (Adapt to Your Catalog)

The exact commands depend on your catalog architecture. The shape of the pipeline is universal:

**Bucket 1 (full removal):**
1. Remove entry from your catalog source-of-truth
2. Regenerate any derived lists (products, gallery, sitemap)
3. Move the published image file to an archive directory
4. Move the original from your source archive to the same archive directory
5. Archive the product on your sales platform (e.g. Stripe `products.update(id, {active: false})` — archive each child price too)

**Bucket 2 (delist, keep in gallery):**
1. Edit catalog entry to remove sale info (e.g. clear `sizes[]` while retaining the sales-platform product ID for history)
2. Regenerate derived lists — the generator should exclude entries with no sale info from "for sale" but keep them in "gallery"
3. Archive the product on the sales platform

**Example generator-filter pattern** (your code may differ):

```ts
const forSale = entries.filter(e => e.salesPlatformProductId && e.sizes && e.sizes.length > 0);
const gallery = entries; // everything, sold or not
```

**Originals archive:** move (don't delete) so the decision is reversible. Recommend `<archive root>/property-release-removed/` or similar.

## Calibrated Debate, Not Capitulation

When the user challenges a flag:
1. Re-apply the 1024-gate (downscale + view actual pixels)
2. State the strongest counter-argument honestly
3. Test against FOP / trademark / copyright frameworks
4. Concede when dispositive; name residual risk when not

Examples of the kind of moves that should be conceded after debate:
- Mural is permanent (installed deliberately by property owner) → FOP applies → OK
- Sculpture by an artist the photographer personally knows AND the sculpture is permanently installed → FOP plus relational context → likely OK
- Branded venue but logo is incidental and minimal → may reduce trademark risk → consider SOFT-FLAG instead of HARD-FLAG

Examples that should stand even under debate:
- Temporary light installation, no FOP defense → maintain flag
- Installation art with no permanence → maintain flag

## Distinction from `model-release-review`

See sibling skill for the persons-in-frame side. When a photo trips both:
- Resolve property side first — trademark/permanent-artwork concerns are usually dispositive of the sale decision
- A model-release OK doesn't restore a photo already off-sale for property reasons (and vice versa)

## Workflow

1. **Scope** — read the catalog, separate exempt category(ies) from non-exempt
2. **Triage by description / IPTC** — flag obvious candidates (named venues, named installations, branded livery)
3. **Visual verification (1024-gate MANDATORY)** — downscale every candidate, view, classify
4. **Spot-check** — pick ≥2 "OK by description" entries, downscale + view, confirm
5. **Structured report** — bucket-by-bucket; one-line reason for every flag
6. **Surface decisions** — present buckets; let the catalog owner assign final disposition
7. **Execute remediation** — per the pipeline; ALWAYS dry-run any live sales-platform mutation before executing it

## Gotchas

- **Live sales-platform keys are destructive** — always dry-run before live runs and visually verify the impact list.
- **Order matters** — archive on the sales platform AFTER catalog regeneration; otherwise the live site briefly shows a product with no sellable price.
- **Don't delete originals** — move to an archive directory. Restoration may be needed.
- **EXIF Artist/Copyright/Make/Model are NEVER stripped** — those are the photographer's provenance.
- **Exempt category is owner-defined** — confirm at audit start which entries are out of scope (e.g. macro, abstract, studio). The skill does not assume; the owner declares.

## When to invoke

- "review the catalog for property releases"
- "image rights audit"
- "can I sell this print"
- "is this image safe to sell"
- "copyright review on the catalog"
- "FOP question on [photo]"
- Adding new images to a catalog from venues / festivals with potential property/copyright concerns
