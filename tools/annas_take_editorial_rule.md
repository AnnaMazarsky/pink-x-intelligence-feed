# Anna's Take: mandatory editorial rule

Approved by Anna on September 28, 2026. Applies to future Pink X Weekly
Intelligence website briefings. This replaces the generic three-story summary
inside the existing `intelligence_brief` cube, not the rest of the page.

## Reader promise

Give a founder one sharper way to understand capital and one concrete decision,
question or action she can use in her raise. The take must add something that
reading the individual headlines would not provide.

## Required editorial move

- Start with one original, evidence-backed insight, tension or useful distinction.
- Connect relevant signals instead of summarizing the stories again.
- Explain how the connection changes investor research, fundraising positioning,
  milestone planning, capital-source selection or understanding of the ecosystem.
- End with one usable exercise, decision rule, question or action for this week.
- Use the heading `ANNA'S TAKE`, one specific headline, concise prose and
  `Your move this week`. Aim for roughly 150-220 words, not a three-column recap.
- Write in English in Anna's direct, intelligent voice. First-person editorial
  judgment is allowed; fabricated personal experience or private knowledge is not.
- Preserve inline evidence links for factual claims. Clearly distinguish sourced
  observations from Anna's interpretation and practical recommendation.

## Evidence and time windows

- Review the previous four published pulses for relevant connections. Expand to
  the previous quarter only when that helps answer a specific question.
- Historical stories may inform a new synthesis, with their original dates and
  run references recorded. Do not present them as fresh news or repeat them in
  headline slots.
- This is an authorized synthesis layer, not an extra news slot. References to
  current or historical approved stories are allowed here for a genuinely new
  interpretation. Existing news-item freshness and dedup rules remain unchanged.
- A curated set of stories is not a representative market dataset. Do not infer
  an acceleration, increase, causation or market-wide trend from selected stories
  alone. Trend claims require comparable measures, periods and denominators.
- When there is no supported macro pattern, use a sharp insight from the current
  pulse. Never manufacture a trend to fill the box.
- Recheck the underlying source before using a specific factual detail not
  supported by the retained evidence.

## Reject these outputs

- A recap of the same three headlines shown below.
- Source-quality disclaimers or production notes as the main reader benefit.
- Generic advice that could be pasted into any week's pulse unchanged.
- Dry totals with no decision-relevant meaning.
- Unsupported assertions about why investors invested.
- Automatic optimism, fabricated certainty, or implying women in senior roles
  automatically improve access to funding for women founders.

## Feed contract

Supply `intelligence_brief` with:

```json
{
  "format": "annas_take",
  "headline": "One specific, useful insight.",
  "read": "Brief factual bridge between the relevant evidence.",
  "paragraphs": [
    "Anna's interpretation and why it changes the reader's understanding.",
    "A concrete consequence for the fundraising process."
  ],
  "action": "One exercise or decision the reader can apply.",
  "sources": [{"label": "Descriptive source name", "url": "https://..."}],
  "lanes": []
}
```

`lanes` is retained only for compatibility with older renderers/SEO consumers.
If populated, use a short compatibility version of the same take, not a second
editorial or a repeated news summary. The `annas_take` renderer ignores lanes.

## Blocking review before publishing

1. What will the reader understand differently?
2. What specific evidence supports the connection?
3. Which statement is interpretation rather than established fact?
4. What can the reader actually do with it?
5. Could this exact text fit an unrelated week? If yes, rewrite.
6. Does it repeat the news cards? If yes, synthesize instead.
7. Does the rendered cube show Anna's Take, full context, useful action and
   evidence links without clipping or invented fallback text?

Save a short local decision record with evidence URLs, contributing run numbers,
analysis window, inference limits and the final take. Do not put this internal
quality-control record in the public cube.

This rule adds no new deliverable, no additional email and no schedule change.
Corrections to an already delivered week retain its run number and date; never
regenerate or resend that week's email without explicit approval.
