# Jack Sparrow: Design

Version: 0.1 (proposal, pending owner approval)
Date: 2026-10-28
Status: NOT APPROVED. No UI work starts until the owner approves Step 1 below.

Jack Sparrow has no custom app screen in v1. The visible design surfaces are:
1. The Telegram messages (status and reply text).
2. The Notion report page and its database view.
3. Charts and images inside reports.

This document defines the visual language for all three.

## 1. Design approval process (required before implementation)

Step 1 (this document, plus sample mockups):
- Research 2 to 3 award-winning reference designs for reading-focused and knowledge-base apps (for example, Superlist, Groto, and Notion-style layouts), reviewed on Awwwards or Mobbin.
- Produce 1 sample Notion report layout as a text wireframe and a rendered preview (HTML or PNG). Include a light and a dark version.
- Owner approves or requests changes.

Step 2 (after approval only): implement the report template and the chart style.

## 2. Design principles

- Scannable first: the reader should know what the reel is about in 5 seconds.
- Progressive disclosure: TL;DR first, detail below, transcript collapsed.
- Calm, not bland: a distinctive but quiet palette. Avoid default white with grey text everywhere.
- Accessible by default: WCAG AA contrast (4.5:1 for body text, 3:1 for large text and UI), clear focus states, no information carried by color alone.
- Consistent: the same section order, icons, and label names on every report.

## 3. Color

Palette A: "Ink and Sage" (proposed default)

| Token | Light | Dark | Use |
|-------|-------|------|-----|
| `--bg` | #F7F5EF | #14171A | Page background |
| `--surface` | #FFFFFF | #1C2025 | Callouts, cards |
| `--text` | #1E2327 | #ECEFEA | Body text |
| `--text-muted` | #55606A | #A6B0B8 | Captions, metadata |
| `--accent` | #2F6B5B | #7CC4AE | Links, headings accent |
| `--accent-2` | #B5652B | #E09A63 | Highlights, warnings |
| `--success` | #2E7D4F | #7BD19A | Confidence high |
| `--warning` | #8A5A00 | #E8C170 | Confidence low |

Contrast targets: `--text` on `--bg` at least 12:1; `--accent` on `--bg` at least 4.5:1 (check before use). Values are a proposal and must be checked with a contrast tool during Step 1.

Category colors (used in Notion select options and chart legends). Each color has a text label as well, so color is not the only cue:

| Category | Color |
|----------|-------|
| projects | #2F6B5B |
| software | #3B6EA8 |
| hardware | #6B5B95 |
| tools | #8A5A00 |
| tricks | #B5652B |
| startup | #A23B5C |
| ideas | #C9A227 |
| tech | #2C7A8C |
| AI/ML | #5B7F2A |
| coding | #4A4A8A |
| other | #6B7278 |

Check that all category colors meet 3:1 against `--surface` before final use.

## 4. Typography

- Headings: a humanist sans with clear letterforms. Proposed: Inter or Source Sans 3 (both open-source, OFL).
- Body: same family for simplicity. Size 16 px minimum, line height 1.6.
- Monospace for transcripts and code: JetBrains Mono or IBM Plex Mono (OFL).
- Heading scale: H1 28 px, H2 22 px, H3 18 px. Body max line length about 70 characters.
- Notion does not allow custom fonts. The Notion page uses Notion's default fonts. Typography rules apply to charts, images, and any HTML preview.

## 5. Notion report layout (proposal)

```
# [Title]                                  (H1)
[Category badge]  [tag] [tag] [tag]        (callout line)
Source: [link]   Creator: @handle   Saved: 2026-10-28   Confidence: high

> TL;DR                                    (callout, 2 to 3 sentences)

## Key points                              (bulleted, max 7)
## Steps or how-to                         (numbered, only if present)
## Tools and links                         (table: name, what it does, link)
## Graphs                                  (only if useful; chart + 1-line caption)
## Sources and papers                      (only if needed)
## Agent notes                             (confidence reasons, unverified items)
### Transcript                             (toggle, collapsed by default)
```

Rules:
- Every section appears only if it has content. Empty sections are removed, not filled with "none".
- Links use descriptive text ("Official Docs for X"), not raw URLs in the middle of a sentence.
- Images have alt text. Charts have a caption that states the source.

## 6. Charts

- Chart types: bar for comparisons, line for trends, table when there are fewer than 4 values.
- Max 1 chart per report unless the content clearly needs more.
- Size: 1200 px wide PNG at 2x for sharpness, under 300 KB.
- Colors from the palette above. Labels directly on bars or points where possible.
- Font: the body sans family if available locally; a system sans as fallback.
- Alt text describes the trend or comparison in one sentence.
- No chart if the data is weak (R20).

## 7. Telegram message style

- Short, plain sentences. No emoji beyond one status marker per message, if the owner wants it.
- Status format:
  - "Queued. Reel saved for processing."
  - "Downloading audio..."
  - "Transcribing..."
  - "Writing your report..."
  - "Done. [Report title] is in Notion: [link]"
- Failure format: "Could not finish at [stage]: [short reason]. Send the link again to retry."

## 8. Iconography

- One simple line icon set (Lucide, ISC license) for category markers in Notion callouts if needed.
- Icons always sit next to a text label.

## 9. Motion

- Not applicable in v1 (Notion and Telegram control motion).
- For any future HTML preview: respect `prefers-reduced-motion`. Keep transitions under 200 ms.

## 10. Responsive and mobile

- Owner will read reports mostly on a phone. Notion's mobile layout is the target.
- Keep TL;DR and category visible without scrolling on a phone screen.
- Tables with more than 3 columns are converted to lists on mobile-friendly reports.

## 11. Open design questions

1. Dark mode for charts: auto-switch, or one light style only?
2. Show the source reel thumbnail in the report? (Default: no, to keep reports clean and avoid copying Instagram content.)
3. Category icons: needed or text only?
