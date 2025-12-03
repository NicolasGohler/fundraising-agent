# Fundraising Agent

Automated agent that collects fundraising data from CryptoRank and RootData, extracts team member information, enriches with email addresses via Apollo.io, and sends results to Slack.

## Features

- **Multi-source data collection**: CryptoRank funding rounds and RootData fundraising
- **Team member extraction**: From project team pages and Apollo.io API
- **Website extraction**: Automatically finds company websites
- **Slack integration**: Sends results and notifications to Slack
- **GitHub Actions**: Automated weekly runs every Monday
- **Detailed source tracking**: Comprehensive metadata about data sources

## Data Sources

### Project Sources
- **CryptoRank Funding Rounds**: `cryptorank_funding_rounds`
- **RootData Fundraising**: `rootdata_fundraising`

### Team Member Sources
- **CryptoRank Team Pages**: `cryptorank_team_page`
- **Apollo API**: `apollo_api`
- **Combined Sources**: `cryptorank_team_page + apollo_api`

## Setup

### Local Development

1. Clone the repository
2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```
4. Set environment variables:
   ```bash
   export APOLLO_API_KEY="your_apollo_api_key"
   export SLACK_BOT_TOKEN="your_slack_bot_token"
   export SLACK_CHANNEL="your_slack_channel_id"
   ```
5. Run the script:
   ```bash
   python fundraising.py
   ```

### GitHub Actions Setup

1. Add the following secrets to your GitHub repository:
   - `APOLLO_API_KEY`: Your Apollo.io API key
   - `SLACK_BOT_TOKEN`: Your Slack bot token
   - `SLACK_CHANNEL`: Your Slack channel ID (e.g., C09CKTZ61DK)

2. The workflow will automatically run every Monday at 9 AM UTC

## Output

The script generates:
- **JSON file**: Complete data with all metadata
- **CSV file**: Formatted for easy analysis
- **Slack notification**: Success/failure notifications
- **GitHub artifacts**: Uploaded results for each run

## Data Schema

Each person record includes:
- `name`: Person's name
- `role`: Job title/role
- `linkedin_url`: LinkedIn profile URL
- `email`: Email address (enriched via Apollo.io bulk enrichment API)
- `source`: Data source (e.g., `apollo_api`, `cryptorank_team_page`)
- `source_url`: URL of the data source
- `source_type`: Type of source (e.g., `people_database`, `project_team_page`)
- `apollo_search_method`: How Apollo was searched (`domain` or `company_name`)
- `project`: Project name
- `project_url`: Project URL
- `project_source`: Where the project was found
- `project_source_url`: URL of the project source
- `project_source_type`: Type of project source
- `company_website`: Company website URL
- `company_domain`: Company domain

## Requirements

- Python 3.9+
- Playwright with Chromium
- Apollo.io API key
- Slack bot with appropriate permissions

## License

MIT License