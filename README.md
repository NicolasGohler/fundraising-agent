# Fundraising Agent

Weekly investor prospecting engine for Web3 fundraising cycles.

Pulls hiring, funding, and competitor activity signals from Apollo.io and CryptoRank, enriches team contacts with emails and Telegram handles, and delivers a ranked lead list to Slack every Monday via GitHub Actions.

Built at [MPM Labs](https://mpmlabs.xyz) to power outbound fundraising motions for portfolio companies. Part of the signal infrastructure behind 7-figure pipeline generation.

## How it works

1. Scrapes recent fundraising rounds from CryptoRank and RootData
2. Extracts team members and enriches emails via Apollo.io bulk enrichment
3. Resolves Telegram usernames for direct outreach
4. Pushes structured results to Slack and uploads artifacts to GitHub

## Setup

Add these to your GitHub repository secrets:

```
APOLLO_API_KEY        Apollo.io API key
SLACK_BOT_TOKEN       Slack bot token
SLACK_CHANNEL         Slack channel ID
LINAUTO_API_KEY       Optional: Telegram username resolution
PROXY_SERVER          Optional: residential proxy
```

The workflow runs every Monday at 9 AM UTC.

## Stack

Python · Apollo.io · CryptoRank · Telethon · Slack SDK · GitHub Actions
