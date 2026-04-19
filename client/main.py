import json
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

import anthropic
from fastapi import FastAPI, Query
from fastapi.requests import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi_mcp import FastApiMCP
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client
from pydantic import BaseModel
import httpx

SPORTS_SERVER = os.getenv("SPORTS_SERVER_URL", "http://localhost:8900")
MCP_SERVER_URL = f"{SPORTS_SERVER}/mcp"

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

_mcp_session: ClientSession | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _mcp_session
    async with streamable_http_client(MCP_SERVER_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            _mcp_session = session
            tools = await session.list_tools()
            print(f"Connected to Sports MCP Server — {len(tools.tools)} tools: {[t.name for t in tools.tools]}")
            yield
    _mcp_session = None


app = FastAPI(
    title="Sports Dashboard",
    description="Personal sports dashboard — fixtures, scores, standings, favorites, and calendar integration",
    version="2.0.0",
    lifespan=lifespan,
)


# ── HTML routes ──────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")

@app.get("/search", response_class=HTMLResponse, include_in_schema=False)
async def search_page(request: Request):
    return templates.TemplateResponse(request, "search.html")

@app.get("/standings", response_class=HTMLResponse, include_in_schema=False)
async def standings_page(request: Request):
    return templates.TemplateResponse(request, "standings.html")

@app.get("/calendar", response_class=HTMLResponse, include_in_schema=False)
async def calendar_page(request: Request):
    return templates.TemplateResponse(request, "calendar.html")

@app.get("/chat", response_class=HTMLResponse, include_in_schema=False)
async def chat_page(request: Request):
    return templates.TemplateResponse(request, "chat.html")


# ── Proxy helpers ────────────────────────────────────────────────────

async def _proxy_get(path: str, params: dict = None):
    async with httpx.AsyncClient(base_url=SPORTS_SERVER, timeout=30) as c:
        resp = await c.get(path, params=params)
        resp.raise_for_status()
        return resp.json()

async def _proxy_post(path: str, params: dict = None):
    async with httpx.AsyncClient(base_url=SPORTS_SERVER, timeout=15) as c:
        resp = await c.post(path, params=params)
        resp.raise_for_status()
        return resp.json()

async def _proxy_delete(path: str):
    async with httpx.AsyncClient(base_url=SPORTS_SERVER, timeout=15) as c:
        resp = await c.delete(path)
        resp.raise_for_status()
        return resp.json()


# ── API routes ───────────────────────────────────────────────────────

@app.get("/api/leagues", tags=["api"], operation_id="list_leagues",
         summary="List all supported leagues",
         description="Returns all supported leagues: NFL, NBA, MLB, NHL, EPL, MLS, La Liga, Bundesliga, Serie A, Ligue 1, Champions League.")
async def api_leagues():
    return await _proxy_get("/leagues")


@app.get("/api/search/teams", tags=["api"], operation_id="search_teams",
         summary="Search for teams by name",
         description="Find teams by name across all leagues. Examples: 'Arsenal', 'Lakers', 'Yankees', 'Patriots'.")
async def api_search_teams(name: str = Query(description="Team name to search")):
    return await _proxy_get("/search/teams", {"name": name})


@app.get("/api/teams/{league_key}", tags=["api"], operation_id="teams_in_league",
         summary="List all teams in a league",
         description="Get every team in a league. League keys: nfl, nba, mlb, nhl, epl, mls, laliga, bundesliga, seriea, ligue1, ucl.")
async def api_teams_in_league(league_key: str):
    return await _proxy_get(f"/teams/{league_key}")


@app.get("/api/scoreboard/{league_key}", tags=["api"], operation_id="get_scoreboard",
         summary="Today's scoreboard for a league",
         description="Get live scores, final results, and upcoming games for today (or a specific date).")
async def api_scoreboard(
    league_key: str,
    date: str = Query(default=None, description="Optional date YYYY-MM-DD"),
):
    params = {"date": date} if date else None
    return await _proxy_get(f"/scoreboard/{league_key}", params)


@app.get("/api/scoreboard", tags=["api"], operation_id="get_all_scoreboards",
         summary="Today's games across ALL leagues",
         description="Get all games happening today across every supported league.")
async def api_all_scoreboards(
    date: str = Query(default=None, description="Optional date YYYY-MM-DD"),
):
    params = {"date": date} if date else None
    return await _proxy_get("/scoreboard", params)


@app.get("/api/fixtures/next/{league_key}/{team_id}", tags=["api"], operation_id="next_fixtures_team",
         summary="Upcoming fixtures for a team",
         description="Get upcoming games for a team. Requires league_key (e.g. 'epl') and team_id.")
async def api_next_team(league_key: str, team_id: str):
    return await _proxy_get(f"/fixtures/next/{league_key}/{team_id}")


@app.get("/api/results/last/{league_key}/{team_id}", tags=["api"], operation_id="last_results_team",
         summary="Recent results for a team",
         description="Get last completed games with scores for a team.")
async def api_last_team(league_key: str, team_id: str):
    return await _proxy_get(f"/results/last/{league_key}/{team_id}")


@app.get("/api/standings/{league_key}", tags=["api"], operation_id="get_standings",
         summary="League standings",
         description="Get current standings for a league. Shows W/D/L, points, etc.")
async def api_standings(league_key: str):
    return await _proxy_get(f"/standings/{league_key}")


# ── Favorites ────────────────────────────────────────────────────────

@app.get("/api/favorites", tags=["api"], operation_id="list_favorites",
         summary="List favorite teams",
         description="Get all teams saved as favorites.")
async def api_list_favorites():
    return await _proxy_get("/favorites")


@app.post("/api/favorites/add", tags=["api"], operation_id="add_favorite",
          summary="Add a team to favorites",
          description="Save a team to your favorites. Requires team_id, team_name, and league_key.")
async def api_add_favorite(
    team_id: str = Query(description="Team ID"),
    team_name: str = Query(description="Team name"),
    league_key: str = Query(description="League key, e.g. 'epl', 'nba'"),
):
    return await _proxy_post("/favorites/add", {"team_id": team_id, "team_name": team_name, "league_key": league_key})


@app.delete("/api/favorites/{team_id}", tags=["api"], operation_id="remove_favorite",
            summary="Remove a team from favorites",
            description="Remove a team from your saved favorites.")
async def api_remove_favorite(team_id: str):
    return await _proxy_delete(f"/favorites/remove/{team_id}")


@app.get("/api/favorites/upcoming", tags=["api"], operation_id="favorites_upcoming",
         summary="Upcoming fixtures for all favorites",
         description="Get upcoming games for every team in your favorites.")
async def api_favorites_upcoming():
    return await _proxy_get("/favorites/upcoming")


@app.get("/api/favorites/results", tags=["api"], operation_id="favorites_results",
         summary="Recent results for all favorites",
         description="Get recent results for every team in your favorites.")
async def api_favorites_results():
    return await _proxy_get("/favorites/results")


# ── Calendar ─────────────────────────────────────────────────────────

class CalendarEvent(BaseModel):
    summary: str
    start_date: str
    start_time: str | None = None
    venue: str | None = None
    description: str | None = None
    duration_hours: float = 2.5


@app.post("/api/calendar/add", tags=["api"], operation_id="calendar_add_game",
          summary="Add a game to Google Calendar",
          description="Create a Google Calendar event for a game with a 30-minute reminder.")
async def api_calendar_add(event: CalendarEvent):
    from calendar_service import add_game_to_calendar
    return add_game_to_calendar(
        summary=event.summary,
        start_date=event.start_date,
        start_time=event.start_time,
        venue=event.venue,
        description=event.description,
        duration_hours=event.duration_hours,
    )


@app.get("/api/calendar/list", tags=["api"], operation_id="calendar_list_events",
         summary="List sports events on calendar",
         description="Show sports events on your Google Calendar for a date range.")
async def api_calendar_list(
    date_from: str = Query(default=None, description="Start date YYYY-MM-DD"),
    date_to: str = Query(default=None, description="End date YYYY-MM-DD"),
):
    from calendar_service import list_sports_events_on_calendar
    return list_sports_events_on_calendar(date_from, date_to)


# ── Chat with Sports Data ───────────────────────────────────────

CHAT_SYSTEM_PROMPT = (
    "You are a sports assistant with access to live sports data tools. "
    "You can look up scores, fixtures, standings, team info, and favorites "
    "across NFL, NBA, MLB, NHL, EPL, MLS, La Liga, Bundesliga, Serie A, Ligue 1, and Champions League. "
    "Use the available tools to answer questions. Be concise. "
    "Format tables and scores clearly using markdown. "
    "Today's date is {date}."
)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []


@app.post("/api/chat", tags=["chat"])
async def chat(body: ChatRequest):
    if _mcp_session is None:
        return {"response": "Sports MCP server is not connected.", "tools_used": []}

    tools_result = await _mcp_session.list_tools()
    anthropic_tools = [
        {
            "name": tool.name,
            "description": tool.description or "",
            "input_schema": tool.inputSchema,
        }
        for tool in tools_result.tools
    ]

    messages: list[dict] = [
        {"role": m.role, "content": m.content} for m in body.history
    ]
    messages.append({"role": "user", "content": body.message})

    from datetime import date as dt_date
    system = CHAT_SYSTEM_PROMPT.format(date=dt_date.today().isoformat())

    client = anthropic.AsyncAnthropic()
    tools_used: list[str] = []

    try:
        for _ in range(10):
            response = await client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2048,
                system=system,
                tools=anthropic_tools,
                messages=messages,
            )

            if response.stop_reason == "tool_use":
                assistant_content = []
                for block in response.content:
                    if block.type == "text":
                        assistant_content.append({"type": "text", "text": block.text})
                    elif block.type == "tool_use":
                        assistant_content.append({
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        })
                messages.append({"role": "assistant", "content": assistant_content})

                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        mcp_result = await _mcp_session.call_tool(block.name, block.input)
                        if mcp_result.content:
                            result_text = "\n".join(
                                item.text for item in mcp_result.content if hasattr(item, "text")
                            )
                        elif hasattr(mcp_result, "structuredContent") and mcp_result.structuredContent is not None:
                            result_text = json.dumps(mcp_result.structuredContent)
                        else:
                            result_text = "{}"
                        tools_used.append(block.name)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result_text,
                        })
                messages.append({"role": "user", "content": tool_results})
            else:
                text = "".join(
                    block.text for block in response.content if hasattr(block, "text")
                )
                return {"response": text, "tools_used": tools_used}

        return {"response": "I had trouble processing that request. Please try again.", "tools_used": tools_used}
    except Exception as e:
        return {"response": f"Sorry, I encountered an error: {e}", "tools_used": tools_used}


# ── MCP ──────────────────────────────────────────────────────────────

mcp = FastApiMCP(
    app,
    name="Sports Dashboard",
    description="Personal sports dashboard — search teams, check fixtures/scores/standings, manage favorites, add games to calendar.",
    include_tags=["api"],
)
mcp.mount_http(app)


if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8901"))
    uvicorn.run(app, host=host, port=port)
