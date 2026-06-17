# LinkedIn Content Creation Agent

An AI agent that generates LinkedIn posts in a trained writing style, built for the NB Media AI Agent assignment. It uses **RAG (Retrieval-Augmented Generation)** over a corpus of real reference posts instead of fine-tuning — fully free-tier, fully local except for two API calls (Gemini + Tavily).

## Overview

Instead of fine-tuning a model on someone's writing (expensive, slow, and overkill for a style this distinctive), this agent:

1. Stores real reference posts locally and embeds them into a vector database (ChromaDB).
2. At generation time, retrieves the posts most relevant to the new topic.
3. Feeds those posts to Gemini as **style examples** inside the prompt, asking it to write something new in the same voice.

This is the same pattern production content tools use ("few-shot style transfer via retrieval"), and it has two big advantages over fine-tuning for this use case: it costs nothing beyond API calls, and the style updates instantly the moment you add a new reference post — no retraining required.

## Features

| Assignment requirement | Implemented as |
|---|---|
| Style training | `ingest.py` embeds reference posts into ChromaDB; retrieval happens at generation time |
| User Input Workflow | "User Input Workflow" tab in `app.py` — topic / audience / goal form |
| Auto-Research Workflow | "Research & Generate" tab — Tavily search feeds Gemini fresh context |
| Output: post, hook, body, CTA, hashtags | All returned as structured JSON, rendered separately in the UI |
| Bonus: image idea | `image_idea` field in every generation |
| Bonus: carousel idea + thumbnail text | `carousel_idea` and `thumbnail_text` fields |

## Architecture

```
                     ┌────────────────────┐
  (optional)         │  scrape_posts.py    │
  LinkedIn  ────────► │  (Playwright)      │
                     └─────────┬──────────┘
                               │ writes
                               ▼
                     data/raw_posts.json
                     (data/sample_posts.json
                      used as fallback)
                               │
                               ▼
                     ┌────────────────────┐
                     │     ingest.py       │   Gemini Embeddings
                     │  load → clean →     │ ◄───────────────────
                     │  embed → store      │
                     └─────────┬──────────┘
                               ▼
                        ┌─────────────┐
                        │  ChromaDB   │  (chroma_db/, persisted locally)
                        └──────┬──────┘
                               │ similarity_search()
                               ▼
                     ┌────────────────────┐    Tavily Search API
                     │  generate_post.py   │ ◄─── (Auto-Research mode only)
                     │  retrieve → prompt → │
                     │  Gemini → parse JSON │ ◄─── Gemini Chat
                     └─────────┬──────────┘
                               ▼
                     ┌────────────────────┐
                     │      app.py         │
                     │   (Streamlit UI)    │
                     └────────────────────┘
```

## Project Structure

```
linkedin-agent/
├── app.py                 # Streamlit UI — run this
├── config.py               # Centralized env var / path / model config
├── scrape_posts.py         # Optional: Playwright LinkedIn scraper
├── ingest.py                # Embeds posts into ChromaDB
├── generate_post.py        # Core RAG generation logic
├── requirements.txt
├── .env.example
├── data/
│   └── sample_posts.json   # Placeholder reference posts (see note below)
└── chroma_db/               # Created automatically by ingest.py
```

> **Important note on `data/sample_posts.json`:** these are original example posts written to demonstrate a generic "founder thought-leadership" LinkedIn voice (short punchy lines, a hook, a personal anecdote, a closing question) so the full pipeline can be run and demoed immediately. They are **not** actually scraped from any real LinkedIn profile. For a real deployment, replace this file with genuine reference posts — either by running `scrape_posts.py` against an account you control, or by manually copying 10–20 real posts into `data/raw_posts.json` using the same JSON shape.

## Installation

### 1. Clone / unzip the project and enter the folder
```bash
cd linkedin-agent
```

### 2. Create a virtual environment (Python 3.11 recommended; 3.10–3.12 also work)
```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. (Only if you plan to scrape) Install Playwright's browser binary
```bash
playwright install chromium
```

### 5. Set up your `.env` file
```bash
copy .env.example .env        # Windows
# cp .env.example .env         # macOS/Linux
```
Then open `.env` and fill in your keys (see below for how to get them).

## Getting Your API Keys

### Gemini API key (required, free tier)
1. Go to https://aistudio.google.com/app/apikey
2. Sign in with a Google account.
3. Click "Create API key" and copy it into `GEMINI_API_KEY` in your `.env` file.

### Tavily API key (required only for Research & Generate mode, free tier)
1. Go to https://app.tavily.com/
2. Sign up for a free account.
3. Copy your API key from the dashboard into `TAVILY_API_KEY` in your `.env` file.

## Running It

### Step 1 — Build the knowledge base
```bash
python ingest.py
```
This reads `data/raw_posts.json` if present, otherwise falls back to `data/sample_posts.json`, embeds every post with Gemini's embedding model, and stores the vectors in `chroma_db/`.

### Step 2 — Launch the app
```bash
streamlit run app.py
```
This opens a browser tab at `http://localhost:8501`. From there:
- Use the **User Input Workflow** tab for the topic / audience / goal form.
- Use the **Research & Generate** tab to have the agent research the topic via Tavily before writing.
- Use the sidebar "Rebuild knowledge base" button any time you update your reference posts — no need to restart the app.

### (Optional) Step 0 — Scrape real reference posts first
```bash
python scrape_posts.py
```
Requires `LINKEDIN_EMAIL`, `LINKEDIN_PASSWORD`, and `LINKEDIN_PROFILE_URL` in `.env`. **Read the warning at the top of `scrape_posts.py` before running this** — LinkedIn's ToS prohibit automated scraping, and this should only be run against an account you own or have explicit permission to automate, at low volume.

## Screenshots

> _Add screenshots here before submitting:_
> - `screenshots/user_input_workflow.png` — the User Input tab with a generated post
> - `screenshots/research_workflow.png` — the Research & Generate tab showing the research summary
> - `screenshots/sidebar.png` — the sidebar status checks and rebuild button

## Troubleshooting

**"Missing required environment variable(s): GEMINI_API_KEY"**
Your `.env` file is missing or the key wasn't filled in. Confirm `.env` (not `.env.example`) exists in the project root and contains a real key.

**`ingest.py` fails with a 403/permission error from Google**
Your Gemini API key may not have the Generative Language API enabled, or you've hit the free-tier rate limit. Wait a minute and retry, or generate a fresh key.

**Gemini returns text that fails JSON parsing**
This is rare but possible with any LLM. `generate_post.py` already strips common markdown code fences defensively. If it still fails, just click "Generate" again — temperature is set to 0.7, so retries usually succeed. Lowering `temperature` in `get_llm()` (in `generate_post.py`) makes output more consistently formatted at the cost of some creativity.

**`scrape_posts.py` hangs or throws a login error**
LinkedIn most likely showed a security checkpoint (CAPTCHA / "verify it's you") that the script cannot solve. Log in manually once in a normal browser from the same network/device, then retry — or skip scraping entirely and populate `data/raw_posts.json` manually.

**ChromaDB telemetry error messages in the console**
Harmless. ChromaDB attempts to send anonymous usage telemetry and occasionally logs a benign error if that fails; it does not affect functionality.

**Streamlit says "Port 8501 is already in use"**
Run `streamlit run app.py --server.port 8502` instead, or stop the other Streamlit process.

## Future Improvements (Beyond This POC)

- Multi-author style profiles (swap between different trained voices)
- A feedback loop where the user edits a generated post and that edit is stored as a new high-quality reference example
- Sentiment/engagement scoring on reference posts so retrieval favors a person's best-performing style, not just their most topically similar post
- Batch generation (generate 5 post variants at once and let the user pick)

---

## One-Week Improvements Plan

If given a full week to build this properly (beyond a proof of concept), here is what I would add, with tech stack and implementation approach for each.

### 1. LinkedIn Auto-Posting

**Feature:** Once a post is generated and approved, publish it directly to LinkedIn without copy-pasting.

**Tech stack:** LinkedIn's official `Share on LinkedIn` / Marketing API (`w_member_social` scope), OAuth 2.0, Python `requests`, or an `n8n` HTTP node if moving the back end to a no-code flow.

**Implementation approach:** Add an OAuth 2.0 flow so the user authorizes the app once; store the resulting access/refresh token securely (encrypted at rest, not in `.env` in plaintext for a real product). Add a "Publish" button in `app.py` that POSTs the approved `full_post` text plus any uploaded image to LinkedIn's `/v2/ugcPosts` endpoint. Handle token refresh and rate limits, and add a confirmation step so nothing posts without explicit human approval — this assignment is about drafting content, not autonomous posting.

### 2. Content Calendar

**Feature:** Let the user schedule generated posts for specific future dates/times instead of posting immediately, and see an overview of what's queued.

**Tech stack:** Google Calendar API (for a visual calendar the user already lives in) + a lightweight database (SQLite for a POC, Postgres for production) to store post content, status (`draft`/`scheduled`/`published`), and scheduled timestamp. A scheduled job (APScheduler, or a cron-triggered cloud function) to fire the actual post at the scheduled time via the Auto-Posting integration above.

**Implementation approach:** Add a "Schedule" button next to "Publish" in the UI that opens a date/time picker, writes a row to the database, and creates a matching Google Calendar event (for visibility) via the Calendar API. A background scheduler polls the database every few minutes for posts whose time has arrived and triggers publishing.

### 3. Analytics Dashboard

**Feature:** Track which generated posts perform best (likes, comments, shares, follower growth) and feed that back into which reference posts get prioritized during retrieval.

**Tech stack:** LinkedIn's analytics endpoints (where available for the account) or a manual metrics-entry form as a fallback, stored in the same SQLite/Postgres database, visualized in a Streamlit dashboard page using `plotly` or `recharts`-style charts.

**Implementation approach:** After a post is published, periodically pull its engagement stats and store them. Build a second Streamlit page showing trend lines per post and per topic. Use this data to weight ChromaDB retrieval — for example, by boosting the `likes` metadata field already present in the post schema so future generations lean more heavily on what's proven to work, not just what's topically similar.

### 4. Multi-Platform Posting

**Feature:** Repurpose the same generated content for Twitter/X, Instagram captions, or a newsletter, with format-appropriate adjustments (character limits, hashtag conventions, tone).

**Tech stack:** Platform-specific APIs (X API v2, Meta Graph API for Instagram), plus a small "platform adapter" layer in Python so `generate_post.py`'s core output feeds multiple formatters.

**Implementation approach:** Add a `platform` parameter to the generation prompt so Gemini adapts length/tone per platform, or do a cheaper second-pass transformation: generate the LinkedIn version first (long-form, the "source of truth"), then ask Gemini to condense/reformat it per platform rather than regenerating from scratch — this keeps brand voice consistent across platforms instead of drifting.

### 5. A/B Testing

**Feature:** Generate two or more variants of a post (different hooks, different CTAs) and systematically determine which performs better.

**Tech stack:** Same database as the Analytics Dashboard, plus a simple statistical significance check (e.g. a basic two-proportion z-test using `scipy.stats`) once enough engagement data has accumulated.

**Implementation approach:** Extend `generate_post_from_topic()` to optionally return N variants instead of one (same retrieved style examples, higher temperature, multiple LLM calls). Tag each published variant with a test ID. Once both variants have been live for a set period, pull engagement data and run the significance check; surface the winner (and why) in the Analytics Dashboard so future generations can learn which hook styles or CTA phrasing actually convert for this specific audience.
