---
name: photo-metadata-helper
description: >
  Workflow for processing JPEG photos: view each image, generate a descriptive title (5–9 words),
  60–90 word description, and 8–12 keywords; reverse-geocode any embedded GPS coordinates via
  Nominatim to add specific location detail; embed all metadata as IPTC fields using exiftool
  (without creating backup files); and rename each file to a hyphenated version of its title.
  USE when the user says things like: "tag these photos", "add metadata to my images", "generate
  keywords for photos", "embed IPTC data", "rename photos with descriptive names", "process these
  JPEGs", "add titles and descriptions to my photos", "geolocate my photos", or any request
  involving generating and embedding photo metadata at scale. Trigger even if only one of
  these steps is mentioned — the full workflow adds value every time.
---

# Photo Metadata Tagger

End-to-end workflow for generating rich IPTC metadata for a folder of JPEGs and renaming them.

## Intake Sequence (FIRST step of the pipeline)

For any new photos being considered for addition to a commercial-photography site, this skill is **step 1 of 3**:

1. **Photo-Metadata-Helper** (this skill) — generate titles, descriptions, keywords, geo, and embed subject names
2. **property-release-review** — audit depicted objects (buildings, artwork, branded venues, trademarks)
3. **model-release-review** — audit depicted persons (identifiability, children, workers at workplace)

Do not skip steps or change the order. Property review goes before model review because property concerns are usually dispositive of the sale decision regardless of model release status.

## Prerequisites

Check that `exiftool` is installed before starting:

```bash
which exiftool && exiftool -ver
```

If missing: `brew install exiftool` (macOS) or `apt install libimage-exiftool-perl` (Linux).

## Step 1 — View All Photos

Before reading any image, downscale it to a maximum of 1024 pixels on the long edge:

```bash
# Requires ImageMagick — check first: which magick || which convert
magick "$FILE" -resize "1024x1024>" "/tmp/preview_$(basename "$FILE")"
```

**If the resize command fails** (ImageMagick not installed, unsupported format, permission error, etc.), stop immediately and ask the user how to proceed — do not fall back to reading the original full-sized file. Use `AskUserQuestion` with the specific error and options such as installing ImageMagick, skipping the affected file, or aborting the batch.

Read the downscaled file from `/tmp/` using the Read tool, not the original. This keeps vision payloads small and avoids read failures on large RAW or high-res files. Work in parallel batches of 6–8 at a time. For each photo, mentally note:

- **Subject**: What is the main subject? (person, species, object, scene)
- **Context**: Indoor/outdoor, setting clues, event type
- **Mood/style**: macro, portrait, landscape, abstract, documentary
- **Distinctive details**: colors, behaviors, poses, unique features

Don't generate metadata yet — just observe. For large sets (20+ photos) a quick first-pass scan before writing helps catch misidentifications early (a fern crozier is not a caterpillar; a Bird of Paradise flower looks alien up close).

## Step 2 — Reverse Geocode GPS (if present)

Extract GPS from all files in one command:

```bash
exiftool -p '$FileName | $GPSLatitude $GPSLatitudeRef | $GPSLongitude $GPSLongitudeRef' /path/to/dir/*.jpg 2>/dev/null
```

If GPS is present, convert DMS to decimal and query Nominatim. Group photos by GPS cluster (photos taken at the same venue will cluster tightly — one lookup per cluster is enough):

```bash
curl -s "https://nominatim.openstreetmap.org/reverse?format=json&lat=LAT&lon=LON&zoom=18&addressdetails=1" \
  -H "User-Agent: photo-metadata-tagger/1.0"
```

Parse the `display_name` and `address` fields for the specific venue, street, neighborhood, and city. Use the most specific available name (e.g., "Hortus Botanicus Amsterdam, Drie-klimaten-kas" rather than just "Amsterdam"). This location context goes into titles, descriptions, and keywords.

If no GPS is present, skip this step and use contextual clues from the images themselves.

## Step 3 — Generate Metadata for Each Photo

For each photo, produce:

**Title** (5–9 words)
- Describes the primary subject and context concisely
- Include location if it meaningfully identifies the image (e.g., "Zebra Longwing Butterfly Wings Open Hortus Botanicus Amsterdam" not "Zebra Longwing Butterfly on a Leaf")
- No articles at the start ("A", "The") — start with the subject

**Description** (60–90 words)
- Open with the most visually distinctive element
- Weave location naturally into the text — don't tack it on at the end
- Include species names, common names, or proper nouns where known
- Mention photographic technique (macro, bokeh, backlighting) when it's a defining feature
- End with a sentence that adds context or meaning beyond what's visible

**Keywords** (8–12 tags)
- Mix subject-specific terms (species name, object type) with contextual ones (location, season, technique)
- Include both the common name and scientific name for flora/fauna when known
- Always include the venue/location name as a keyword if GPS was resolved
- Avoid generic filler like "photo", "image", "picture"

## Step 4 — Write and Execute a Bash Script

Don't run 21 individual exiftool commands interactively. Write a single bash script, then execute it.

**Critical flags:**
- Always use `-overwrite_original` — this prevents exiftool from creating `.jpg_original` backup files
- Clear existing keywords before writing new ones by including `-IPTC:Keywords=` as the first keyword argument in each call — otherwise new keywords are appended to old ones

**Pattern for each photo block:**

```bash
T="Your Title Here"
D="Your 60-90 word description here."
exiftool -overwrite_original \
  -IPTC:ObjectName="$T" \
  -IPTC:Caption-Abstract="$D" \
  -IPTC:Keywords= \
  -IPTC:Keywords="keyword1" \
  -IPTC:Keywords="keyword2" \
  -IPTC:Keywords="keyword3" \
  "/path/to/Original-Filename.jpg"
mv "/path/to/Original-Filename.jpg" "/path/to/${T// /-}.jpg"
```

The `${T// /-}` bash substitution replaces all spaces with hyphens for the filename.

**Script structure tip**: Use a helper function to keep the script DRY:

```bash
tag_and_rename() {
  local OLD_FILE="$1" NEW_TITLE="$2" DESC="$3"
  shift 3
  local KW_ARGS=()
  for kw in "$@"; do KW_ARGS+=(-IPTC:Keywords="$kw"); done
  exiftool -overwrite_original \
    -IPTC:ObjectName="$NEW_TITLE" \
    -IPTC:Caption-Abstract="$DESC" \
    -IPTC:Keywords= \
    "${KW_ARGS[@]}" \
    "$OLD_FILE"
  mv "$OLD_FILE" "${OLD_FILE%/*}/${NEW_TITLE// /-}.jpg"
}
```

## Step 4.5 — Embed Subject Names (PersonInImage)

If any image contains an identifiable person, embed the subject's full name into the photo's metadata. This is the IPTC Extension standard for naming people in an image; downstream tools, model-release audits, and image asset managers read it.

Use the IPTC4xmpExt PersonInImage tag — written as `XMP-iptcExt:PersonInImage` in exiftool — plus an IPTC keyword for searchability:

```bash
exiftool -overwrite_original -P \
  -XMP-iptcExt:PersonInImage="Subject Full Name" \
  -IPTC:Keywords+="Subject Full Name" \
  /path/to/photo.jpg
```

**Critical rules:**
- Use the subject's full legal name (matches their model release on file).
- One PersonInImage per subject. For group shots, run the command once per name — exiftool stacks the values.
- `-P` preserves file modification time. `-overwrite_original` prevents `.jpg_original` backups.
- `IPTC:Keywords+=` (note the `+=`) appends; bare `=` would overwrite existing keywords.
- Embed BOTH on the source original (in your archive dir) AND the published/web copy. Otherwise the next pipeline rebuild loses the name from the published copy.

**When to embed:** every time a person is identifiable. Skip macros, architecture-only frames, distant unidentifiable figures, and silhouettes.

**Verify:**

```bash
exiftool -G -s -PersonInImage -Keywords /path/to/photo.jpg
```

Output should show `[XMP] PersonInImage : <Name>` and `<Name>` listed in `[IPTC] Keywords`.

## Step 5 — Verify

After the script runs:

```bash
# Check new filenames, no backups, correct count
ls /path/to/dir/*.jpg | grep -v Plans
ls /path/to/dir/ | grep "_original" | wc -l   # should be 0

# Spot-check metadata on 1-2 files
exiftool -IPTC:ObjectName -IPTC:Caption-Abstract -IPTC:Keywords /path/to/file.jpg
```

Confirm the title, description word count, and keyword list all look correct. Clean up `/tmp/preview_*` files after verification.

## Common Pitfalls

| Pitfall | Fix |
|---|---|
| Reading full-res originals directly | Downscale to ≤1024px long edge first with `magick`; read the `/tmp/preview_*` copy |
| `.jpg_original` backup files created | Add `-overwrite_original` to every exiftool call |
| New keywords appended to old ones | Include `-IPTC:Keywords=` (blank) before setting new keywords |
| Misidentified subject (crozier vs caterpillar, etc.) | Review ambiguous shots carefully before writing — when uncertain, describe what you see literally |
| GPS lookup returns neighborhood not venue | Use `zoom=18` in Nominatim URL for maximum specificity |
| Very long filenames from long titles | Keep titles to 5–9 words; prioritize subject over adjectives |
| Description word count outside 60–90 | Count words after drafting; trim or expand before embedding |
