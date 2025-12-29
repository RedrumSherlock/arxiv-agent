# arxiv-agent
An AI agent to research latest arxiv papers and send digest to email or webhook 

## What does it do
This agent workflow will perform the following steps with one execution:
1. Use the public arxiv API to load papers published within a configurable date range (e.g., 30 to 23 days ago) to allow time for community feedback
2. (LLM based) Based on the title and abstraction of each paper and the acceptance criteria defined in the .env file, filter out the ones that are clearly not matching using LLM
3. (LLM based) For the rest of papers, use LLM to give each one of them a score 
4. Pick the top MAX_ITEMS papers, for each one of them
    4a. web search the community feedback of these papers
    4b. download the paper from arxiv
    4c. (LLM based) combine the above information and give a final feedback on this paper using LLM
5. Send the digest of each paper as a list to the notification channel like email or Google Chat webhook, including title, summary, authors, publication date, rating, community feedback, etc.


## Configuration
Run `cp .env.example .env` and configure the .env file.

### Required Settings

| Variable | Description |
|----------|-------------|
| `API_KEY` | API key for your LLM endpoint (LiteLLM, Azure OpenAI, etc.) |
| `API_ENDPOINT` | OpenAI-compatible API endpoint URL |

### Search Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `TRACE_BACK_DAYS_START` | 30 | Start of date range (days ago) |
| `TRACE_BACK_DAYS_END` | 23 | End of date range (days ago) |
| `SEARCH_TOPICS` | - | Comma-separated list of search topics |
| `ACCEPTANCE_CRITERIA` | - | Description of what papers to accept |
| `MAX_ITEMS` | 5 | Maximum number of papers in the final digest |
| `SCORE_THRESHOLD` | 50 | Minimum score (1-100) for a paper to be included |

> **Example:** `TRACE_BACK_DAYS_START=30` and `TRACE_BACK_DAYS_END=23` selects papers published 30-23 days ago (7-day window with 23-day buffer for community feedback)

### LLM Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_FILTER` | gemini-3-flash | Model for filtering papers |
| `MODEL_SCORER` | gemini-3-flash | Model for scoring papers |
| `MODEL_ANALYZER` | gemini-3-pro | Model for deep analysis |
| `FILTER_BATCH_SIZE` | 100 | Number of papers per LLM call for filtering |
| `SCORER_BATCH_SIZE` | 50 | Number of papers per LLM call for scoring |

### Web Search (Optional)

| Variable | Description |
|----------|-------------|
| `TAVILY_API_KEY` | Tavily API key for searching community feedback |

### Notification - Email via Brevo (Optional)

| Variable | Description |
|----------|-------------|
| `EMAIL_ADDRESS_LIST` | Comma-separated list of recipient emails |
| `BREVO_API_KEY` | Brevo API key |
| `BREVO_SENDER_EMAIL` | Sender email address |
| `BREVO_SENDER_NAME` | Sender display name (default: "Arxiv Agent") |

### Notification - Webhook (Optional)

| Variable | Description |
|----------|-------------|
| `WEBHOOK_URL` | Webhook URL (supports Google Chat webhooks)

## Prompt tuning
Tune the prompts for the agent under the prompts/ folder.

## Get Started
Simply run with 
```
uv run python run.py
```