# Fundraising Lead Scraper

Automated weekly scraper that collects fundraising data from CryptoRank, RootData, and Apollo.io, then uploads the results to Slack.

## Features

- **Multi-source data collection**: CryptoRank, RootData, and Apollo.io
- **Automatic team member extraction** with LinkedIn profiles
- **CTO filtering** (excludes CTOs as requested)
- **Dated folder organization** (e.g., `Fundraises - 10-13/`)
- **Slack integration** with file uploads
- **Weekly automation** via GitHub Actions

## Schedule

Runs automatically every **Monday at 9 AM UTC** via GitHub Actions.

## Output

- `funding_data.csv` - Person-centric CSV with LinkedIn profiles
- `funding_data.json` - Raw JSON data
- Organized in dated folders: `Fundraises - MM-DD/`

## Setup

1. **Fork this repository**
2. **Add secrets** in GitHub repository settings:
   - `APOLLO_API_KEY`: Your Apollo.io API key
   - `SLACK_BOT_TOKEN`: Your Slack bot token
3. **Enable GitHub Actions** in repository settings

## Manual Run

You can trigger the workflow manually:
1. Go to **Actions** tab
2. Select **Weekly Fundraising Scraper**
3. Click **Run workflow**

## Data Sources

- **CryptoRank**: Project funding rounds and team pages
- **RootData**: Additional fundraising projects
- **Apollo.io**: Team member enrichment and LinkedIn profiles

## Output Format

Each person includes:
- `name` - Team member name
- `role` - Job title (CEO, CFO, Co-Founder, etc.)
- `linkedin_url` - LinkedIn profile URL
- `source` - Data source (cryptorank, rootdata + apollo, etc.)
- `project` - Company name
- `project_url` - Project page URL
