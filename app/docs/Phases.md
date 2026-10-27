# Jack Sparrow: Phases

Version: 0.1
Date: 2026-10-28
Rule: finish a phase's "Done when" before starting the next. Small chunks, one PR each where possible.

## Phase 0: Hosting and feasibility spike

Goal: confirm the riskiest assumptions before building.

Tasks:
- 0.1 Create a Telegram bot with BotFather. Confirm long polling receives a message.
- 0.2 Test yt-dlp audio extraction on 3 public reels (short, medium, long). Record success and time.
- 0.3 Test Groq Whisper on one extracted audio file. Record latency and free-tier limit.
- 0.4 Test one Gemini free-tier call and one Groq LLM call. Record limits.
- 0.5 Create a Notion integration and a test database. Write one page via API. Test one external image in a page.
- 0.6 Test bot hosting: run the bot on the candidate host (owner's machine or a cloud VM) for 72 hours. Free cloud is not required.

Done when:
- All 6 tasks have a recorded result in Memory.md.
- A hosting option is chosen per Architecture.md section 10.
- Any blocked item has a decision logged (switch tool, accept risk, or drop feature).

## Phase 1: Project setup

Status: COMPLETE (2026-10-28). 15 tests pass, ruff clean.

Tasks:
- 1.1 Create repo layout from Architecture.md section 9.
- 1.2 Add `pyproject.toml` (Python 3.12), `ruff`, `pytest`.
- 1.3 Add `.env.example` and `.gitignore` (include `.env`, `data/`).
- 1.4 Add config loader with validation for required variables.
- 1.5 Add SQLite job store with tables `jobs` and `stages`, plus migration on startup.
- 1.6 Add structured logging with no transcript content.

Done when:
- `pytest` runs (even with placeholder tests).
- App starts and creates the database without errors.
- No secrets committed.

## Phase 2: Telegram intake

Status: CODE COMPLETE (2026-10-28). 42 tests pass, ruff clean. Live bot test pending: needs TELEGRAM_BOT_TOKEN and TELEGRAM_OWNER_ID from the owner.
Known limitation (task 2.3): share links and canonical reel links use different dedupe keys, so the same reel shared both ways can create two jobs.

Tasks:
- 2.1 Bot starts with long polling and responds to `/start` and `/help`.
- 2.2 Owner allowlist check on every update (R11).
- 2.3 URL parser accepts reel, post, and share links; normalizes to a shortcode.
- 2.4 Duplicate check using shortcode. If the job exists, reply with the existing status or Notion link.
- 2.5 Create a job row and reply "queued".
- 2.6 Status messages edited in place as stages change.

Done when:
- An owner message with a reel link creates a job and shows "queued".
- A non-owner message gets no response and no job.
- A duplicate link does not create a second job.

## Phase 3: Media and transcription

Status: CODE COMPLETE (2026-10-28). 65 tests pass. Live download and transcription not yet tested: needs a Groq key (task 0.3) and real reels (task 3.x check). Phase 3 ends at status 'transcribed'. Report generation is Phase 4 and Phase 5.

Tasks:
- 3.1 Media Agent: yt-dlp audio-only download, ffmpeg convert to mono 16 kHz WAV.
- 3.2 Handle failures: private, deleted, rate-limited, unsupported. Map to clear user messages.
- 3.3 Transcribe Agent: Groq Whisper call with language detection and timestamps.
- 3.4 Fallback to faster-whisper locally when the Groq call fails or the limit is hit.
- 3.5 Save transcript to the job folder. Delete media after success (R13).
- 3.6 Handle no-speech reels (S2).

Done when:
- 10 saved sample reels produce transcripts (or a clear "no speech" result).
- Media files are removed after success.
- Failures show a clear message and the job is marked failed.

## Phase 4: Multi-agent refinement

Status: CODE COMPLETE (2026-10-28). 92 tests pass, 1 live test skipped. Live LLM and Exa runs not yet tested.
Verifier uses Exa (free tier) for up to 3 claims per reel. A claim is 'sourced' only when a result overlaps its key words.
Scope decisions made to fit free-tier limits (also in Memory.md):
- Cleaner merged into the Extractor prompt (one LLM call instead of two).
- Verifier uses Exa free tier (up to 3 claims per reel). Status 'sourced' means a source overlaps the claim's key words. It is not a model-checked verdict.
- Editor is the rule-based Assembler in `app/analysis.py`.
- Critic is rule-based checks.
- LLM calls per reel: Extractor, Classifier, Chart Planner (chart step can return null).

Tasks:
- 4.1 Define pydantic schemas for each agent's input and output.
- 4.2 Write prompts for Cleaner and Extractor. Test on 5 transcripts.
- 4.3 Add Classifier with the soft category list and the validator (Architecture.md section 5).
- 4.4 Add Verifier with web search and fetch. Confidence field added.
- 4.5 Add Paper Finder, triggered only when the extractor flags a paper dependency.
- 4.6 Add Chart Planner (returns "none" when data is weak).
- 4.7 Add Editor and Critic. Critic can send work back once.
- 4.8 Orchestrator (LangGraph or asyncio) wires the stages with retries and partial flags.
- 4.9 Golden tests: one real transcript added (binary search reel, tests/golden/). Four more transcripts still needed from the owner.

Done when:
- Golden tests pass on category and required fields.
- No agent output fails schema validation after retries on the test set.
- Every factual claim in the test outputs has a source or an "unverified" mark (R16).

## Phase 5: Notion report output

Status: CODE COMPLETE (2026-10-28). Layout approved by owner. 113 tests pass. Live Notion test not yet run.
Deviation from the approved preview: the chart is a Notion table, not a PNG image. Notion needs an uploaded or public image URL, and no free image host is set up yet. Owner to confirm table is OK for now.
Writes happen once per job. Reruns update properties only, not the page body.

Tasks:
- 5.1 Report Agent validates the owner-created "Jack Sparrow Reports" database on startup (properties and types). It does not create the database.
- 5.2 Write page with the section order in PRD FR-15.
- 5.3 Add Category and Tags as Notion properties; create new select options when needed.
- 5.4 Idempotent write: use Job ID to find an existing page before creating one.
- 5.5 Charts: matplotlib PNG generated from the chart spec, then added to the page. If upload fails, add a text table instead.
- 5.6 Reply in Telegram with the Notion link and a 3-line TL;DR.
- 5.7 Design review: APPROVED (2026-10-28).

Done when:
- A reel link produces a complete Notion page with all sections.
- Sending the same link again does not create a duplicate page.
- The owner approves the sample page design.

## Phase 6: Reliability and hardening

Tasks:
- 6.1 Retry policy per stage (R32). Max 2 retries with backoff.
- 6.2 Job resume after restart. Stuck jobs marked failed after a timeout.
- 6.3 Cleanup task for media older than 24 hours on failure (R13).
- 6.4 Usage counter for each free-tier provider, shown in logs and a `/usage` command.
- 6.5 Integration test with one real short reel in a test Notion database.
- 6.6 Run the 10-reel manual check (Architecture.md section 13).

Done when:
- 90% of the 10-reel check completes with no manual steps (M1 in PRD).
- Bot restart does not lose jobs.
- `/usage` shows current counts for each provider.

## Phase 7: Hosting and v1 release

Tasks:
- 7.1 Deploy to the chosen host from Phase 0. Write a short runbook in `README.md`.
- 7.2 Set up a restart policy (systemd, Docker restart policy, or the host's equivalent).
- 7.3 Set up a simple heartbeat: the owner gets a Telegram message if the bot has been down for more than 10 minutes (only if this is free to run).
- 7.4 Measure median time from link to report (M2).
- 7.5 Write the v1 review in Memory.md: what worked, what to change.

Done when:
- Bot runs for 7 days on the chosen host with no manual restart.
- Median time under 3 minutes for a 60-second reel (M2). Full reel processed, target 2 to 3 minutes.
- Owner signs off v1.

## Phase 8 (v2, not scheduled): Resurface and search

Backlog only. Do not start until v1 sign-off.
- Weekly digest of reports not opened in 30 days.
- Notion view by category and tag.
- Other platforms are out of scope (Instagram only, per owner).
- Better verification with more sources.

## Backlog (unscheduled)

- Long reel handling policy (PRD open question 1).
- Report language setting (PRD open question 3).
- Rust rewrite of the media path, only if benchmarks justify it.
