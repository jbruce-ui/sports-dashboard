import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from fastapi import FastAPI, Query
from fastapi_mcp import FastApiMCP
from db import init_db, get_connection
import espn_client as espn

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(
    title="Sports MCP Server",
    description="MCP-powered sports fixtures, scores, standings, and favorites tracker. Powered by ESPN.",
    version="2.0.0",
    lifespan=lifespan,
)


# ── Leagues ──────────────────────────────────────────────────────────

@app.get("/leagues", operation_id="list_leagues",
         summary="List all supported leagues",
         description="Returns all supported leagues with their keys. Use the key in other endpoints. Supports: NFL, NBA, MLB, NHL, EPL, MLS, La Liga, Bundesliga, Serie A, Ligue 1, Champions League.")
async def list_leagues():
    return espn.list_leagues()


# ── Search & Discovery ──────────────────────────────────────────────

@app.get("/search/teams", operation_id="search_teams",
         summary="Search for teams by name across all leagues",
         description="Search for teams by name across all supported leagues. Returns team ID, name, league. Use the team ID and league key with other endpoints.")
async def search_teams(name: str = Query(description="Team name to search for, e.g. 'Arsenal', 'Lakers', 'Yankees'")):
    return await espn.search_teams(name)


@app.get("/teams/{league_key}", operation_id="get_teams_in_league",
         summary="List all teams in a league",
         description="Get all teams in a specific league. League keys: nfl, nba, mlb, nhl, epl, mls, laliga, bundesliga, seriea, ligue1, ucl.")
async def teams_in_league(league_key: str):
    return await espn.get_teams(league_key)


# ── Scoreboard (today's / date's games) ─────────────────────────────

@app.get("/scoreboard/{league_key}", operation_id="get_scoreboard",
         summary="Get today's scoreboard for a league",
         description="Get current/today's games and scores for a league. Optionally pass a date for a specific day. Shows live scores, final results, and upcoming games.")
async def scoreboard(
    league_key: str,
    date: str = Query(default=None, description="Optional date YYYY-MM-DD, defaults to today"),
):
    events = await espn.get_scoreboard(league_key, date)
    _cache_events(events, league_key)
    return events


@app.get("/scoreboard", operation_id="get_all_scoreboards",
         summary="Get today's games across ALL leagues",
         description="Get all games happening today (or on a specific date) across every supported league. Great for a daily overview.")
async def all_scoreboards(
    date: str = Query(default=None, description="Optional date YYYY-MM-DD"),
):
    return await espn.get_scoreboard_multi(date)


# ── Team Schedule & Results ──────────────────────────────────────────

@app.get("/schedule/{league_key}/{team_id}", operation_id="get_team_schedule",
         summary="Get full season schedule for a team",
         description="Get the complete schedule (past results and upcoming fixtures) for a specific team in a league.")
async def team_schedule(league_key: str, team_id: str):
    return await espn.get_team_schedule(league_key, team_id)


@app.get("/fixtures/next/{league_key}/{team_id}", operation_id="get_next_fixtures_team",
         summary="Get upcoming fixtures for a team",
         description="Get upcoming (not yet played) games for a team. Returns dates, times, opponents, venues.")
async def next_fixtures_team(league_key: str, team_id: str):
    events = await espn.get_team_upcoming(league_key, team_id)
    _cache_events(events, league_key)
    return events


@app.get("/results/last/{league_key}/{team_id}", operation_id="get_last_results_team",
         summary="Get recent results for a team",
         description="Get the most recent completed games with scores for a team.")
async def last_results_team(
    league_key: str,
    team_id: str,
    limit: int = Query(default=5, description="Number of results to return"),
):
    events = await espn.get_team_results(league_key, team_id, limit)
    _cache_events(events, league_key)
    return events


# ── Standings ────────────────────────────────────────────────────────

@app.get("/standings/{league_key}", operation_id="get_standings",
         summary="Get league standings",
         description="Get current standings for a league. Shows wins, losses, points, etc.")
async def standings(league_key: str):
    return await espn.get_standings(league_key)


# ── Favorites ────────────────────────────────────────────────────────

@app.post("/favorites/add", operation_id="add_favorite_team",
          summary="Add a team to your favorites",
          description="Save a team to your favorites. Provide team_id, team_name, and league_key.")
async def add_favorite(
    team_id: str = Query(description="Team ID from search/teams results"),
    team_name: str = Query(description="Team name for display"),
    league_key: str = Query(description="League key, e.g. 'epl', 'nba'"),
):
    con = get_connection()
    con.execute(
        "INSERT OR REPLACE INTO favorite_teams (team_id, team_name, league_key) VALUES (?, ?, ?)",
        [team_id, team_name, league_key],
    )
    con.close()
    return {"status": "added", "team_id": team_id, "team_name": team_name, "league_key": league_key}


@app.delete("/favorites/remove/{team_id}", operation_id="remove_favorite_team",
            summary="Remove a team from favorites",
            description="Remove a team from your saved favorites list.")
async def remove_favorite(team_id: str):
    con = get_connection()
    con.execute("DELETE FROM favorite_teams WHERE team_id = ?", [team_id])
    con.close()
    return {"status": "removed", "team_id": team_id}


@app.get("/favorites", operation_id="list_favorite_teams",
         summary="List all your favorite teams",
         description="See all teams you've saved as favorites.")
async def list_favorites():
    con = get_connection()
    rows = con.execute("SELECT team_id, team_name, league_key, added_at FROM favorite_teams ORDER BY added_at").fetchall()
    con.close()
    return [{"team_id": r[0], "team_name": r[1], "league_key": r[2], "added_at": str(r[3])} for r in rows]


@app.get("/favorites/upcoming", operation_id="get_favorites_upcoming",
         summary="Get upcoming fixtures for all favorite teams",
         description="Fetch the next games for every team in your favorites list.")
async def favorites_upcoming():
    con = get_connection()
    rows = con.execute("SELECT team_id, team_name, league_key FROM favorite_teams").fetchall()
    con.close()
    results = {}
    for team_id, team_name, league_key in rows:
        try:
            events = await espn.get_team_upcoming(league_key, team_id)
            results[team_name] = events
            _cache_events(events, league_key)
        except Exception:
            results[team_name] = []
    return results


@app.get("/favorites/results", operation_id="get_favorites_results",
         summary="Get recent results for all favorite teams",
         description="Fetch recent results/scores for every team in your favorites list.")
async def favorites_results():
    con = get_connection()
    rows = con.execute("SELECT team_id, team_name, league_key FROM favorite_teams").fetchall()
    con.close()
    results = {}
    for team_id, team_name, league_key in rows:
        try:
            events = await espn.get_team_results(league_key, team_id)
            results[team_name] = events
            _cache_events(events, league_key)
        except Exception:
            results[team_name] = []
    return results


# ── Local DB Queries ─────────────────────────────────────────────────

@app.get("/db/events", operation_id="query_cached_events",
         summary="Query locally cached events",
         description="Search the local DuckDB cache of events. Filter by team name, date range, etc.")
async def query_cached_events(
    team: str = Query(default=None, description="Filter by team name (partial match)"),
    league: str = Query(default=None, description="Filter by league key"),
    date_from: str = Query(default=None, description="Start date YYYY-MM-DD"),
    date_to: str = Query(default=None, description="End date YYYY-MM-DD"),
    limit: int = Query(default=50, description="Max results"),
):
    con = get_connection()
    query = "SELECT * FROM events WHERE 1=1"
    params = []
    if team:
        query += " AND (home_team ILIKE ? OR away_team ILIKE ?)"
        params += [f"%{team}%", f"%{team}%"]
    if league:
        query += " AND league_id = ?"
        params.append(league)
    if date_from:
        query += " AND event_date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND event_date <= ?"
        params.append(date_to)
    query += " ORDER BY event_date DESC LIMIT ?"
    params.append(limit)
    rows = con.execute(query, params).fetchdf()
    con.close()
    return rows.to_dict(orient="records")


# ── Helpers ──────────────────────────────────────────────────────────

def _cache_events(events: list[dict], league_key: str = ""):
    if not events:
        return
    con = get_connection()
    for e in events:
        if not e or not e.get("id"):
            continue
        con.execute("""
            INSERT OR REPLACE INTO events
            (id, name, league_id, season, round, home_team_id, home_team,
             away_team_id, away_team, home_score, away_score, event_date,
             event_time, venue, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            e.get("id"), e.get("name"), league_key,
            "", "", e.get("home_team_id"),
            e.get("home_team"), e.get("away_team_id"), e.get("away_team"),
            e.get("home_score"), e.get("away_score"), e.get("date"),
            e.get("time"), e.get("venue"), e.get("status"),
        ])
    con.close()


# ── MCP Setup ────────────────────────────────────────────────────────

mcp = FastApiMCP(
    app,
    name="Sports MCP Server",
    description="Query sports fixtures, scores, standings, and manage favorite teams. Powered by ESPN.",
)
mcp.mount_http()


if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8900"))
    uvicorn.run(app, host=host, port=port)
