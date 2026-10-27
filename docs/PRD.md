# Jack Sparrow: PRD (Product Requirements Document)

Version: 0.1 (draft)
Date: 2026-10-28
Owner: denoroy737@gmail.com

## 1. Problem

People save Instagram reels "for later" and never open them again. The saved content, which often contains useful project ideas, tools, tricks, and research leads, is effectively lost.

## 2. Solution

Jack Sparrow turns saved reels into structured, readable reports that are stored in Notion and easy to find later.

Flow:

1. User sends an Instagram reel link to a Telegram bot.
2. Jack Sparrow downloads the audio.
3. Jack Sparrow transcribes the audio to text.
4. A team of AI agents refines the transcript into the important information: ideas, steps, tools, links, and claims.
5. Agents decide the category (for example: projects, software, hardware, tools, tricks, startup, ideas, tech, AI/ML, coding, other).
6. Jack Sparrow writes a clean report to Notion with a summary, key points, graphs or images where useful, and links. Research papers are included only when the content actually depends on them.
7. Jack Sparrow replies in Telegram with the Notion link and a 3 line summary.

## 3. Target user

Primary: the owner (single user for v1). Someone who saves short-form video for learning and project ideas and wants those saves to become usable notes.

## 4. Goals (v1)

- G1: A reel link becomes a Notion report with no manual steps, end to end.
- G2: Reports are quick to scan: a clear title, TL;DR, categories, key points, and links.
- G3: Agents choose the category and tags. The user does not pick them.
- G4: Runs on free or open-source tools where practical. Paid services are allowed with owner approval.
- G5: The Telegram bot backend can be hosted for free (or on hardware the user already owns). This is verified by a spike, not assumed.

## 5. Non-goals (v1)

- Multi-user accounts, billing, or a public sign-up.
- Downloading or re-hosting video. Only audio is processed, and it is discarded after transcription.
- Full-text search UI or a custom web app. Notion is the interface.
- Automatic posting or any action on Instagram.
- Summarizing content the user has not saved through Jack Sparrow.

## 6. Users and key scenarios

| # | Scenario | Expected result |
|---|----------|-----------------|
| S1 | User sends a public reel link to the bot | Bot acknowledges, then replies with a Notion link within a few minutes |
| S2 | Reel has no speech (music only) | Bot reports "no speech detected" and still saves a short note with the caption if available |
| S3 | Reel is private, deleted, or blocked | Bot explains the failure in one line and does not retry forever |
| S4 | Same reel sent twice | Bot returns the existing report instead of creating a duplicate |
| S5 | Reel is long | Bot processes the full reel. Target completion is about 2 to 3 minutes |
| S6 | Non-English speech | Transcript is in the original language. Report is written in English |

## 7. Functional requirements

### Intake (Telegram)
- FR-1: Accept messages containing an Instagram reel URL (`instagram.com/reel/...`, `instagram.com/p/...`, `instagram.com/share/...`).
- FR-2: Reject or ignore non-reel messages with a short help reply.
- FR-3: Accept only messages from the owner's Telegram user ID (allowlist).
- FR-4: Send a status message that updates through the stages: queued, downloading, transcribing, analyzing, writing to Notion, done.

### Media and transcription
- FR-5: Extract audio from the reel (audio only, no video kept).
- FR-6: Transcribe with a free hosted Whisper model (Groq free tier) or a local open-source Whisper model as fallback.
- FR-7: Delete downloaded media and audio files after a successful transcript is stored.

### Agents (refinement)
- FR-8: Run a multi-agent pipeline. Agents have separate responsibilities (see Architecture.md).
- FR-9: Agents extract: title, one-paragraph TL;DR, key points, steps or how-to items, tools and libraries mentioned, links, numbers or claims that need a source, and open questions.
- FR-10: Agents choose one primary category and up to 5 tags. The category list starts from the examples above. Agents may propose a new category, and it is accepted if it is specific and not a duplicate.
- FR-11: Agents mark claims that need verification. Verification uses free web search and only adds sources where they support the point.
- FR-12: A research paper is linked only when the reel's content depends on it (for example, it cites a specific study). Papers are not added by default.

### Report output (Notion)
- FR-13: Create one Notion page per reel in a single "Jack Sparrow Reports" database.
- FR-14: Database properties: Title, Category, Tags, Source URL, Creator handle (if known), Date saved, Status, Confidence.
- FR-15: Page body sections: TL;DR, Key points, Steps or how-to, Tools and links, Graphs or images (only when they add value), Sources and papers (only when needed), Transcript (collapsed toggle), Agent notes.
- FR-16: Graphs are generated from data the reel contains (for example, a comparison of tools or numbers). Charts are rendered as PNG and uploaded or linked. No chart is added when there is no real data.
- FR-17: Images are used only when they help understanding. The source Instagram image is not copied into the report.

### Community post (added 2026-10-28)
- FR-21: After analysis, Maya writes one short, eye-catching post for a public community: a hook, a body with the useful takeaway, and a closing line.
- FR-22: The post has no links, no hashtags, no category, no creator name, and no Notion references. It is plain text, sent to the owner in Telegram to copy.
- FR-23: The post is validated (length and banned words). A post that fails validation is not sent.

### Context and research (added 2026-10-28)
- FR-24: Public metadata (title, caption, creator, duration, upload date) is saved with the job and used in analysis. Only public fields are kept. No cookies or request headers are stored.
- FR-25: A research step plans up to 4 searches from the reel's names, runs them on the web, and lists official and reliable sources first. Duplicates are removed.
- FR-26: Results that are inferred or not clearly verified are marked needs_review for manual checking.
- FR-27: Comments and DMs are NOT read (Rules R15). Public web sources are used instead.
- Not in this version: on-screen text, video frames, and speech beyond the audio track. These need a vision-capable model (Gemini free tier with a key, or local OCR with Tesseract). Owner to choose.

### Reliability
- FR-18: Each job has an ID. Re-running a job does not create a duplicate Notion page.
- FR-19: Failed stages are retried up to 2 times with backoff. After that, the job is marked failed and the user is told which stage failed.
- FR-20: Jobs survive a bot restart (stored in a local SQLite file).

## 8. Non-functional requirements

- NFR-1 Cost: free tiers and open-source tools preferred. Paid services or hosting are allowed with owner approval and a recorded monthly cap. Free-tier limits are checked and logged.
- NFR-2 Latency: a typical 60-second reel completes in under 3 minutes.
- NFR-3 Privacy: transcripts and reports are visible only to the owner. No public links. Secrets are in environment variables, never in the repo.
- NFR-4 Accessibility of output: reports use clear headings, short paragraphs, descriptive link text, and alt text on images.
- NFR-5 Maintainability: each agent is a separate module with a clear input and output schema.
- NFR-6 Portability: runs on a single small Linux machine or a free-tier cloud VM.

## 9. Success metrics

- M1: 90% of reel links produce a Notion report without manual intervention (measured over the first 50 jobs).
- M2: Median time from link to report under 3 minutes.
- M3: The owner opens or reuses at least 1 report per week (qualitative check after 4 weeks).
- M4: Monthly cost stays within the cap the owner approves (currently none set).

## 10. Constraints and assumptions

- Free and open-source tools preferred. Candidate stack: Telegram Bot API, Groq (Whisper and LLM, free tier), Google Gemini (free tier), yt-dlp (audio extraction), Notion API, SQLite, matplotlib for charts.
- Free-tier limits change. Each limit must be confirmed in the provider's current docs before it is relied on.
- Instagram content access depends on the reel being public. Jack Sparrow does not bypass logins, paywalls, or privacy settings.
- The user is responsible for only saving content they have the right to process for personal use.

## 11. Decisions from owner (2026-10-28)

1. Long reels: process the full reel. Target completion is about 2 to 3 minutes per reel.
2. Other platforms (YouTube Shorts, TikTok): no. Instagram only, for v1 and v2 unless the owner changes this.
3. Report language: English, in a structured format.
4. Notion database: the owner creates it once. Jack Sparrow validates its fields on startup and does not create it.
5. Hosting: the owner does not want a free-cloud-only setup. Hosting will be adjusted later if required. Hosting choice is deferred; the Phase 0 hosting test still runs.

## 12. Release scope

- v1: Telegram intake, audio extraction, transcription, multi-agent refinement, Notion report with categories, tags, and charts where useful, job tracking, hosting spike.
- v2: Search and "resurface" (weekly digest of unread reports), more platforms, better verification.

## 13. Glossary

- Reel: short vertical video on Instagram.
- Job: one reel processed from link to Notion page.
- Agent: one AI worker with a single responsibility, coordinated by an orchestrator.
