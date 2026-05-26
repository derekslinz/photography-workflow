---
description: Run the full five-step photography-workflow intake pipeline on a directory of new photos — metadata, quality, property, model, then explicit-sign-off publish.
argument-hint: <input-directory>
---

# /photo-intake

You are running the photography-workflow plugin's full intake pipeline on the directory the user has provided: **$ARGUMENTS**.

This command is the single entry point to the five skills in this plugin. Drive every step in order; never skip; never reorder; never collapse step 5 into anything else.

## The pipeline

For every photo in the input directory, walk through the five steps below in order. The skills are namespaced under `photography-workflow:` — invoke each one's workflow as documented in its `SKILL.md`. If you're unsure of any skill's exact rules, re-read its `SKILL.md` before acting.

1. **`photography-workflow:photo-metadata-helper`** — generate IPTC title / description / keywords / `PersonInImage` and rename each file. Confirm the 1024-gate ran before any image read.
2. **`photography-workflow:quality-review`** — assess technical / editorial / print-readiness. Stop the run for any photo that comes back **FAIL**; surface reasons; wait for user instruction. **PASS** and **CONDITIONAL PASS** continue.
3. **`photography-workflow:property-release-review`** — audit depicted objects (buildings, sculpture, mural, branded venue, trademark). **Bucket 1** photos drop out of the pipeline entirely. **Bucket 2** photos carry forward marked portfolio-only (no sale at step 5). **OK / EXEMPT** continue normally.
4. **`photography-workflow:model-release-review`** — audit depicted persons. **HARD-FLAG** without an on-file release drops out (or stalls until the release is produced). **OK / EXEMPT** continue.
5. **`photography-workflow:reviewed-photo-publish`** — Stripe product + sized prices, derived-list regeneration, file moves, intake-queue cleanup. **Mandatory per-photo explicit sign-off in the current turn before any live mutation.** No batch approvals, no session-level yeses, no shortcuts. See the sign-off block at the top of that skill — it is load-bearing.

## Rules that apply to every step

- **1024-gate.** Before reading or classifying any image, downscale to 1024px on the long edge and view only the downscaled copy. If resize fails, HALT and ask. This rule is duplicated in every skill on purpose — treat it as load-bearing safety code, not boilerplate.
- **Calibrated debate, not capitulation.** When the user pushes back on a flag, re-apply the 1024-gate, state the strongest counter-argument honestly, test it against the relevant standard, and concede only when dispositive.
- **Short-circuit on upstream failure.** A FAIL at step 2, Bucket 1 at step 3, or unresolved HARD-FLAG at step 4 means that photo does NOT proceed to subsequent steps. Surface the stop and wait for instruction.
- **Sign-off is non-negotiable.** Step 5's per-photo sign-off rule is the one place in the pipeline where calibrated debate does NOT apply. Refuse batch approvals politely; restate the rule; offer to streamline presentation only.

## How to begin

1. Confirm the input directory exists and list the photos under review.
2. Surface the planned scope (file count, exempt category if declared, anything ambiguous).
3. Ask the user to confirm scope before starting step 1.
4. Run the pipeline.
5. Produce a final summary: per-photo verdict at each step, dispositions, and what was published vs held vs dropped.

If the user invoked this command without a directory argument, ask for one before doing anything else.
