---
name: localization-audit-review
description: >
  Step 5 of 6 in the photo intake pipeline. Audits all Dutch-facing customer content for a
  cleared photo against the durable Netherlands Dutch localization rules — register, terminology,
  capitalization, fine-art vocabulary, shipping/returns/legal phrasing, species names,
  geographic/time/event claims, translation completeness, and English leakage. Produces a
  PASS / CONDITIONAL PASS / FAIL verdict. On FAIL, surfaces specific violations and waits for
  user instruction. Mandatory 2048px downscale before any image read. USE WHEN: Dutch QA,
  localization audit, nl review, Dutch copy check, Netherlands Dutch validation. NOT FOR: metadata
  tagging (use photo-metadata-helper), quality gating (use quality-review), rights audits (use
  property-release-review / model-release-review), final publishing (use reviewed-photo-publish).
effort: medium
---

# Localization Audit Review

Step 5 of 6 in the photo intake pipeline. Reviews all Dutch-facing customer content (product
titles/descriptions, UI strings, category/series associations, FAQ, mockup alt text) for a photo
that has cleared metadata, quality, property, and model review. Ensures every /nl/ field is
natural, idiomatic Netherlands Dutch — not translated English — before the photo reaches the
publish step.

## Intake Sequence (Step 5 of 6)

1. **photo-metadata-helper** — metadata, naming, subject-name embed
2. **quality-review** — technical, editorial, and print-readiness gate
3. **property-release-review** — depicted-object audit
4. **model-release-review** — depicted-person audit
5. **localization-audit-review** (this skill) — Dutch customer-facing content QA
6. **reviewed-photo-publish** — catalog entry, sales-platform listing, intake-queue cleanup

**If a photo fails localization audit, do not proceed to step 6 for that photo.** Surface the
failure and wait for user instruction.

## 🚨 MANDATORY FIRST ACTION: Downscale Every Image to 2048px Long Edge

**Before reading any image for visual verification during localization audit, downscale to 2048px
on the long edge. Process only the downscaled copy. If resize fails, HALT and prompt the user.**

```bash
magick "$FILE" -resize "2048x2048>" "/tmp/l10n_$(basename "$FILE")"
```

The audit reads Dutch copy, not pixels — but the visual gate is load-bearing across the whole
pipeline. Clean up `/tmp/l10n_*` after audit completes.

## Inputs Required

For each photo under audit, the skill needs:

1. **The photo file** — path in the intake location (for 2048-gate visual context)
2. **All Dutch-facing content for this photo** — from the catalog entry / intake metadata:
   - `titleNl` (Dutch product title)
   - `descriptionNl` (Dutch product description)
   - Series/category assignment (gallery series slug → localized series title/description)
   - Size ladder labels in Dutch (framed/canvas/paper, mount options)
   - Mockup alt text / captions for /nl/ gallery and PDP
   - Any FAQ or informational copy associated with the photo
3. **Source metadata** — EXIF DateTimeOriginal, GPS, camera, dimensions (for factual guards)

If any Dutch field is missing, empty, or identical to the English field (without explicit
"unchanged" marking), flag it per the completeness rule.

## The Audit Criteria

Apply the **Dutch Localization Rules — Future-Proofing Guide** (Linz Perspective · Netherlands
Dutch · Generation & QA) as the deterministic standard. Every criterion below maps to a
specific rule section in that guide.

### 1. Register & Pronouns (Rule 1)

| Check | PASS | FAIL |
|-------|------|------|
| **je/jouw/jou** used consistently in all customer-facing NL copy | ✅ | ❌ |
| **u/uw/U** absent unless legally required or quoting external text | ✅ | ❌ |
| Applies across: navigation, product PDP, checkout, newsletter, cookie consent, transactional UI, marketing copy | ✅ | ❌ |

### 2. Idiomatic Dutch Terminology (Rule 2)

| English concept | Preferred NL | Flag if found |
|----------------|--------------|---------------|
| Frame (product type) | **ingelijste print** / **baklijst** | frame, box frame, lijst (alone) |
| Canvas print | **canvasprint** | Canvas Print, canvas-print |
| Fine art paper print | **fine-artprint op papier** | Fine Art Print, Fine-art print |
| Frame style | **lijststijl** | frame style |
| Box frame | **baklijst** | boxlijst, box frame |
| Classic frame | **klassieke lijst** | classic frame |
| Finish | **afwerking** | finish |
| Shopping cart | **winkelwagen** | cart, shopping cart, mandje (inconsistent) |

Maintain the controlled Dutch ecommerce terminology dictionary. Flag unpreferred alternatives.

### 3. Dutch Capitalization (Rule 3)

| Check | PASS | FAIL |
|-------|------|------|
| Normal Dutch sentence capitalization (only first word + proper nouns) | ✅ | ❌ |
| No English title case (e.g. "Ingelijste Print", "Canvasprint Op Papier") | ✅ | ❌ |
| Proper nouns capitalized (Amsterdam, Dryas iulia, Prodigi, Stripe) | ✅ | ❌ |

### 4. Fine-Art Terminology (Rule 4)

| Concept | Canonical NL | Flag if found |
|---------|--------------|---------------|
| Fine art print (general) | **fine-artprint** | fine art print, Fine Art Print |
| Fine art paper | **fine-artprint op papier** | fine art paper, Fine Art Paper |
| Canvas print | **canvasprint** | Canvas Print, canvas print |
| Box frame | **baklijst** | box frame, boxlijst |
| Framed print | **ingelijste print** | framed print, ingelijste print (lowercase OK in sentence) |
| Passe-partout | **passe-partout** | passe partout, mat |
| Print (noun) | **print** | artwork (when print is meant) |
| Finish | **afwerking** | finish, coating |

Keep established industry terminology rather than forcing artificial Dutch equivalents.

### 5. Shipping & Returns (Rule 5)

| Concept | Preferred NL | Flag if found |
|---------|--------------|---------------|
| Free shipping worldwide | **Gratis verzending wereldwijd** | Gratis Wereldwijd, Gratis verzending wereldwijd (title case) |
| 14-day return period | **14 dagen retourneren** / **Retourtermijn van 14 dagen** | 14 Dagen Retour, 14 dagen retour |
| Return policy | **Retourbeleid** | return policy, Return Policy |
| Statutory withdrawal period | **bedenktijd** (only when specifically describing the statutory period) | bedenktijd used loosely for any return window |

Terminology must accurately reflect the actual policy (76 countries free shipping, 14-day
withdrawal under EU consumer law Art. 16(c)).

### 6. Legal / Privacy Terminology (Rule 6)

| Check | PASS | FAIL |
|-------|------|------|
| **AVG** used in ordinary Dutch-facing UI (not GDPR) | ✅ | ❌ |
| Expanded to **Algemene Verordening Gegevensbescherming** when useful | ✅ | — |
| **EU** kept as EU | ✅ | ❌ |
| GDPR flagged unless explicitly required by a legal reference | ✅ | ❌ |

### 7. Species & Common Names (Rule 7)

| Check | PASS | FAIL |
|-------|------|------|
| Established Dutch common names used (e.g. **Juliavlinders** for Julia heliconians) | ✅ | ❌ |
| No mechanical translation of English species names | ✅ | ❌ |
| Scientific name retained separately where useful: **Juliavlinder (Dryas iulia)** | ✅ | ❌ |

### 8. Domain-Specific Terminology (Rule 8)

Validate against established Dutch usage:
- Photography terms (diepte van veld, sluitertijd, diafragma, belichting)
- Meteorological (lichtende nachtwolken for noctilucent clouds — not literal "lichtende nachten")
- Astronomical, botanical, zoological, architectural terms
- Flag terms that don't match established Dutch domain vocabulary

### 9. Idiomatic Translation (Rule 9)

| Check | PASS | FAIL |
|-------|------|------|
| Meaning and tone preserved, not English sentence structure | ✅ | ❌ |
| Rewritten naturally in Netherlands Dutch | ✅ | ❌ |
| Example: "de wereld onthuld op een schaal waar we normaal gesproken aan voorbijgaan" (not literal translation of "the world revealed at a scale we normally pass by") | ✅ | ❌ |

### 10. Avoid Semantic Shifts (Rule 10)

| English | Correct NL (context-dependent) | Flag if found |
|---------|-------------------------------|---------------|
| editorial | **redactioneel** | editorial |
| journal | **artikel** / **blogartikel** / **blog** | journal |
| frame | **lijst** or **baklijst** (per product type) | frame |

Translate according to meaning and context, not dictionary equivalence.

### 11. Avoid English Stylistic Artifacts (Rule 11)

Flag: unnecessary repetition, English rhetorical constructions, English title capitalization,
literal idioms, unnatural noun stacking, excessive formality. Treat as soft QA unless it
affects naturalness or meaning.

### 12. Bilingual Asset Metadata (Rule 12)

| Check | PASS | FAIL |
|-------|------|------|
| Bilingual EXIF/IPTC keyword strategy preserved (English + Dutch keywords may coexist) | ✅ | ❌ |
| Common + scientific species names may coexist in metadata | ✅ | ❌ |
| Asset metadata distinguished from Dutch customer-facing page localization | ✅ | ❌ |

### 13. Filenames (Rule 13)

| Check | PASS | FAIL |
|-------|------|------|
| Canonical filename strategy preserved | ✅ | ❌ |
| No separate Dutch image assets created merely for localization | ✅ | ❌ |
| English canonical filenames coexist with Dutch page content + bilingual IPTC | ✅ | ❌ |

### 14. Location Names (Rule 14)

| Check | PASS | FAIL |
|-------|------|------|
| Correct Dutch/local proper names (Amsterdam, Scheveningen, De Pier, het Kurhaus, Damrak, Noordzee) | ✅ | ❌ |
| No automatic translations of place names | ✅ | ❌ |

### 15. Geographic Claims (Rule 15)

| Check | PASS | FAIL |
|-------|------|------|
| Subject location distinguished from camera/vantage location | ✅ | ❌ |
| GPS = photographer's position, not automatically subject location | ✅ | ❌ |
| Location as subject metadata only when supported by the image | ✅ | ❌ |
| Otherwise describe the vantage | ✅ | ❌ |

### 16. Time & Seasonal Claims (Rule 16)

| Check | PASS | FAIL |
|-------|------|------|
| Blue hour, golden hour, dawn, dusk, sunrise, sunset, summer, winter, etc. agree with DateTimeOriginal and hemisphere | ✅ | ❌ |
| If DateTimeOriginal unavailable, no invented time-of-day/seasonal claims | ✅ | ❌ |

### 17. Events & Holidays (Rule 17)

| Check | PASS | FAIL |
|-------|------|------|
| Calendar coincidence not turned into photographic subject matter | ✅ | ❌ |
| Event/holiday context only when image corroborates it | ✅ | ❌ |

### 18. Translation Completeness (Rule 18)

| Check | PASS | FAIL |
|-------|------|------|
| Every /nl/ product has Dutch title, description, customer-facing metadata, UI strings, FAQ, category/series association | ✅ | ❌ |
| Intentional bilingual asset metadata is the only exception | ✅ | ❌ |
| Dutch title/description identical to English → flagged unless explicitly marked unchanged | ✅ | ❌ |

### 19. English Leakage Detection (Rule 19)

Run automated lint over Dutch customer-facing output. At minimum flag known unlocalized strings:
- Print Type, box frame, Canvas Print, GDPR, Julia heliconians
- Fine Art Print, Frame Style, Box Frame, Shopping Cart
- Return Policy, Shipping Policy, Terms of Service

Use a controlled prohibited/unpreferred phrase list. Do not reject every English word.

### 20. Consistency (Rule 20)

| Check | PASS | FAIL |
|-------|------|------|
| One canonical Dutch term per concept throughout the site | ✅ | ❌ |
| No alternation between baklijst / boxlijst / box frame for same product type | ✅ | ❌ |
| Canonical terminology map maintained in generation layer | ✅ | ❌ |

## Deterministic QA Checklist (per the Guide)

Every audit run must verify all of the following:

- [ ] **je/jouw register** (Rule 1)
- [ ] **AVG terminology** (Rule 6)
- [ ] **Winkelwagen terminology** (Rule 2)
- [ ] **baklijst terminology** (Rule 2, 4)
- [ ] **fine-artprint terminology** (Rule 4)
- [ ] **Dutch capitalization** (Rule 3)
- [ ] **Known English leakage** (Rule 19)
- [ ] **Complete Dutch fields** (Rule 18)
- [ ] **Canonical terminology consistency** (Rule 20)
- [ ] **Factual, time, and geographic guards** (Rules 15, 16, 17)

## Verdicts

| Verdict | Meaning | Next Step |
|---------|---------|-----------|
| ✅ **PASS** | All QA checks pass; Dutch content is natural, complete, consistent, and factually grounded | Proceed to step 6 (reviewed-photo-publish) |
| ⚠️ **CONDITIONAL PASS** | Minor reservations (soft stylistic polish, one non-critical terminology variance) — noted for follow-up | Proceed to step 6; carry notes into listing |
| ❌ **FAIL** | One or more hard violations (missing Dutch fields, u/uw register, GDPR leakage, wrong terminology, factual claim mismatch, English title case) | Stop; surface specific violations; wait for user instruction |

**FAIL triggers:** any Rule 1 (register), Rule 6 (AVG/GDPR), Rule 18 (missing Dutch fields identical to English), Rule 15/16/17 (factual mismatch), or Rule 19 (uncontrolled English leakage on prohibited terms).

**CONDITIONAL PASS triggers:** Rule 11 (stylistic artifacts), single Rule 2/4 variance with correct meaning, Rule 3 capitalization on non-heading text.

## Workflow

1. **Scope** — list the photos under audit; for each, collect all Dutch-facing fields from the intake metadata / catalog entry
2. **Downscale** — `magick` each file to `/tmp/l10n_*` at 2048px (HALT on any resize failure)
3. **Automated lint pass** — run the controlled English-leakage phrase list against all Dutch copy; emit violations with file/field/location
4. **Manual review** — for each photo, work through the 20 rules above against the collected Dutch content; use the 2048px visual copy for subject/geography/time context
5. **Verdict** — assign PASS / CONDITIONAL PASS / FAIL; write specific reasons for every CONDITIONAL or FAIL (rule number + field + observed vs expected)
6. **Report** — per-photo table with rule-by-rule status
7. **Decision** — for FAIL photos, surface options:
   - Fix Dutch copy now (re-run audit)
   - Keep in intake for re-edit
   - Move to `/root/intake/_rejected/` for later review
8. **Proceed** — PASS and CONDITIONAL PASS photos continue to reviewed-photo-publish; FAIL photos wait

## Report Format

```
Localization Audit — {n} photos

| File | Register | Terminology | Capitalization | Fine-art | Shipping | Legal | Species | Domain | Idiomatic | Semantic | Style | Metadata | Filename | Location | Geography | Time | Events | Complete | Leakage | Consistency | Verdict | Notes |
|------|:--------:|:-----------:|:--------------:|:--------:|:--------:|:-----:|:-------:|:------:|:---------:|:--------:|:-----:|:--------:|:--------:|:--------:|:---------:|:----:|:------:|:--------:|:-------:|:-----------:|:-------:|-------|
| my-photo.jpg     | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ | ✅ | ⚠️ CONDITIONAL | "winkelwagen" vs "mandje" inconsistency in cart UI |
| another.jpg      | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ PASS | all checks clean |
| third.jpg        | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ FAIL | u/uw in checkout copy; GDPR in privacy link; titleNl == title (EN) |
```

Each ✅/❌/⚠️ is a specific rule check. The Notes column names the exact violation(s).

## Calibrated Judgment

- Do not fail for subjective stylistic preferences — the standard is **natural, idiomatic
  Netherlands Dutch**, not a specific translator's voice.
- When uncertain between CONDITIONAL PASS and FAIL on a soft rule (Rule 11, single Rule 2
  variance), lean toward CONDITIONAL PASS with explicit notes.
- Hard rules (1, 6, 15, 16, 17, 18, 19 prohibited terms) are non-negotiable — FAIL on violation.
- The user has the final call on every FAIL.

## Gotchas

- **The per-rule checklist table is mandatory on every run — even for a single photo.**
  Score all 20 rules per photo and derive the verdict from the results. Never collapse the
  per-rule columns into a single cell, and never emit a verdict without the table.
- **No publish without audit.** This skill is the final content gate before reviewed-photo-publish.
  A photo that bypasses this step (e.g. manual catalog edit) must be re-audited before any
  subsequent GMC push or site deploy.
- **Series/category localization matters.** The gallery series title/description in Dutch
  (`lib/series.ts` or `data/series.json`) must also pass the audit for the series this photo
  belongs to. If the series-level Dutch copy hasn't been audited, flag it here.
- **Mockup alt text is customer-facing.** The `mockups[].alt` (or equivalent) for /nl/ gallery
  and PDP must be audited — it's not asset metadata, it's page content.
- **Size ladder labels in Dutch.** The product's `sizes[].label` (or equivalent) for framed,
  canvas, paper, mount options must use canonical terminology (ingelijste print, canvasprint,
  fine-artprint op papier, baklijst, klassieke lijst, passe-partout, afwerking).
- **Intake metadata vs. catalog entry.** The audit runs against the Dutch fields that will be
  written to catalog.json — if the intake metadata helper produced `titleNl`/`descriptionNl`,
  audit those. If they'll be generated at publish time, audit the generator's output in dry-run.

## When to invoke

- "localization audit these photos"
- "Dutch QA on the intake batch"
- "check nl copy before publish"
- "review Dutch localization"
- "Netherlands Dutch validation"
- After model-release-review clears a photo and before reviewed-photo-publish
- Any photo intake run after model-release-review completes