import httpx
from datetime import datetime, timedelta

BASE = "https://site.api.espn.com/apis/site/v2/sports"
STANDINGS_BASE = "https://site.api.espn.com/apis/v2/sports"

LEAGUES = {
    "nfl": ("football", "nfl", "NFL"),
    "nba": ("basketball", "nba", "NBA"),
    "mlb": ("baseball", "mlb", "MLB"),
    "nhl": ("hockey", "nhl", "NHL"),
    "epl": ("soccer", "eng.1", "Premier League"),
    "mls": ("soccer", "usa.1", "MLS"),
    "laliga": ("soccer", "esp.1", "La Liga"),
    "bundesliga": ("soccer", "ger.1", "Bundesliga"),
    "seriea": ("soccer", "ita.1", "Serie A"),
    "ligue1": ("soccer", "fra.1", "Ligue 1"),
    "ucl": ("soccer", "uefa.champions", "Champions League"),
}


def _league_path(league_key: str) -> tuple[str, str, str]:
    if league_key in LEAGUES:
        return LEAGUES[league_key]
    if "/" in league_key:
        parts = league_key.split("/", 1)
        return parts[0], parts[1], league_key
    raise ValueError(f"Unknown league: {league_key}. Available: {list(LEAGUES.keys())}")


async def _get(url: str, params: dict = None) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


def _parse_event(e: dict) -> dict:
    comp = (e.get("competitions") or [{}])[0]
    competitors = comp.get("competitors", [])
    home = next((c for c in competitors if c.get("homeAway") == "home"), {})
    away = next((c for c in competitors if c.get("homeAway") == "away"), {})
    status = comp.get("status", {}).get("type", {})

    home_score = None
    away_score = None
    if status.get("completed") or status.get("name") == "STATUS_IN_PROGRESS":
        raw_home = home.get("score")
        raw_away = away.get("score")
        if isinstance(raw_home, dict):
            home_score = raw_home.get("displayValue", raw_home.get("value"))
        elif raw_home is not None:
            home_score = str(raw_home)
        if isinstance(raw_away, dict):
            away_score = raw_away.get("displayValue", raw_away.get("value"))
        elif raw_away is not None:
            away_score = str(raw_away)

    dt = e.get("date", "")
    date_str = dt[:10] if dt else ""
    time_str = ""
    if "T" in dt:
        try:
            parsed = datetime.fromisoformat(dt.replace("Z", "+00:00"))
            time_str = parsed.strftime("%H:%M")
        except Exception:
            time_str = dt[11:16] if len(dt) > 16 else ""

    return {
        "id": e.get("id"),
        "name": e.get("name", ""),
        "short_name": e.get("shortName", ""),
        "date": date_str,
        "time": time_str,
        "home_team": home.get("team", {}).get("displayName", ""),
        "home_team_short": home.get("team", {}).get("shortDisplayName", ""),
        "home_team_id": home.get("team", {}).get("id"),
        "home_score": str(home_score) if home_score is not None else None,
        "away_team": away.get("team", {}).get("displayName", ""),
        "away_team_short": away.get("team", {}).get("shortDisplayName", ""),
        "away_team_id": away.get("team", {}).get("id"),
        "away_score": str(away_score) if away_score is not None else None,
        "venue": comp.get("venue", {}).get("fullName", ""),
        "status": status.get("description", status.get("name", "")),
        "completed": status.get("completed", False),
        "league": (e.get("league") or {}).get("abbreviation", ""),
    }


async def get_scoreboard(league_key: str, date: str = None) -> list[dict]:
    sport, league, _ = _league_path(league_key)
    params = {}
    if date:
        params["dates"] = date.replace("-", "")
    data = await _get(f"{BASE}/{sport}/{league}/scoreboard", params)
    league_info = (data.get("leagues") or [{}])[0]
    events = data.get("events", [])
    results = []
    for e in events:
        parsed = _parse_event(e)
        parsed["league"] = league_info.get("abbreviation", league_key)
        results.append(parsed)
    return results


async def get_teams(league_key: str) -> list[dict]:
    sport, league, _ = _league_path(league_key)
    data = await _get(f"{BASE}/{sport}/{league}/teams")
    teams_raw = data.get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", [])
    return [
        {
            "id": t.get("team", {}).get("id"),
            "name": t.get("team", {}).get("displayName", ""),
            "short_name": t.get("team", {}).get("shortDisplayName", ""),
            "abbreviation": t.get("team", {}).get("abbreviation", ""),
            "logo": t.get("team", {}).get("logos", [{}])[0].get("href", "") if t.get("team", {}).get("logos") else "",
            "league": league_key,
        }
        for t in teams_raw
    ]


async def get_team_schedule(league_key: str, team_id: str) -> list[dict]:
    sport, league, _ = _league_path(league_key)
    data = await _get(f"{BASE}/{sport}/{league}/teams/{team_id}/schedule")
    events = data.get("events", [])
    team_info = data.get("team", {})
    results = []
    for e in events:
        parsed = _parse_event(e)
        parsed["league"] = league_key
        results.append(parsed)
    results.sort(key=lambda x: x.get("date", ""))
    return results


async def get_team_upcoming(league_key: str, team_id: str) -> list[dict]:
    sport, league, _ = _league_path(league_key)
    today = datetime.now()
    end = today + timedelta(days=60)
    date_range = f"{today.strftime('%Y%m%d')}-{end.strftime('%Y%m%d')}"
    data = await _get(f"{BASE}/{sport}/{league}/scoreboard", {"dates": date_range})
    league_info = (data.get("leagues") or [{}])[0]
    results = []
    for e in data.get("events", []):
        comp = (e.get("competitions") or [{}])[0]
        competitors = comp.get("competitors", [])
        team_ids = [c.get("team", {}).get("id") for c in competitors]
        if team_id in team_ids:
            parsed = _parse_event(e)
            parsed["league"] = league_info.get("abbreviation", league_key)
            if not parsed.get("completed"):
                results.append(parsed)
    results.sort(key=lambda x: x.get("date", ""))
    return results


async def get_team_results(league_key: str, team_id: str, limit: int = 5) -> list[dict]:
    schedule = await get_team_schedule(league_key, team_id)
    today = datetime.now().strftime("%Y-%m-%d")
    completed = [e for e in schedule if e.get("completed")]
    completed.sort(key=lambda x: x.get("date", ""), reverse=True)
    return completed[:limit]


async def get_standings(league_key: str) -> list[dict]:
    sport, league, _ = _league_path(league_key)
    data = await _get(f"{STANDINGS_BASE}/{sport}/{league}/standings")
    children = data.get("children", [])
    results = []
    for group in children:
        group_name = group.get("name", "")
        entries = group.get("standings", {}).get("entries", [])
        for entry in entries:
            team = entry.get("team", {})
            stats = {}
            for s in entry.get("stats", []):
                val = s.get("value", s.get("displayValue", ""))
                stats[s["name"]] = val
            results.append({
                "team": team.get("displayName", ""),
                "team_id": team.get("id"),
                "logo": team.get("logos", [{}])[0].get("href", "") if team.get("logos") else "",
                "group": group_name,
                "rank": stats.get("rank", ""),
                "games_played": stats.get("gamesPlayed", ""),
                "wins": stats.get("wins", ""),
                "draws": stats.get("ties", stats.get("draws", "")),
                "losses": stats.get("losses", ""),
                "points": stats.get("points", ""),
                "goals_for": stats.get("pointsFor", stats.get("goalsFor", "")),
                "goals_against": stats.get("pointsAgainst", stats.get("goalsAgainst", "")),
                "goal_diff": stats.get("pointDifferential", stats.get("goalDifference", "")),
                "streak": stats.get("streak", ""),
            })
    results.sort(key=lambda r: (r["group"], float(r["rank"]) if r["rank"] != "" else 999))
    return results


async def search_teams(query: str) -> list[dict]:
    query_lower = query.lower()
    all_teams = []
    for league_key in LEAGUES:
        try:
            teams = await get_teams(league_key)
            for t in teams:
                if query_lower in t.get("name", "").lower() or query_lower in t.get("short_name", "").lower() or query_lower in t.get("abbreviation", "").lower():
                    all_teams.append(t)
        except Exception:
            continue
    return all_teams


async def get_scoreboard_multi(date: str = None) -> dict[str, list[dict]]:
    results = {}
    for league_key in LEAGUES:
        try:
            events = await get_scoreboard(league_key, date)
            if events:
                _, _, display_name = LEAGUES[league_key]
                results[display_name] = events
        except Exception:
            continue
    return results


def list_leagues() -> list[dict]:
    return [
        {"key": k, "sport": v[0], "espn_slug": v[1], "name": v[2]}
        for k, v in LEAGUES.items()
    ]
