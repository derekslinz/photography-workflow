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

For any new photos being considered for addition to a commercial-photography site, this skill is **step 1 of 5**:

1. **photo-metadata-helper** (this skill) — generate titles, descriptions, keywords, geo, and embed subject names
2. **quality-review** — technical, editorial, and print-readiness gate
3. **property-release-review** — audit depicted objects (buildings, artwork, branded venues, trademarks)
4. **model-release-review** — audit depicted persons (identifiability, children, workers at workplace)
5. **reviewed-photo-publish** — catalog entry, sales-platform listing, remove from intake queue

Do not skip steps or change the order. Quality review runs before legal review because failing photos shouldn't consume rights-clearance effort. Property review runs before model review because property/trademark concerns are usually dispositive of the sale decision regardless of model release status. Publish is segmented out as its own step so a failed publish never silently blocks a still-clean rights audit.

## Prerequisites

Check that `exiftool` is installed before starting:

```bash
which exiftool && exiftool -ver
```

If missing: `brew install exiftool` (macOS) or `apt install libimage-exiftool-perl` (Linux).

## Step 1 — View All Photos

Before reading any image, downscale it to a maximum of 2048 pixels on the long edge:

```bash
# Requires ImageMagick — check first: which magick || which convert
magick "$FILE" -resize "2048x2048>" "/tmp/preview_$(basename "$FILE")"
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

**The coordinates are the camera position, not the subject's location.** This distinction is mandatory, not pedantic:
- **It only matters when the subject is a significant distance from the vantage.** For the common case — a near or in-scene subject — GPS *is* the subject's location; tag it directly and skip the rest of this block. Engage the vantage reasoning below only once you've judged the subject to be far off (the focal-length heuristic is your first cue).
- The GPS tag records where the photographer stood. It equals the subject's location *only* when the subject is at or near the camera — a flower in the garden you're standing in, a dish on the table in front of you, a building you're beside.
- For any distant subject — a mountain range, a skyline across the water, a coastline, a landmark on the horizon — the resolved location is the **vantage point**, not where the subject is. A peak photographed from ten miles away is not "at" your coordinates; placing it there is geographically impossible (you cannot stand on the summit and photograph it from a distance at the same time).
- Decide per photo whether the subject is *here* (camera location describes it) or *over there* (camera location is only the viewpoint). When it's over there, phrase accordingly: "the Rockies seen from a ridge near Boulder", "the Manhattan skyline viewed from Brooklyn" — never "the Rockies, Boulder" or a keyword that asserts the subject sits at the camera's address.
- When unsure how far the subject is, do not assert a subject location at all — describe what is visible and, at most, attribute the *vantage* ("photographed from …").

**Use lens and camera-direction EXIF to inform the here-vs-there call — but know its limits.** Pull these alongside the coordinates:

```bash
exiftool -p '$FileName | $FocalLength | $FocalLengthIn35mmFormat | $LensModel | $GPSImgDirection $GPSImgDirectionRef | $SubjectDistance' /path/to/dir/*.jpg 2>/dev/null
```

- **Focal length is a strong distance heuristic.** A long focal length (telephoto, say 135mm-equivalent and up) is positive evidence the subject is distant → treat the GPS as a vantage, not the subject's location. A wide focal length means you likely captured the scene you were standing in → GPS plausibly describes the subject.
- **Focal length and lens do NOT give bearing.** They tell you the field of view, not which direction the camera faced. By themselves they cannot place a distant subject.
- **`GPSImgDirection`** (when present) is the compass bearing the camera was pointing. GPS + bearing gives you a *line of sight*; combined with a map you can form a *hypothesis* about which landmark lies along it. This is a hypothesis to corroborate against the visible image — never an identification asserted from EXIF alone. If `GPSImgDirection` is absent, you have no bearing and cannot infer a distant subject's location at all.
- **`SubjectDistance`** is usually missing or pinned to "infinity" beyond a few dozen meters — do not rely on it for distant subjects.
- **Terrain geometry constrains the candidates further.** The topography of the vantage limits what can be in frame: standing on the eastern slope of a range, the ridgeline rises to your west and you're looking out east — the peaks themselves can't be your distant subject, but the valley, foothills, or far range to the east can. Water, a known ridgeline, a coastline, or an obvious occluding landform all rule out whole arcs of the bearing. Use the resolved location plus the visible terrain to discard impossible candidates before settling on one.
- Bottom line: GPS + lens + direction + terrain can *narrow candidates and shape the here-vs-there decision*, but they do not by themselves identify a distant subject. Confirm against what's actually in the frame before naming anything.

If no GPS is present, skip this step and use contextual clues from the images themselves.

## Step 2.5 — Read Capture Date & Time (Ground Truth for Title & Description)

Before generating any metadata, extract the capture timestamp for every photo. This is a **required input to generation**, on equal footing with what you see in the image and the resolved location — not an optional check.

```bash
exiftool -p '$FileName | $DateTimeOriginal' /path/to/dir/*.jpg 2>/dev/null
```

`DateTimeOriginal` is the ground truth for *when* the shot was taken — both the **clock time** (time of day) and the **date** (season). Record both per photo and carry them into Step 3 alongside the visual observations from Step 1 and the location from Step 2. The timestamp governs every time-related claim that may appear in the title or description, on two axes:

- **Time of day** — A photo stamped `12:47` was taken at midday; it cannot be titled or described as blue hour, golden hour, dawn, dusk, sunrise, sunset, or twilight, no matter how the light reads to the eye. Warm or blue light is **not** evidence of the hour: overcast, open shade, artificial light, white balance, and editing all produce it at any time of day.
- **Season** — The *date* grounds any seasonal word (spring, summer, autumn/fall, winter, and their cues like "autumn foliage", "spring bloom", "summer light", "winter snow"). A photo dated in July is not "autumn" because the leaves look warm. Map date → season using the GPS **hemisphere**: latitude from Step 2 tells you which — June–August is summer in the northern hemisphere but winter in the southern. Visible cues (snow, blossoms, bare trees) describe *conditions*, which you may state literally; they do not by themselves license a *season* label that the date contradicts.
- If `DateTimeOriginal` is missing, you have **no** time or date evidence — make no time-of-day or seasonal claim at all; describe only what is literally visible.

The visible image tells you *what* and *how it looks*; the timestamp tells you *when*. Generation in Step 3 must respect all three. The full guard wording lives in Step 3 under the Description rules.

## Step 2.6 — Check Calendar Context (Holidays & Events)

With the location from Step 2 and the date from Step 2.5 both in hand, do a quick check for any holiday or notable event at that place around that date. This often surfaces real context — a market on King's Day, a parade, a festival, a religious observance — that sharpens the description and keywords.

**Holidays (deterministic).** The country comes from Nominatim's `address.country_code` (Step 2); the year from `DateTimeOriginal` (Step 2.5). Query the free, no-auth Nager.Date API (ISO 3166-1 alpha-2, uppercase):

```bash
# COUNTRY = uppercased country_code from Step 2; YEAR from Step 2.5
curl -s "https://date.nager.at/api/v3/PublicHolidays/${YEAR}/${COUNTRY}"
```

Compare the capture date to the returned holiday dates. Treat anything within a few days as *proximate* (festivities often run a window around the official day). Note the match — but see the guard below before it touches metadata.

**Events (non-deterministic).** Local festivals, fairs, sporting events, and concerts have no reliable free lookup. Use well-known recurring events you're confident about (e.g., Carnival in Venice, Oktoberfest in Munich) only when the date and place line up — and always as a hypothesis to confirm against the image, never an assertion from the calendar alone.

**Guard — coincidence is not depiction.** This mirrors the time/season guard:
- A date falling on or near a holiday does **not** mean the photo depicts it. A quiet canal shot taken on King's Day is not "King's Day celebration" unless the image actually shows it (crowds, orange, flags, market stalls).
- Fold a holiday or event into the title/description/keywords **only when the image corroborates it.** Otherwise drop it, or at most include it as soft context phrased as timing ("photographed on King's Day"), never as subject.
- When the API returns nothing, or you have no confident event match, add nothing — silence is correct, invented festivity is not.

## Step 3 — Generate Metadata for Each Photo

For each photo, produce:

**Title** (5–9 words)
- Describes the primary subject and context concisely
- Include location if it meaningfully identifies the image (e.g., "Zebra Longwing Butterfly Wings Open Hortus Botanicus Amsterdam" not "Zebra Longwing Butterfly on a Leaf")
- No articles at the start ("A", "The", "One") — start with the subject
- **Discard any existing IPTC Title / ObjectName / XMP-dc:Title from Lightroom.** Lightroom routinely populates the title field with a truncated description sentence (e.g., "One of Amsterdam's many drawbridges, the Aluminumbrug, spans…"). Treat these as input to ignore, not input to keep. Generate the title fresh from observing the image — never preserve a Lightroom title verbatim. Sentence-shape (commas, articles, > 12 words) is the giveaway.

**Description** (60–90 words)
- Open with the most visually distinctive element
- Weave location naturally into the text — don't tack it on at the end
- Include species names, common names, or proper nouns where known
- Mention photographic technique (macro, bokeh, backlighting) when it's a defining feature
- End with a sentence that adds context or meaning beyond what's visible

**Time guard — time of day AND season (applies to both the title and the description — read before writing any atmospheric or seasonal language):**
- Time-of-day words — *blue hour, golden hour, dawn, dusk, sunrise, sunset, twilight, midday sun, evening light, morning light, night* — and seasonal words — *spring, summer, autumn/fall, winter*, and their cues ("autumn foliage", "spring bloom", "winter snow") — are **factual claims about when the photo was taken**, not mood adjectives. Use one only if it is consistent with the `DateTimeOriginal` clock time and date recorded in Step 2.5 (season also requires the GPS hemisphere — June is summer up north, winter down south).
- If the timestamp says midday and the scene looks moody or warm, describe the *light itself* ("soft diffused light", "warm directional light", "deep shadows"), never the *hour* ("blue hour"). Warm or blue light is not evidence of the time of day — overcast, shade, artificial light, white balance, and editing all produce it at any hour. Likewise, warm foliage or a dusting of snow describes *conditions* you can state literally, but does not license a *season* label the date contradicts.
- No `DateTimeOriginal` → no time-of-day or seasonal phrase at all. Default to describing what is literally visible.
- This is a hard guard: a description that contradicts the timestamp is wrong even if it reads beautifully. When in doubt, drop the time or season reference entirely.

**Keywords** (8–12 tags)
- Mix subject-specific terms (species name, object type) with contextual ones (location, season, technique)
- Include both the common name and scientific name for flora/fauna when known
- Include the resolved venue/location as a keyword when it describes the subject (subject is at the camera position). When the camera location is only the vantage onto a distant subject, tag the vantage as such (e.g., "viewed from Boulder") or omit it — don't assert the subject sits at your coordinates (see Step 2)
- Avoid generic filler like "photo", "image", "picture"

## Step 4 — Write and Execute a Bash Script

Don't run 21 individual exiftool commands interactively. Write a single bash script, then execute it.

**Critical flags:**
- Always use `-overwrite_original` — this prevents exiftool from creating `.jpg_original` backup files
- Clear existing keywords before writing new ones by including `-IPTC:Keywords=` as the first keyword argument in each call — otherwise new keywords are appended to old ones

**Pattern for each photo block:**

Always sync ALL four title fields. `01-extract.ts` / `01b-merge-new.ts` read `Title` (XMP-dc:Title) BEFORE `ObjectName`, so a stale Lightroom title in `Title` will win over the fresh one in `ObjectName` and the catalog gets the truncated description.

```bash
T="Your Title Here"
D="Your 60-90 word description here."
exiftool -overwrite_original -P \
  -IPTC:ObjectName="$T" \
  -Title="$T" \
  -XMP-dc:Title="$T" \
  -IPTC:Headline="$T" \
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
  exiftool -overwrite_original -P \
    -IPTC:ObjectName="$NEW_TITLE" \
    -Title="$NEW_TITLE" \
    -XMP-dc:Title="$NEW_TITLE" \
    -IPTC:Headline="$NEW_TITLE" \
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
| Reading full-res originals directly | Downscale to ≤2048px long edge first with `magick`; read the `/tmp/preview_*` copy |
| `.jpg_original` backup files created | Add `-overwrite_original` to every exiftool call |
| New keywords appended to old ones | Include `-IPTC:Keywords=` (blank) before setting new keywords |
| Misidentified subject (crozier vs caterpillar, etc.) | Review ambiguous shots carefully before writing — when uncertain, describe what you see literally |
| GPS lookup returns neighborhood not venue | Use `zoom=18` in Nominatim URL for maximum specificity |
| Very long filenames from long titles | Keep titles to 5–9 words; prioritize subject over adjectives |
| Description word count outside 60–90 | Count words after drafting; trim or expand before embedding |
| "Blue hour"/"golden hour" on a midday photo, or "autumn" on a July photo | Time-of-day and season are claims about capture date/time — read `DateTimeOriginal` (Step 2.5), map season via GPS hemisphere; describe light/conditions, not the hour or season |
| Calling a photo a "King's Day celebration" because the date matches | Holiday/event proximity (Step 2.6) is context, not depiction — fold in only if the image shows it; otherwise omit or state as timing |
| Distant subject labeled with the camera's GPS location | Coordinates are the vantage point, not where the subject is — a far mountain/skyline isn't "at" your address; phrase as "seen from …" or omit |

## Auditing an Existing Catalog (not just fresh intake)

This skill also covers auditing the metadata of **already-published** products, not only tagging new photos. The same rules apply, but the failure modes are different — the metadata was often generated long ago (sometimes by an LLM or by Lightroom/auto-tagging), so it carries *confident-but-wrong* claims rather than missing data.

**Run the deterministic pass first, then human-verify what the script can't.** A script can ground every time/season claim in `DateTimeOriginal` and catch keyword hygiene catalog-wide in seconds; reserve attention (and the user's eyes) for the proper-noun and subject-identity calls that need an image. The alinzperspective project keeps a reusable example at `scripts/audit-catalog-metadata.ts` (read-only; batch-reads EXIF, flags HARD/SOFT/INFO, and lists every entry that *asserts* a named landmark so a human can verify it).

**Build a labeled contact sheet for landmark/subject review.** When many entries assert specific named places, downscale each, annotate with the *claimed* name + the *GPS-reverse-geocoded* place as a cross-check, and `montage` them into one sheet for the user to scan. The GPS cross-check alone surfaces most mismatches (claimed Keizersgracht, GPS says Amstel).

### Lessons learned (hard-won)

| Lesson | What it means in practice |
|---|---|
| **Catalog text can contain fabricated proper nouns** | A description naming "the Aluminiumbrug on the Nieuw Keizersgracht" may be invented — the *embedded* EXIF caption was generic ("a classic Dutch drawbridge"). Never trust a specific bridge/tower/canal/church name you can't confirm against GPS + the image. Verify or strip it; don't substitute another guess. |
| **Camera GPS is the vantage, not the subject — even in the city** | The GPS may resolve to the bridge you're *standing on* (Hendrick Jacobsz Staetsbrug) while the subject is a different bridge down the river (Walter Suskindbrug). Reverse-geocode to locate yourself, then identify the subject from the frame. |
| **Adjacent landmarks get swapped** | "Mahlertoren" (Zuidas) for the Mondriaantoren (Omval) — towers/bridges near each other are easily confused. GPS + a known cluster (e.g. Rembrandt Tower marks Omval) disambiguates; the same GPS also gave the real foreground location (Park Somerlust). |
| **Sunrise reads as sunset** | A warm "sunset" frame shot at 06:03 in August is *sunrise*. Trust the `DateTimeOriginal` clock over the colour of the light — warm/violet sky happens at both ends of the day. |
| **Use the house season convention consistently** | This project uses **meteorological** seasons (DJF/MAM/JJA/SON, month-based) — September is autumn, full stop, no astronomical-boundary softening. Confirm which convention the project wants and apply it uniformly. |
| **Machine-vision junk accumulates in keywords** | Auto-tagging leaves `Any Vision`, `Labels`, `no person`, `outdoors`, case-variant duplicates (`Reflection`/`reflection`), and contradictory time tags (`dawn`+`dusk`+`night` on one photo). Scrub catalog-wide: drop junk, collapse case dupes, and drop time tags that contradict the verified capture hour. |
| **Figurative / behavioral words are false positives** | "roosts communally **at night**" (behaviour), "cooling toward **night**" (figurative), "symbol of **summer** meadows" (cultural association), "leafless **winter** trees" (a condition) — none are capture-time claims. Don't auto-"fix" them; describe conditions literally instead of forcing a season label. |
| **Stub descriptions & proper-noun misspellings** | Watch for 6-word stub descriptions (vs the 60–90 target) and typos in names (`Rembrantplein`→Rembrandtplein). The title/Dutch/keyword fields sometimes hold the correct spelling while the description doesn't — cross-check the fields against each other. |
| **A filename can disagree with the catalog** | A source named `…-Sunrise-De-Krijtberg-…` under a catalog id `…-sunset-…` is a flag: the time-of-day and/or a named landmark may be wrong. The filename is another evidence source, not gospel — reconcile it against EXIF + image. |
| **Edit catalog JSON without reformatting** | If the file is `JSON.stringify(obj, null, 2)`-shaped, mutate by id and write back with the same call (+ trailing newline) so the diff shows only changed entries. Verify round-trip is byte-identical first. Never change a published entry's `id` (it keys URLs + sales-platform products) — fix only the human-facing fields. |
| **Re-embed fixes into the source JPEG** | Catalog JSON is the live source of truth, but a future re-extract reads the archived original — embed corrected title/caption/keywords (and GPS, if you've learned it) back into the source so the fix is durable. |
