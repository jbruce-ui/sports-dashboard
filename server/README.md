# Sports MCP Server

FastAPI + FastAPI-MCP server wrapping TheSportsDB. Provides 18 MCP tools for querying sports fixtures, scores, standings, and managing favorite teams. Uses DuckDB for local caching.

## Quick Start

```bash
cd sports-mcp-server
pip install fastapi uvicorn fastapi-mcp duckdb httpx python-dotenv
python3 main.py
```

Server runs on `http://localhost:8900`. MCP endpoint at `/mcp`.

## API Key

Uses TheSportsDB free tier (key `3` for dev). For production, get a key at thesportsdb.com and update `.env`.

## MCP Tools

| Tool | Description |
|------|-------------|
| `search_teams` | Find teams by name |
| `search_leagues` | Find leagues by sport |
| `search_leagues_by_country` | Find leagues by country + sport |
| `get_teams_in_league` | All teams in a league |
| `get_next_fixtures_team` | Next 5 games for a team |
| `get_next_fixtures_league` | Upcoming games in a league |
| `get_last_results_team` | Last 5 results for a team |
| `get_last_results_league` | Recent results in a league |
| `get_fixtures_by_date` | All games on a date |
| `get_fixtures_by_round` | Games in a round/week |
| `get_event_details` | Full details for a game |
| `get_standings` | League standings table |
| `add_favorite_team` | Save a favorite team |
| `remove_favorite_team` | Remove a favorite |
| `list_favorite_teams` | List favorites |
| `get_favorites_upcoming` | Upcoming for all favorites |
| `get_favorites_results` | Results for all favorites |
| `query_cached_events` | Search local DuckDB cache |

## Connecting from Claude Code

Add to your MCP config:
```json
{
  "mcpServers": {
    "sports": {
      "url": "http://localhost:8900/mcp"
    }
  }
}
```
