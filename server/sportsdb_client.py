import httpx
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

API_KEY = os.getenv("SPORTSDB_API_KEY", "3")
BASE_URL = f"https://www.thesportsdb.com/api/v1/json/{API_KEY}"

async def _get(endpoint: str, params: dict = None) -> dict | None:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{BASE_URL}/{endpoint}", params=params)
        resp.raise_for_status()
        return resp.json()

async def search_teams(team_name: str) -> list[dict]:
    data = await _get("searchteams.php", {"t": team_name})
    return data.get("teams") or []

async def search_leagues(league_name: str) -> list[dict]:
    data = await _get("search_all_leagues.php", {"s": league_name})
    return data.get("countrys") or []  # API uses "countrys"

async def list_leagues_by_country_sport(country: str, sport: str) -> list[dict]:
    data = await _get("search_all_leagues.php", {"c": country, "s": sport})
    return data.get("countrys") or []

async def get_league_seasons(league_id: str) -> list[dict]:
    data = await _get("search_all_seasons.php", {"id": league_id})
    return data.get("seasons") or []

async def get_next_events_by_team(team_id: str) -> list[dict]:
    data = await _get("eventsnext.php", {"id": team_id})
    return data.get("events") or []

async def get_last_events_by_team(team_id: str) -> list[dict]:
    data = await _get("eventslast.php", {"id": team_id})
    return data.get("results") or []

async def get_next_events_by_league(league_id: str) -> list[dict]:
    data = await _get("eventsnextleague.php", {"id": league_id})
    return data.get("events") or []

async def get_last_events_by_league(league_id: str) -> list[dict]:
    data = await _get("eventspastleague.php", {"id": league_id})
    return data.get("events") or []

async def get_events_by_round(league_id: str, round_num: str, season: str) -> list[dict]:
    data = await _get("eventsround.php", {"id": league_id, "r": round_num, "s": season})
    return data.get("events") or []

async def get_season_events(league_id: str, season: str) -> list[dict]:
    data = await _get("eventsseason.php", {"id": league_id, "s": season})
    return data.get("events") or []

async def get_event_details(event_id: str) -> dict | None:
    data = await _get("lookupevent.php", {"id": event_id})
    events = data.get("events") or []
    return events[0] if events else None

async def get_team_details(team_id: str) -> dict | None:
    data = await _get("lookupteam.php", {"id": team_id})
    teams = data.get("teams") or []
    return teams[0] if teams else None

async def get_teams_in_league(league_id: str) -> list[dict]:
    data = await _get("lookup_all_teams.php", {"id": league_id})
    return data.get("teams") or []

async def get_events_by_date(date: str, sport: str = None, league: str = None) -> list[dict]:
    params = {"d": date}
    if sport:
        params["s"] = sport
    if league:
        params["l"] = league
    data = await _get("eventsday.php", params)
    return data.get("events") or []

async def get_league_table(league_id: str, season: str) -> list[dict]:
    data = await _get("lookuptable.php", {"l": league_id, "s": season})
    return data.get("table") or []
