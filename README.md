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
Run `cp .env.example .env` and configure the .env file. Some key configuration items that must be changed:
- TRACE_BACK_DAYS
- SEARCH_TOPICS
- ACCEPTANCE_CRITERIA
- MAX_ITEMS
- SCORE_THRESHOLD
- OPENAI_API_KEY_MINI
- OPENAI_API_KEY

Either email address list or the webhook URL shall be configured
- EMAIL_ADDRESS_LIST
- BREVO_API_KEY
- WEBHOOK_URL

## Prompt tuning
Tune the prompts for the agent under the prompts/ folder.

## Get Started
Simply run with 
```
uv run python run.py
```