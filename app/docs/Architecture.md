# Jack Sparrow: Architecture

Version: 0.1 (draft)
Date: 2026-10-28
Related: PRD.md, Rules.md, Phases.md

## 1. Language choice

**Python 3.12** for v1.

Why:
- Best free ecosystem for this pipeline: yt-dlp, Whisper clients, Groq and Gemini SDKs, Notion client, matplotlib, and the Telegram libraries are mature.
- Multi-agent orchestration libraries (LangGraph, plain asyncio) are mature in Python.
- Rust would add build and development cost with no user-visible benefit at this scale. It can be revisited if a hot path needs it.

## 2. High-level diagram

```
 Telegram user
      |
      v
 [Telegram Bot] --(long polling)--> [Intake Handler]
                                          |
                                          v
                                   [Job Store: SQLite]
                                          |
                                          v
                                   [Orchestrator]
                                          |
          +-------------+-----------------+-----------------+
          |             |                 |                 |
          v             v                 v                 v
     [Media Agent] [Transcribe Agent] [Analysis Agents] [Report Agent]
     yt-dlp+ffmpeg  Groq Whisper      (see section 4)    Notion + charts
                                          |
                                          v
                                   [Notion Database]
                                          |
                                          v
                                 Telegram reply (link + TL;DR)
```

## 3. Components

| Component | Responsibility | Tech |
|-----------|----------------|------|
| Telegram Bot | Receive messages, send status and results | aiogram 3 (MIT). python-telegram-bot was rejected: it is LGPL-3.0, which Rules R34 does not allow |
| Intake Handler | Validate URL, check owner allowlist, create job | Python (`app/intake.py`, `app/reel_url.py`) |
| Job Store | Persist jobs, stages, retries, dedupe keys | SQLite (stdlib) |
| Orchestrator | Run stages in order, handle retries, update status | LangGraph (MIT) or asyncio state machine |
| Media Agent | Download audio only, normalize to mono 16 kHz | yt-dlp + ffmpeg (both open source) |
| Transcribe Agent | Speech to text, with language detection | Groq Whisper API (free tier); fallback: faster-whisper (MIT) locally |
| Analysis Agents | Extract and refine content (section 4) | Groq LLM (open-weight models) and Gemini (free tier) |
| Verify Agent | Check claims, find supporting links | Free web search + fetch |
| Report Agent | Build Notion page, generate charts | Notion API, matplotlib |
| Storage | Local artifacts and temp files | Local disk, cleaned after success |

## 4. Multi-agent design

Agents are small, single-purpose workers. The orchestrator passes typed data between them. No agent writes to Notion except the Report Agent.

```
Transcript
   |
   v
[1. Cleaner]  -> removes filler, fixes obvious ASR errors, keeps timestamps
   |
   v
[2. Extractor] -> title, TL;DR, key points, steps, tools, links, claims
   |
   +--> [3. Classifier] -> category + tags (from list or new, validated)
   |
   v
[4. Verifier] -> checks claims that need sources; adds links; marks confidence
   |
   v
[5. Paper Finder] -> runs only if the content depends on a paper
   |
   v
[6. Chart Planner] -> decides if a chart is useful; emits data spec or "none"
   |
   v
[7. Editor] -> merges everything into one readable report, plain language
   |
   v
[8. Critic] -> checks structure, length, broken links, schema; sends back once if needed
   |
   v
Report Agent (Notion + charts)
```

### Agent contract

Every agent:
- has a name, a system prompt file in `prompts/`, and a pydantic schema for input and output;
- returns valid JSON that matches its schema, or fails with a reason;
- gets at most 2 retries on invalid output, then the job continues with a flag `agent_partial=true`;
- logs model name, token counts (if available), latency, and the stage name. Transcripts are not logged in full.

### Model routing

| Task | Primary | Fallback |
|------|---------|----------|
| Cleaner, Extractor | Groq open-weight LLM | Gemini free tier |
| Classifier | Groq open-weight LLM (small, fast) | Gemini free tier |
| Verifier, Editor, Critic | Gemini free tier (longer context) | Groq open-weight LLM |
| Transcription | Groq Whisper | faster-whisper (local) |

Model names are read from config, not hard-coded. Free-tier availability is checked before each release.

## 5. Category system

- Categories are a soft list: projects, software, hardware, tools, tricks, startup, ideas, tech, AI/ML, coding, other.
- The Classifier picks one primary category from the list, or proposes a new one.
- A proposed category is accepted only if: it is 1 to 2 words, not a synonym of an existing category, and used in at least 1 report. Otherwise it maps to the closest existing one or "other".
- Categories are stored as Notion select options. New options are created by the Report Agent.

## 6. Data model

SQLite table `jobs`:

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT (UUID) | primary key |
| source_url | TEXT | normalized reel URL |
| dedupe_key | TEXT | reel shortcode, unique |
| chat_id | INTEGER | Telegram chat |
| status | TEXT | queued, downloading, transcribing, analyzing, writing, done, failed |
| failed_stage | TEXT | nullable |
| error | TEXT | short message, nullable |
| notion_page_id | TEXT | nullable |
| created_at | TEXT | ISO 8601 UTC |
| updated_at | TEXT | ISO 8601 UTC |

SQLite table `stages`: job_id, stage, attempt, started_at, finished_at, ok, detail.

Notion database "Jack Sparrow Reports" properties: Title (title), Category (select), Tags (multi-select), Source URL (url), Creator (text), Date saved (date), Status (select), Confidence (select: high, medium, low), Job ID (text).

## 7. Interfaces

- Source platform: Instagram only (reels, posts, and share links).
- Notion database is created once by the owner. Jack Sparrow validates its properties on startup.
- Report language: English.


- Telegram: long polling (no public URL needed). Webhook is optional later.
- Notion: REST API with an internal integration token.
- Groq and Gemini: REST via official SDKs, keys in environment variables.
- No inbound HTTP port is required in v1.

## 8. Configuration

Environment variables (see `.env.example`, never commit real values):

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_OWNER_ID`
- `GROQ_API_KEY`
- `GEMINI_API_KEY`
- `NOTION_TOKEN`
- `NOTION_DATABASE_ID`
- `JACK_SPARROW_DATA_DIR` (default `./data`)
- `JACK_SPARROW_MAX_REEL_MINUTES` (default to be decided, see PRD open questions)

## 9. Project layout

```
jack-sparrow/
  app/
    bot.py              # Telegram handlers
    orchestrator.py     # stage runner, retries
    store.py            # SQLite job store
    media.py            # yt-dlp + ffmpeg
    transcribe.py       # Whisper client + fallback
    agents/
      cleaner.py
      extractor.py
      classifier.py
      verifier.py
      paper_finder.py
      chart_planner.py
      editor.py
      critic.py
    schemas/            # pydantic models per agent
    report/
      notion_writer.py
      charts.py
  prompts/              # one markdown prompt per agent
  tests/
  docs/                 # these six files
  .env.example
  pyproject.toml
  README.md
```

## 10. Hosting options (to be verified in the hosting spike)

Owner decision (2026-10-28): a free cloud host is not required, and paid hosting is allowed with approval. Hosting will be adjusted later if needed. Until then, the bot can run on hardware the owner controls. The options below stay as reference.


| Option | Cost | Fit | Notes |
|--------|------|-----|-------|
| Owner's own machine running 24/7 | $0 | Good for v1 | Needs uptime; long polling works behind NAT |
| Oracle Cloud Always Free VM | $0 | Good | Check current free tier terms and idle policy |
| Free tier PaaS (Render, Koyeb, similar) | $0 | Partial | Free instances may sleep; long polling and background jobs need checking |
| Fly.io or similar paid | Paid | Good | Not used unless free options fail |

Decision rule: pick the first option that runs the bot for 72 hours with no missed messages. Owner may override this later.

## 11. Security and privacy

- Owner allowlist on every Telegram update.
- Secrets only in environment variables or a secrets file excluded from git.
- Temporary media deleted after success or after 24 hours on failure.
- Notion pages are private to the integration.
- Logs contain IDs, stages, and errors. They do not contain transcripts or full URLs with tokens.

## 12. Failure handling

- Download fails: retry 2 times, then report "could not access this reel".
- Transcription fails: fall back to local Whisper; if that fails, mark failed.
- Agent output invalid: retry, then continue with partial flag.
- Notion write fails: keep the report in SQLite and retry on next run. Do not send a success reply until the page exists.

## 13. Testing approach

- Unit tests: URL parsing, dedupe, category validation, schema checks.
- Golden tests: 5 sample transcripts with expected category and key fields.
- Integration test: one real short reel end to end in a test Notion database.
- Manual check: 10 real saved reels after v1.

## 14. Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Instagram blocks or changes downloads | High | yt-dlp updates; keep fallback; show a clear error |
| Free-tier rate limits | Medium | Queue jobs, backoff, track usage, local Whisper fallback |
| Hallucinated facts in reports | High | Verifier agent, confidence field, transcript kept in toggle |
| Notion image or chart limits | Medium | Prefer small PNGs; link if upload fails |
| Free host sleeps or drops the bot | Medium | Hosting spike; own machine as fallback |
