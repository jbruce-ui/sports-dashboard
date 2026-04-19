# Sports MCP Client

Interactive CLI that queries the Sports MCP Server and can push games to Google Calendar.

## Quick Start

```bash
cd sports-mcp-client
pip install httpx rich google-auth google-auth-oauthlib google-api-python-client
python3 client.py
```

## Google Calendar Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project, enable Google Calendar API
3. Create OAuth2 credentials (Desktop app)
4. Download as `credentials.json` in this directory
5. First `cal add` command will open a browser for auth

## Commands

```
search team Arsenal          # Find teams
search league Soccer         # Find leagues
next team 133604             # Next fixtures
last team 133604             # Recent results
standings 4328 2025-2026     # League table
fav add 133604 Arsenal       # Add favorite
fav next                     # Upcoming for all favorites
cal add 1                    # Add game #1 from last query to calendar
cal list                     # Show sports events on calendar
```
