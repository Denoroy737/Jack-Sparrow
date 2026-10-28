# Jack Sparrow

Jack Sparrow turns Instagram reels you save into structured reports in Notion.
Send a reel link to your Telegram bot. The bot downloads the audio, transcribes
it, finds the tools and links it mentions, and saves a report page to Notion.
It also writes a short post you can share with a community.

Only the bot owner can use it. Other Telegram users are ignored.

## What you get

Each reel becomes a Notion page with:

- **Summary:** a short plain-language overview.
- **Key points:** each with a bold label and a short explanation.
- **Steps:** when the reel explains a process.
- **Tools and links:** a table of Name | Link | Status. Each status is
  `verified (official)`, `verified`, `needs review`, or `from the reel`.
- **Graphs, Claims, Sources and papers:** when the reel has them.
- **Agent notes:** anything that could not be checked, and open questions.
- **Transcript:** the full speech text, folded under a toggle.

Anything the AI could not confirm is marked **needs review**. Check those before you rely on them.

## Requirements

- Windows, macOS, or Linux
- Python 3.12 or newer
- [ffmpeg](https://ffmpeg.org/) installed and available on your PATH
- Accounts and keys:
  - A Telegram bot token (from @BotFather) and your numeric Telegram user ID
  - A Groq API key (transcription and analysis, free tier)
  - A Notion integration token
  - An Exa API key (web research, optional but needed for the links table)

## Setup

1. Get the project folder and open a terminal in it.
2. Create a virtual environment and install the project:

   ```
   python -m venv .venv
   .venv\Scripts\activate            (Windows)
   source .venv/bin/activate         (macOS and Linux)
   pip install -e ".[dev]"
   ```

3. Copy the settings template and fill it in:

   ```
   copy .env.example .env            (Windows)
   cp .env.example .env              (macOS and Linux)
   ```

   Open `.env` and set your keys. Never share this file or commit it.

4. Create the Notion connection:
   - In Notion, create an integration and copy its token into `NOTION_TOKEN`.
   - Open the Notion page where reports should go, choose **Connections**, and add the integration.
   - Put that page's ID in `NOTION_PARENT_PAGE_ID`. Leave `NOTION_DATABASE_ID` empty.
     Jack Sparrow creates the "Jack Sparrow Reports" database under that page.

5. Check your Groq chat model:

   ```
   python -m app groq-check
   ```

   It lists the models your key can use. If the chat call fails, set
   `JACK_SPARROW_GROQ_CHAT_MODEL` in `.env` to one of the listed models
   (for example `openai/gpt-oss-120b`), then run the check again.

6. Start the bot:

   ```
   python -m app bot
   ```

   Leave this window open. Then send your bot a reel link in Telegram.

## Using the bot

- Send an Instagram reel link (`instagram.com/reel/...`, `/p/...`, or a share link).
- You get progress messages, then a report link in Notion.
- Sending the same reel again does not create a duplicate. If the last attempt
  failed, sending it again retries it.
- Only public reels work. Private or removed reels show a short reason.

## Commands

| Command | What it does |
| --- | --- |
| `python -m app` | Create or update the local database, then exit |
| `python -m app bot` | Run the Telegram bot |
| `python -m app groq-check` | List Groq models and test the chat model |
| `python -m app notion-check` | Show the status of the Notion database (needs `NOTION_DATABASE_ID`) |
| `python -m app text-report FILE` | Analyze a plain text file and save it as a report |

`text-report` is useful for text that is not a reel, such as a post you want
summarized. The report has no reel link.

## Where your data is

Everything is stored in the `data` folder (change it with `JACK_SPARROW_DATA_DIR`):

- `jack_sparrow.db`: the job list and status of each reel
- `jobs/<job id>/`: the transcript, the report (`report.json`), the community post (`post.txt`),
  and the reel's public caption and creator (`meta.json`)
- `text-reports/`: reports from `text-report`
- `notion_database_id.txt`: the ID of the Notion database Jack Sparrow created

Downloaded audio is deleted after it has been transcribed. Video is never downloaded.
If a job fails partway, its leftover audio is not cleaned up yet. A cleanup
step is planned (see `docs/Phases.md`, Phase 6).

## Troubleshooting

| Problem | What to do |
| --- | --- |
| `Configuration error: ...` | A key is missing or malformed in `.env`. The message names it. |
| "This reel is private or needs a login" | Only public reels can be processed. |
| "Instagram is limiting requests" | Wait a while, then send the link again. |
| "Could not save to Notion" | Run `python -m app notion-check`. Check that the integration is connected to the parent page. |
| Analysis fails with a 404 | The Groq chat model is not available to your key. Set `JACK_SPARROW_GROQ_CHAT_MODEL` (see step 5). |
| Links table shows "no link found" | Add an `EXA_API_KEY`. Without it, no web research runs. |
| Bot does not reply | Check `TELEGRAM_OWNER_ID` is your numeric ID, not your username. |

Developers: see [docs/Developer.md](docs/Developer.md) for how the code is organized.
