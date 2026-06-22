---
name: reviewed-photo-publish
description: "Step 5 of 5 in the photo intake pipeline. Takes a photo that has cleared metadata, quality, property, and model review and pushes it live — writes the catalog entry, creates the sales-platform product and child prices (one per supported print size), regenerates derived lists (for-sale, gallery, sitemap), moves the file from intake to the published location, and archives the original. Mandatory dry-run before any live sales-platform mutation. Mandatory 2048px-long-edge downscale for any pre-flight visual verification. USE WHEN: publish photo, list this print, push to sales, add to catalog, go live, finalize listing, complete the intake pipeline. NOT FOR: metadata tagging (use photo-metadata-helper), quality gating (use quality-review), rights audits (use property-release-review / model-release-review), or unpublishing a live entry (that's the remediation pipeline in property-release-review)."
effort: medium
---

# Publish

Step 5 of 5 in the photo intake pipeline. Turns a cleared photo into a live, sellable catalog entry — atomically across catalog source-of-truth, sales platform, derived lists, and file system. Refuses to publish anything that hasn't been stamped by every upstream step.

## Intake Sequence (Step 5 of 5)

1. **photo-metadata-helper** — metadata, naming, subject-name embed
2. **quality-review** — technical, editorial, and print-readiness gate
3. **property-release-review** — depicted-object audit
4. **model-release-review** — depicted-person audit
5. **publish** (this skill) — catalog entry, sales-platform listing, intake-queue cleanup

Publish is the only step in the pipeline that mutates external state (sales platform, live site, archive). It is deliberately segmented so that an upstream FAIL never silently triggers a publish, and a failed publish never silently corrupts an upstream verdict.

## 🚨 MANDATORY: Explicit Sign-Off Before Any Live Mutation

**Every publish run requires explicit, per-photo user sign-off before any live sales-platform mutation, file move, or queue removal. No exceptions. No shortcuts. No batch-implicit approvals.**

The skill ALWAYS runs in this order:
1. Pre-flight verify the photo and its upstream verdicts
2. Print the full dry-run preview (what will be created in Stripe, what files will move where, what the queue change will be)
3. **STOP and ask the user to confirm this specific photo, in writing, in the current turn.** A prior approval, a session-level "go ahead," a `--yes` flag, or a "yes do all of them" message earlier in the session is NOT sign-off for the next photo.
4. Only after the user replies with an affirmative for *this* photo does any live mutation run.

Acceptable affirmations: "yes publish", "confirmed", "go", "ship it" — paired with enough specificity that there is no doubt which photo is being approved. If the user's reply is ambiguous, ask again. Never infer approval from silence, from "ok", or from a thumbs-up to a different photo.

This rule exists because Stripe mutations are visible to customers within seconds and file moves are not transactionally tied to the catalog write — a partial publish without explicit sign-off is the worst-case outcome of this pipeline.

## 🚨 MANDATORY FIRST ACTION: Downscale Every Image to 2048px Long Edge

**Before reading any image for pre-flight verification, downscale to 2048px on the long edge. Process only the downscaled copy. If resize fails, HALT and prompt the user.**

```bash
magick "$FILE" -resize "2048x2048>" "/tmp/pub_$(basename "$FILE")"
```

Publish does not classify images — it acts on verdicts already in place — but any pre-flight visual check (confirming the file opens, confirming dimensions match the chosen print sizes, confirming the right photo is being published) still goes through the gate. The gate is load-bearing across the whole pipeline; see `[[downscale-gate-load-bearing]]` for why.

Clean up `/tmp/pub_*` after publish completes.

## The Question

For each candidate photo: **has every upstream step cleared it, and what does "going live" mean for this photo specifically (which sizes, sale or portfolio-only, which derived lists)?**

A photo is publishable only if every upstream verdict on file is one of:

| Step | Acceptable verdict |
|------|--------------------|
| photo-metadata-helper | IPTC `ObjectName`, `Caption-Abstract`, `Keywords` present; `PersonInImage` present for any identifiable subject |
| quality-review | PASS, or CONDITIONAL PASS with a noted size restriction |
| property-release-review | OK, EXEMPT, or Bucket 2 (portfolio-only — publish to gallery but NOT to sale) |
| model-release-review | OK, EXEMPT, or HARD-FLAG with release confirmed on file |

**Anything else is a refuse-to-publish.** Bucket 1 (remove entirely) and FAIL never reach this step in a clean run, but the skill double-checks anyway because intake state can drift.

## Inputs the skill needs

Every publish run requires:

1. **The cleared photo(s)** — file path(s) in the intake location
2. **Catalog source-of-truth path** — JSON/YAML/SQLite file the user maintains; the skill never assumes
3. **Sales platform credentials and target mode** — confirmed dry-run or live; never assume live
4. **Supported print sizes for this photo** — from quality-review verdict (PASS = all sizes; CONDITIONAL PASS = the subset that meets the dpi floor)
5. **Disposition** — for-sale (default) or portfolio-only (Bucket 2 from property-release-review)

If any of these is missing or ambiguous, the skill asks before doing anything.

## Workflow

1. **Pre-flight verification**
   - Read upstream verdicts (from intake report, sidecar JSON, IPTC, or wherever the pipeline records them)
   - Confirm every step has an acceptable verdict per the table above
   - For any identifiable person, confirm `PersonInImage` is embedded and the model release is on file
   - 2048-gate spot-check the image opens and matches the expected subject
   - HALT and surface if anything is missing — do not infer, do not default

2. **Resolve print sizes**
   - For PASS: all configured sizes
   - For CONDITIONAL PASS: only sizes at or below the noted maximum
   - For portfolio-only: empty `sizes[]` — no sale prices created

3. **Dry-run preview + explicit per-photo sign-off**
   - Print the catalog entry that will be written (id, title, description, keywords, sizes, sales-platform IDs that will be created)
   - Print the sales-platform mutations that will run (product create, price creates per size)
   - Print the file moves that will happen (intake → published, original → archive)
   - Print the derived-list regenerations that will be triggered
   - **STOP and ask the user to confirm THIS specific photo before any live mutation.** See the "Explicit Sign-Off" rule at the top of this skill. A session-level "yes" or batch-level approval is not sufficient — every photo gets its own affirmative in the turn that publishes it.

4. **Set price tier (before catalog merge)**

   Every new photo needs a `priceTier` before the ladder script runs. Tiers auto-assign for
   unpriced entries based on quality signals (printspace-manual → platinum; panoramas/portraits → gold;
   full D850/Z9 native ≥8000px → gold; everything else → silver). To override, set `priceTier`
   explicitly in the catalog entry or pass it as metadata before step 5.

   Tier multipliers over the 4.8× base:
   | Tier | Multiplier | 20×30 | 40×60 | 60×90 |
   |---|---|---|---|---|
   | silver | 1.0× | €135 | €230 | €365 |
   | gold | 1.25× | €170 | €290 | €455 |
   | platinum | 1.50× | €205 | €345 | €550 |

5. **Write catalog entry + assign size ladder**

   Copy photo to `/root/uploaded/` then run the pipeline scripts in order:

   ```bash
   # 1. Additive merge — NEVER run 01-extract.ts (destroys Stripe IDs)
   bun scripts/catalog/01b-merge-new.ts

   # 2. Classify into series (up-close / travel / documentary / portraits / panoramas / boudoir)
   bun scripts/catalog/02-classify.ts

   # 3. Copy to public/images/<series>/  (copies the FULL-RES original)
   bun scripts/catalog/03-copy-images.ts

   # 3b. Downscale published files to 2400px + archive originals, THEN
   #     pre-generate responsive WebP derivatives + manifest for the image loader.
   #     Required: 03 copies full-res; this is what makes the served files small
   #     and produces the WebP the site actually serves (lib/imageLoader.ts).
   bun scripts/catalog/06-optimize-and-archive.ts

   # 4. Assign size ladders + apply price tier multipliers
   #    Auto-tier fires here for new entries without an explicit priceTier
   bun scripts/catalog/03b-assign-ladders.ts
   ```

   The manifest (`lib/image-derivatives.json`) is committed; `.webp` files are gitignored
   (regenerated on the box). New images serve their 2400px jpg until the next `npm run deploy`
   bundles the updated manifest — see step 9.

   For portfolio-only photos: set `sizes: []` in catalog.json before running 03b, or add the
   entry id to the `PORTFOLIO_ONLY` set in `03b-assign-ladders.ts`.

6. **Create Stripe products and prices (skip for portfolio-only)**

   ```bash
   # Dry-run first — confirms product/price counts, logs WOULD CREATE lines
   bun scripts/catalog/04-stripe-sync.ts --dry-run

   # Live run after confirmation
   bun scripts/catalog/04-stripe-sync.ts --live
   ```

   The sync is idempotent (lookup_key–based). Prices are immutable in Stripe — repricing an existing
   entry requires creating a new price (with `transfer_lookup_key`) and archiving the old one; the
   sync script does not do this automatically.

7. **Derived lists** — no regeneration step needed. `lib/products.ts` and `lib/gallery.ts` read
   `data/catalog.json` at request time. The new entry is live as soon as catalog.json is saved.

8. **Verify**
   - Catalog entry readable from `data/catalog.json`
   - Stripe product visible with all child prices (or absent for portfolio-only)
   - File accessible at `public/images/<series>/<id>.jpg`
   - Intake queue entry status updated in `data/uploads.json`

9. **Rebuild and push GMC feed**

   After every publish run (regardless of batch size), rebuild the Google Merchant Center feed and push live:

   ```bash
   # Dry-run first to confirm product count looks right
   bun scripts/gmc-sync.ts --dry-run
   # Then push live
   bun scripts/gmc-sync.ts
   ```

   The GMC feed is push-only (`gmc-sync.ts` is the sole write path — pull feeds are disabled). A publish run that skips the GMC push leaves the feed stale for up to 24 hours. Push immediately after every batch.

   `gmc-sync.ts` self-heals the feed's additional product images before building: it runs `scripts/catalog/generate-gmc-mockups.ts` (idempotent — existing files skip), which renders each new entry's wall mockups (framed/canvas/paper, type-matched) and full-res detail crop into `public/images/gmc-extra/`. These feed `additionalImageLinks` per offer (GMC store-quality "add more images"). No separate step needed; if the run warns that the generator was skipped (repo lock busy, exit 75), re-run `bun scripts/gmc-sync.ts` after the competing image op finishes so new entries get their extra images.

10. **Surface result**
    - One-line summary per photo: id, title, sizes, sales-platform product ID, disposition
    - GMC push result: entries inserted/updated, countries synced
    - Any non-fatal anomalies flagged for follow-up

## Ordering Rules

Order is not negotiable:

1. Catalog write **before** sales-platform create — so the entry exists to record the returned IDs
2. Sales-platform create **before** derived-list regeneration — so the for-sale list picks up the new product on first regeneration
3. Derived-list regeneration **before** file move — so the live site is not pointing at a path that doesn't exist yet
4. File move **before** intake-queue removal — so a failed move doesn't lose the photo
5. GMC push **after** file move — so all published images are accessible at their final URLs before Google indexes them

A failure at any step HALTs the run and surfaces the partial state. The skill never auto-rolls-back — partial publishes are presented to the user with a recovery plan.

## No Concession on Sign-Off

When the user pushes to skip the dry-run, batch-approve, or proceed on a session-level "yes":
1. Refuse politely and explicitly. The sign-off rule is not negotiable inside this skill.
2. Restate the rule: every photo requires its own explicit affirmation in the current turn before any live mutation.
3. Offer to streamline the *presentation* (e.g. a tighter dry-run summary format) rather than the *approval mechanic*.

This is the one place in the pipeline where calibrated debate does not apply — the cost of a wrong publish is customer-visible within seconds and is not cleanly reversible.

## Safety Rules

- **Live sales-platform credentials are destructive** — never run without an explicit per-photo sign-off in the current turn. Dry-run by default. See the Sign-Off rule at the top.
- **No partial product creation** — if any size's price create fails, archive the product immediately and surface the failure. Do not leave a product live with a subset of prices.
- **Originals are moved, never deleted** — archive directory is the safety net for any later un-publish.
- **EXIF Artist / Copyright / Make / Model are NEVER stripped** — those are the photographer's provenance. Carry them into the published file unchanged.
- **Never re-publish a photo that has a Bucket-1 history without explicit user re-approval** — once removed for property reasons, restoration requires the user to confirm the underlying concern was resolved.

## Gotchas

- The user's catalog source-of-truth, sales platform, and derived-list generator are project-specific — the skill asks at run time, never assumes.
- CONDITIONAL PASS size restrictions from quality-review are *binding* — do not create sales-platform prices for any size the photo failed on quality-review's viewing-distance-aware resolution ladder (each size has its own dpi floor — 240/180/150 for 20×30 / 40×60 / 60×90 — not a flat 240).
- Portfolio-only (Bucket 2) photos go to the gallery list but get no sales-platform product. The catalog entry retains an empty `sizes[]` and no `salesPlatformProductId`.
- A photo that ships with a model-release HARD-FLAG cleared by an on-file release should record the release ID in the catalog entry — so future audits can verify provenance without re-asking.
- If the publish run is interrupted between catalog write and sales-platform create, the next run sees a catalog entry with no product ID — treat that as a resumable state, not a duplicate.
- Currency, tax behavior, and shipping zones are sales-platform config, not publish concerns. Publish creates the product and prices; everything else is the user's platform setup.

## When to invoke

- "publish this photo"
- "list this print"
- "push to sales"
- "add to the catalog"
- "go live with these"
- "finalize the intake pipeline"
- After model-release-review clears a photo and the user wants to ship it
