# Jack Sparrow: Memory (session state and progress log)

Purpose: the running record of what has been decided, built, tested, and what is next. Update at the end of every work session (Rules R38).

## Current status

- Phase 3 live test PASSED on owner's machine (reel downloaded, transcribed by Groq, status 'transcribed').
- Phase 4 (analysis) code complete; live LLM and Exa tests pending.
- Phase 5 (Notion) code complete. Owner approved the layout. Chart is a table (not image). Live Notion test pending.
- Community post: built and tested; owner approved the style.
- Phase 0 not started (hosting spike; the owner's own machine is currently being used).
- Stage: project skeleton, config loader, SQLite job store, logging setup, tests passing
- Blocked: nothing
- Next action: owner provides TELEGRAM_BOT_TOKEN and TELEGRAM_OWNER_ID for the live test of Phase 2; then Phase 0 hosting spike, or Phase 3 (media and transcription)

## Decisions

| Date | Decision | Reason |
|------|----------|--------|
| 2026-10-28 | Phase 1 uses stdlib only (no new dependencies) | Keeps the skeleton light; dependencies added per phase |
| 2026-10-28 | Language: Python 3.12 | Best free ecosystem for yt-dlp, Whisper clients, Notion, Telegram; Rust deferred |
| 2026-10-28 | Instagram only, no other platforms | Owner answer |
| 2026-10-28 | Notion DB created once by owner; bot validates | Owner answer |
| 2026-10-28 | English reports, structured format | Owner answer |
| 2026-10-28 | Hosting: free cloud not required; adjust later | Owner answer |
| 2026-10-28 | Telegram library: aiogram 3 (MIT) | python-telegram-bot is LGPL-3.0 and fails R34 |
| 2026-10-28 | Transcription: Groq Whisper primary, faster-whisper local fallback | Architecture section 4; fallback works offline |
| 2026-10-28 | Single background worker, one job at a time | Free-tier limits and small hosts |
| 2026-10-28 | Phase 4: Cleaner merged into Extractor; Verifier stub until search provider chosen; Editor and Critic rule-based | Free-tier call limits; search provider not yet chosen |
| 2026-10-28 | Web search: Exa free tier; claims marked 'sourced' only on word overlap | Owner choice; verifier must not guess |
| 2026-10-28 | Notion database is created by the bot (owner's later decision, replacing 'owner creates it'); needs a shared parent page |
| 2026-10-28 | Notion page layout approved by owner; chart rendered as table until an image host exists | Owner approval; Rules R43 |
| 2026-10-28 | Comments and DMs are never read (R15). Research uses public web sources | Access controls must not be bypassed |
| 2026-10-28 | Visual analysis deferred until owner picks Gemini (key) or Tesseract (local OCR) | No vision model on current keys |
| 2026-10-28 | Telegram via long polling | No public URL needed; easier to host on a home or free machine |
| 2026-10-28 | Notion is the only UI in v1 | Scope control (Rules R3) |
| 2026-10-28 | Categories are agent-chosen from a soft list, validated | User asked agents to decide; validator prevents category sprawl |
| 2026-10-28 | Papers linked only when the reel depends on them | User request |
| 2026-10-28 | Free and open-source preferred; paid allowed with approval and a monthly cap | Owner answer; Rules R5, R7 relaxed |
| 2026-10-28 | Design.md is a proposal; Step 1 approval required before UI work | Project design preference: design approval before implementation |

## Owner answers (2026-10-28)

1. Long reels: process full reel, target 2 to 3 minutes.
2. Other platforms: no. Instagram only.
3. Report language: English, structured format.
4. Notion database: owner creates it once. Bot validates it.
5. Hosting: free cloud not required; will adjust later if needed.

7. Rules R5 and R7 relaxed: free or open-source preferred; paid tools and recurring spend allowed with owner approval and a recorded monthly cap.
6. Design: pending. Palette and layout (Design.md) still need approval.

## Free-tier limits (to be filled in during Phase 0)

| Service | Limit | Checked on | Source |
|---------|-------|------------|--------|
| Telegram Bot API | To confirm | - | - |
| Groq (Whisper) | To confirm | - | - |
| Groq (LLM) | To confirm | - | - |
| Gemini API | To confirm | - | - |
| Notion API | To confirm | - | - |
| Hosting option | To confirm | - | - |

## Progress log

### 2026-10-28 (Context and research)
- Owner asked for full-reel understanding. Built: public caption and metadata, AI research with Exa, source tiers, verification, de-duplication, manual-review flags.
- Not built, and why: comments and DMs (Rules R15, no access bypass). On-screen text and video frames (needs a vision model: Gemini key or Tesseract). Owner to choose.
- Changed Analyzer signature to (transcript, url, context). Test fakes updated.
- Tests: 140 passing, 1 skipped (live).


### 2026-10-28 (Notion database created by the bot)
- Owner changed the earlier decision: Jack Sparrow now creates the "Jack Sparrow Reports" database itself (task 5.1 revised).
- It needs a parent page shared with the integration. If exactly one page is shared, it is used. If several are, set NOTION_PARENT_PAGE_ID.
- The new database ID is saved to data/notion_database_id.txt, so restarts reuse it. NOTION_DATABASE_ID can still be set to use an existing database.
- Tests: 123 passing, 1 skipped (live).


### 2026-10-28 (Phase 5, Notion page)
- Owner approved the preview layout.
- `app/notion_layout.py`: builds the page body in the approved order. Empty sections are skipped. Transcript sits in a collapsed toggle. Long text is split under Notion's limits.
- `app/notion_writer.py`: `write_report` creates the page with its body, or updates properties only if the job already has a page.
- `app/notion_publish.py`: publisher used by the pipeline. The database is checked at startup. Setup errors stop the bot with a clear message.
- Pipeline: after analysis, status 'writing' then 'done' with the Notion page ID saved. A Notion error marks the job failed at stage 'notion' and keeps the report.
- Deviation: the chart is a table, not an image. Needs owner OK.
- Tests: 113 passing, 1 skipped (live).


### 2026-10-28 (Community post)
- Owner approved the style: hook, blank line, body, blank line, closing. No category, no links, no Notion references, no hashtags.
- `prompts/post.md` and `app/social_post.py` (render and validate). New `SocialPost` schema. `Report.post` field.
- Analysis writes the post. The pipeline saves `post.txt` and sends it to the owner as a plain-text Telegram message.
- Delivery failure does not fail the job. The report is still saved.
- WhatsApp: no free bot route to personal chats. The owner copies the post from Telegram.
- Tests: 107 passing, 1 skipped (live).


### 2026-10-28 (Phase 5, partial)
- `app/notion_client.py`: stdlib REST client. Notion-Version pinned to 2022-06-28 (confirm in Phase 0 task 0.5). Errors never include the token.
- `app/notion_writer.py`: validates the owner's database (9 properties and types, task 5.1). Writes Category, Tags, Source URL, Creator, Date saved, Status, Confidence, and Job ID. Finds an existing page by Job ID and updates it, so reruns do not duplicate (task 5.4).
- `app/notion_layout.py`: stub. Raises NotImplementedError until the design is approved.
- `docs/design/notion_report_preview.html`: preview of the report page, built from the binary-search reel. Notion controls its own fonts, so the real page will differ.
- Tests: 101 passing, 1 skipped (live).


### 2026-10-28 (Phase 4 verifier and golden test)
- Web search provider chosen: Exa free tier (owner's choice). Endpoint `POST https://api.exa.ai/search`, header `x-api-key`. Client in `app/web_search.py`, standard library only.
- EXA_API_KEY added to config, .env.example, and secret-field list. Owner has not provided the key yet.
- Verifier: up to 3 claims per reel searched. Status 'sourced' requires word overlap; otherwise 'unverified'.
- Golden test: real transcript (binary search reel) in `tests/golden/`. Offline test uses a canned extraction. Live test is skipped unless RUN_LIVE=1 and GROQ_API_KEY are set.
- Transcript shows ASR errors ('debat threshold', 'debaard sexual'). The live Extractor should correct them. Check this in the live run.
- The sandbox cannot reach api.exa.ai, so Exa was not called live.
- Tests: 92 passing, 1 skipped (live).


### 2026-10-28 (Phase 3 live test)
- Owner ran `python -m app bot` on Windows. Reel (post link) was queued, downloaded, transcribed by Groq (HTTP 200), and marked transcribed with speech detected.
- Transient Telegram network timeout was handled (aiogram retried).
- Owner's Groq key and bot token were shared in chat. Owner plans to rotate them. Keys are not stored in this repo.

### 2026-10-28 (Phase 4)
- `prompts/` holds agent prompts (extractor, classifier, chart).
- `app/schemas.py`: pydantic models for every agent output and the final Report.
- `app/llm.py`: Groq JSON-mode client and `call_agent` (2 retries on invalid output, then AgentError).
- `app/categories.py`: category validation (aliases, new categories limited to 1-2 words).
- `app/paper_search.py`: arXiv API search (free, no key), used only when the reel depends on a paper.
- `app/analysis.py`: pipeline. Extractor is required; classifier, chart, and paper steps set partial=True on failure. Chart values and labels must appear in the transcript (R20). Non-http links are removed.
- `app/pipeline.py`: analysis step after transcription; saves `report.json`; status 'analyzing' then 'analyzed'.
- Verifier is a stub until a web search provider is picked (open decision).
- Model name `llama-3.3-70b-versatile` is unverified; confirm during the live test.
- Tests: 87 passing. Ruff clean.


### 2026-10-28 (Phase 3)
- `app/media.py`: yt-dlp audio-only download, ffmpeg to mono 16 kHz WAV, user-safe error messages (private, rate-limited, unavailable, no audio). Raw error text never reaches Telegram.
- `app/transcribe.py`: Groq Whisper (`whisper-large-v3-turbo`) primary; faster-whisper `small` (int8, CPU) fallback, loaded only when needed. No-speech detection via `no_speech_prob`.
- `app/pipeline.py`: download -> transcribe -> save `transcript.json` and `transcript.txt` under `data/jobs/<id>/` -> delete media (R13). Stage timing recorded in `stages`.
- `app/worker.py`: single background worker that claims queued jobs (atomic claim in store) and updates the Telegram status message at each stage.
- `app/store.py`: new status `transcribed`; `claim_next_queued`, `record_stage`, `now_iso`.
- `app/bot.py`: `run_polling` now starts the worker alongside polling.
- Libraries added: yt-dlp (Unlicense), groq (Apache-2.0), faster-whisper (MIT). ffmpeg is a system program called as a separate process (not bundled).
- Tests: 65 passing. Ruff clean.
- Known gaps: failed-job media is not cleaned after 24 hours yet (Phase 6). A job stuck in 'downloading' after a crash is not resumed yet (Phase 6). Live reel test not run.


### 2026-10-28 (Phase 2)
- Library: aiogram 3 (MIT). Architecture previously named python-telegram-bot, which is LGPL-3.0 and rejected under R34. Corrected in Architecture.md.
- `app/reel_url.py`: Instagram reel, post, tv, and share link parsing with dedupe keys.
- `app/intake.py`: owner gating (non-owner gets no reply), /start and /help, duplicate handling, retry of failed jobs by resending the link.
- `app/bot.py`: aiogram wiring with long polling; saves the status message ID so it can be edited later (task 2.6).
- `app/store.py`: schema v2 adds `status_message_id`.
- `python -m app bot` runs the bot. It refuses to start without token and owner ID.

### 2026-10-28 (Phase 1)
- Created `pyproject.toml`, `.gitignore`, `.env.example`.
- `app/config.py`: env + `.env` loading, owner ID validation, `require()` that lists missing names without values.
- `app/store.py`: SQLite schema v1 (`jobs`, `stages`) with PRAGMA user_version migrations; create, get, dedupe lookup, status updates.
- `app/logging_setup.py`: logging format only; no transcript logging.
- `app/__main__.py`: `python -m app` loads config, creates DB, exits.
- Tests: 15 passing (pytest). Lint: ruff clean.
- Runtime library dependencies: none yet (stdlib only).
- Environment note: sandbox has Python 3.13; project targets 3.12+ as specified.
- Git: no repo initialized yet (R36 and R37 apply once a repo exists).

### 2026-10-28
- Created `docs/` with: PRD.md, Architecture.md, Rules.md, Phases.md, Design.md, Memory.md.
- Chose Python 3.12 as the implementation language.
- Drafted multi-agent pipeline: Cleaner, Extractor, Classifier, Verifier, Paper Finder, Chart Planner, Editor, Critic, plus Media, Transcribe, and Report agents.
- No code written. No external services tested yet. All free-tier limits are unverified.
- Design: proposal only. Not approved.

## Test results

- 2026-10-28: 42 pytest tests pass (config, store, reel URL parsing, intake rules, bot wiring). Ruff clean.
- Not tested live: Telegram connection (no token yet).

## Hosting spike results

Not started.

## Known risks (see Architecture.md section 14)

- Instagram download changes (yt-dlp).
- Free-tier rate limits.
- Hallucinated facts in reports.
- Free host reliability.
