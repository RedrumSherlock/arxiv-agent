# arxiv-agent
An AI agent to research latest arxiv papers and send digest to email or webhook 

## What does it do
This agent workflow will perform the following steps with one execution:
1. Use the public arxiv API to load the papers from the last X days, where X is configurable from the .env file
2. Based on the title and abstraction of each paper and the acceptance criteria defined by the user in the .env file, filter out the ones that are clearly not matching using LLM (mini version LLM)
3. For the rest of papers, give each one of them a score 
4. Pick the top MAX_ITEMS papers, for each one of them
    4a. web search the community feedback of these papers
    4b. download the paper from arxiv
    4c. combine the above information and give a final feedback on this paper using LLM (full/pro version LLM)
5. Send the digest of each paper as a list to the notification channel with the following format. The notification channel shall support email and webhook. For email it should use Brevo API.
    - Title
    - Summary (less than 100 words)
    - Authors (including the university/organiaztion)
    - Publish Date
    - Rating (a score from 1-100)
    - Rating justification (less than 100 words)
    - Comminity reputation (less than 100 words)



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
| `TRACE_BACK_DAYS` | 7 | Number of days to look back for papers |
| `SEARCH_TOPICS` | - | Comma-separated list of search topics |
| `ACCEPTANCE_CRITERIA` | - | Description of what papers to accept |
| `MAX_ITEMS` | 5 | Maximum number of papers in the final digest |
| `SCORE_THRESHOLD` | 50 | Minimum score (1-100) for a paper to be included |

### LLM Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_MINI` | gemini-2.5-flash | Model for filtering and scoring (faster/cheaper) |
| `MODEL_FULL` | gemini-3.0-pro-preview | Model for deep analysis (more capable) |
| `FILTER_BATCH_SIZE` | 10 | Number of papers per LLM call for filtering |
| `SCORER_BATCH_SIZE` | 10 | Number of papers per LLM call for scoring |

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