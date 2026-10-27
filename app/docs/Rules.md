# Jack Sparrow: Rules

Version: 0.1
Date: 2026-10-28
Applies to: the owner, every contributor, and every AI assistant (including Claude) working in this repo.

## 1. Scope rules (what we build)

- R1: Only build what is in PRD.md and Phases.md for the current phase. Anything else goes into the backlog section of Phases.md.
- R2: Do not add new platforms (YouTube, TikTok, etc.) before v1 is accepted.
- R3: No web app, dashboard, or custom UI in v1. Notion is the interface.
- R4: Design work for any user-facing surface (including the Notion report layout) follows Design.md and needs owner approval before implementation.

## 2. Cost and tooling rules

- R5: Prefer free or open-source tools. Paid tools and hosting are allowed with owner approval. Each paid tool needs a written decision in Memory.md that names the reason and the monthly cost cap.
- R6: Every external service used must have its free-tier limit recorded in Architecture.md section 3 or in a `docs/limits.md` file, with the date checked.
- R7: Recurring spend is allowed only with owner approval and a monthly cap recorded in Memory.md. One-time purchases (domain, hardware) also need owner approval.
- R8: Prefer local open-source models when a hosted free tier is at its limit. The fallback must work offline for transcription.

## 3. Privacy and security rules

- R9: Secrets live only in environment variables or an untracked `.env`. Never commit them, print them, or paste them into logs or issues.
- R10: `.env.example` lists variable names only, with placeholder values.
- R11: The bot ignores every message from users other than `TELEGRAM_OWNER_ID`.
- R12: Do not log full transcripts, full report text, or tokenized URLs. Log IDs, stage names, durations, and error types.
- R13: Delete downloaded video and audio after a successful transcript. Delete failed-job media after 24 hours.
- R14: Reports and transcripts stay private. Notion pages must not be shared publicly.
- R15: Do not bypass logins, paywalls, private accounts, or access controls. If a reel cannot be accessed normally, the job fails with a clear message.

## 4. Content and accuracy rules

- R16: Every factual claim in a report must trace to the transcript, the caption, or a cited source. Claims with no support are either removed or marked "unverified".
- R17: Reports must show a confidence level (high, medium, low) and a short reason when it is not high.
- R18: Do not invent links, papers, DOIs, or statistics. If a link cannot be confirmed by fetching it, do not include it.
- R19: Research papers are included only when the reel depends on them. Add the citation and link, never a summary the agent cannot verify.
- R20: Charts must use numbers that appear in the source. If the data is weak, do not chart it.
- R21: Do not reproduce long passages of copyrighted text, captions, or lyrics in reports. Summarize in own words and keep quotes short.
- R22: The transcript is kept inside a collapsed toggle, so the report stays readable.

## 5. Agent rules

- R23: Each agent has one responsibility, one prompt file in `prompts/`, and one schema.
- R24: Agents must return schema-valid JSON. Invalid output is retried at most twice.
- R25: Agents may propose categories and tags, but the validator decides what is accepted (see Architecture.md section 5).
- R26: Only the Report Agent writes to Notion.
- R27: Agents must not call tools or sites outside the allowlist in config (search, fetch, Notion, Groq, Gemini).
- R28: Prompts must tell agents to say "I don't know" or "not in source" rather than guess.

## 6. Engineering rules

- R29: Python 3.12, type hints on all public functions, `ruff` for lint and format.
- R30: Every stage is idempotent. Re-running a job must not duplicate a Notion page or re-download media that exists.
- R31: No blocking calls in the Telegram handler. Long work runs in a background worker.
- R32: Every external call has a timeout and at most 2 retries with exponential backoff.
- R33: Keep functions small. A file over 300 lines needs a reason in review.
- R34: New dependencies must be open source with a permissive license (MIT, BSD, Apache 2.0). Record them in `pyproject.toml` with a comment on the license.
- R35: No Rust code in v1 unless a benchmark in Memory.md shows Python is a bottleneck.

## 7. Git and process rules

- R36: `main` is always runnable. Work happens on short-lived branches.
- R37: Each PR covers one phase task from Phases.md and links to it.
- R38: Update Memory.md at the end of each work session: what changed, what is next, what is blocked.
- R39: Do not change these six docs silently. Any change to PRD, Architecture, or Rules is noted in Memory.md with the reason.

## 8. Rules for AI assistants

- R40: Read Memory.md, then Phases.md, before starting work.
- R41: Ask before deleting files, rewriting history, or changing secrets handling.
- R42: Do not claim a tool, API, or free tier works without checking its current docs or a test call. Say what was checked.
- R43: For any UI or design change, present the design first and wait for approval before coding.
- R44: When uncertain about scope, pick the smaller option and list the question in Memory.md.
- R45: Report results honestly. If a test was not run, say so.

## 9. Definition of done (per task)

- Code runs locally and the relevant tests pass.
- Lint passes.
- No secrets in the diff.
- The change matches PRD and Architecture, or the docs were updated with a reason.
- Memory.md is updated.
