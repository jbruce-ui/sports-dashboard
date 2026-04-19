#!/usr/bin/env python3
"""
Sports MCP Client — interactive CLI that talks to the Sports MCP Server
and can push game events to Google Calendar.
"""

import asyncio
import json
import sys
import httpx
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt
from rich.panel import Panel
from rich.markdown import Markdown

SERVER_URL = "http://localhost:8900"
console = Console()


async def call_server(method: str, path: str, params: dict = None) -> dict | list:
    async with httpx.AsyncClient(base_url=SERVER_URL, timeout=15) as client:
        if method == "GET":
            resp = await client.get(path, params=params)
        elif method == "POST":
            resp = await client.post(path, params=params)
        elif method == "DELETE":
            resp = await client.delete(path)
        else:
            raise ValueError(f"Unsupported method: {method}")
        resp.raise_for_status()
        return resp.json()


def print_events_table(events: list[dict], title: str = "Fixtures / Results"):
    table = Table(title=title, show_lines=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Date", style="cyan")
    table.add_column("Time", style="cyan")
    table.add_column("Home", style="green")
    table.add_column("Score", style="bold yellow", justify="center")
    table.add_column("Away", style="red")
    table.add_column("Venue", style="dim")
    table.add_column("ID", style="dim", width=8)

    for i, e in enumerate(events, 1):
        score = ""
        if e.get("home_score") is not None and e.get("away_score") is not None:
            score = f"{e['home_score']} - {e['away_score']}"
        table.add_row(
            str(i),
            e.get("date", ""),
            (e.get("time") or "")[:5],
            e.get("home_team", ""),
            score,
            e.get("away_team", ""),
            (e.get("venue") or "")[:25],
            str(e.get("id", "")),
        )
    console.print(table)


def print_teams_table(teams: list[dict]):
    table = Table(title="Teams", show_lines=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("ID", style="dim")
    table.add_column("Name", style="bold green")
    table.add_column("Sport", style="cyan")
    table.add_column("League", style="yellow")
    table.add_column("Country")
    table.add_column("Stadium", style="dim")

    for i, t in enumerate(teams, 1):
        table.add_row(
            str(i), t.get("id", ""), t.get("name", ""),
            t.get("sport", ""), t.get("league", ""),
            t.get("country", ""), (t.get("stadium") or "")[:30],
        )
    console.print(table)


def print_standings_table(standings: list[dict]):
    table = Table(title="Standings", show_lines=True)
    table.add_column("Rank", style="bold", width=4)
    table.add_column("Team", style="green")
    table.add_column("P", justify="center")
    table.add_column("W", justify="center", style="green")
    table.add_column("D", justify="center", style="yellow")
    table.add_column("L", justify="center", style="red")
    table.add_column("GF", justify="center")
    table.add_column("GA", justify="center")
    table.add_column("GD", justify="center")
    table.add_column("Pts", justify="center", style="bold cyan")

    for row in standings:
        table.add_row(
            str(row.get("rank", "")), row.get("team", ""),
            str(row.get("played", "")), str(row.get("won", "")),
            str(row.get("draw", "")), str(row.get("loss", "")),
            str(row.get("goals_for", "")), str(row.get("goals_against", "")),
            str(row.get("goal_diff", "")), str(row.get("points", "")),
        )
    console.print(table)


def show_help():
    help_text = """
## Commands

**Search & Discovery**
- `search team <name>` — Find teams by name
- `search league <sport>` — Find leagues by sport
- `teams <league_id>` — List teams in a league

**Fixtures & Results**
- `next team <team_id>` — Next 5 fixtures for a team
- `next league <league_id>` — Next fixtures for a league
- `last team <team_id>` — Last 5 results for a team
- `last league <league_id>` — Recent results for a league
- `date <YYYY-MM-DD> [sport]` — Games on a date
- `round <league_id> <round> <season>` — Games in a round

**Standings**
- `standings <league_id> <season>` — League table

**Favorites**
- `fav add <team_id> <team_name>` — Add favorite
- `fav remove <team_id>` — Remove favorite
- `fav list` — Show favorites
- `fav next` — Upcoming for all favorites
- `fav results` — Recent results for favorites

**Calendar**
- `cal add <event_index>` — Add last-shown game to Google Calendar
- `cal list [from] [to]` — Show sports events on calendar

**Other**
- `help` — Show this help
- `quit` / `exit` — Exit
"""
    console.print(Markdown(help_text))


last_events: list[dict] = []


async def handle_command(cmd: str):
    global last_events
    parts = cmd.strip().split()
    if not parts:
        return

    verb = parts[0].lower()

    try:
        if verb == "help":
            show_help()

        elif verb == "search" and len(parts) >= 3:
            kind = parts[1].lower()
            query = " ".join(parts[2:])
            if kind == "team":
                teams = await call_server("GET", "/search/teams", {"name": query})
                print_teams_table(teams)
            elif kind == "league":
                leagues = await call_server("GET", "/search/leagues", {"sport": query})
                table = Table(title="Leagues", show_lines=True)
                table.add_column("ID", style="dim")
                table.add_column("Name", style="bold green")
                table.add_column("Sport", style="cyan")
                table.add_column("Country")
                for l in leagues:
                    table.add_row(l.get("id", ""), l.get("name", ""), l.get("sport", ""), l.get("country", ""))
                console.print(table)

        elif verb == "teams" and len(parts) >= 2:
            teams = await call_server("GET", f"/teams_in_league/{parts[1]}")
            print_teams_table(teams)

        elif verb == "next" and len(parts) >= 3:
            kind, id_ = parts[1].lower(), parts[2]
            if kind == "team":
                events = await call_server("GET", f"/fixtures/next/team/{id_}")
            else:
                events = await call_server("GET", f"/fixtures/next/league/{id_}")
            last_events = events
            print_events_table(events, "Upcoming Fixtures")

        elif verb == "last" and len(parts) >= 3:
            kind, id_ = parts[1].lower(), parts[2]
            if kind == "team":
                events = await call_server("GET", f"/results/last/team/{id_}")
            else:
                events = await call_server("GET", f"/results/last/league/{id_}")
            last_events = events
            print_events_table(events, "Recent Results")

        elif verb == "date" and len(parts) >= 2:
            params = {"date": parts[1]}
            if len(parts) >= 3:
                params["sport"] = " ".join(parts[2:])
            events = await call_server("GET", "/fixtures/date", params)
            last_events = events
            print_events_table(events, f"Games on {parts[1]}")

        elif verb == "round" and len(parts) >= 4:
            events = await call_server("GET", "/fixtures/round", {
                "league_id": parts[1], "round": parts[2], "season": parts[3],
            })
            last_events = events
            print_events_table(events)

        elif verb == "standings" and len(parts) >= 3:
            standings = await call_server("GET", f"/standings/{parts[1]}", {"season": parts[2]})
            print_standings_table(standings)

        elif verb == "fav":
            if len(parts) < 2:
                console.print("[red]Usage: fav add|remove|list|next|results[/red]")
                return
            sub = parts[1].lower()
            if sub == "add" and len(parts) >= 4:
                name = " ".join(parts[3:])
                result = await call_server("POST", "/favorites/add", {"team_id": parts[2], "team_name": name})
                console.print(f"[green]Added {name} to favorites[/green]")
            elif sub == "remove" and len(parts) >= 3:
                await call_server("DELETE", f"/favorites/remove/{parts[2]}")
                console.print("[yellow]Removed from favorites[/yellow]")
            elif sub == "list":
                favs = await call_server("GET", "/favorites")
                table = Table(title="Favorite Teams")
                table.add_column("ID")
                table.add_column("Name", style="bold green")
                table.add_column("Added")
                for f in favs:
                    table.add_row(f["team_id"], f["team_name"], f.get("added_at", ""))
                console.print(table)
            elif sub == "next":
                data = await call_server("GET", "/favorites/upcoming")
                for team_name, events in data.items():
                    print_events_table(events, f"Upcoming: {team_name}")
            elif sub == "results":
                data = await call_server("GET", "/favorites/results")
                for team_name, events in data.items():
                    print_events_table(events, f"Results: {team_name}")

        elif verb == "cal":
            if len(parts) < 2:
                console.print("[red]Usage: cal add <index> | cal list[/red]")
                return
            sub = parts[1].lower()
            if sub == "add" and len(parts) >= 3:
                idx = int(parts[2]) - 1
                if idx < 0 or idx >= len(last_events):
                    console.print("[red]Invalid index. Run a fixtures query first.[/red]")
                    return
                event = last_events[idx]
                summary = f"{event.get('home_team', '?')} vs {event.get('away_team', '?')}"
                desc = f"League: {event.get('league', '')}\nSeason: {event.get('season', '')}"
                from calendar_service import add_game_to_calendar
                result = add_game_to_calendar(
                    summary=summary,
                    start_date=event.get("date", ""),
                    start_time=event.get("time"),
                    venue=event.get("venue"),
                    description=desc,
                )
                console.print(f"[green]Added to calendar: {result['summary']}[/green]")
                if result.get("link"):
                    console.print(f"[dim]{result['link']}[/dim]")
            elif sub == "list":
                from calendar_service import list_sports_events_on_calendar
                date_from = parts[2] if len(parts) >= 3 else None
                date_to = parts[3] if len(parts) >= 4 else None
                events = list_sports_events_on_calendar(date_from, date_to)
                table = Table(title="Calendar Sports Events")
                table.add_column("Summary", style="bold green")
                table.add_column("Start", style="cyan")
                table.add_column("Location", style="dim")
                for e in events:
                    table.add_row(e.get("summary", ""), e.get("start", ""), e.get("location", ""))
                console.print(table)

        elif verb in ("quit", "exit"):
            console.print("[yellow]Goodbye![/yellow]")
            sys.exit(0)

        else:
            console.print("[red]Unknown command. Type 'help' for available commands.[/red]")

    except httpx.ConnectError:
        console.print("[red]Cannot connect to server. Is it running on localhost:8900?[/red]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


async def main():
    console.print(Panel.fit(
        "[bold cyan]Sports MCP Client[/bold cyan]\n"
        "Query fixtures, scores, standings & push to calendar\n"
        "Type [bold]help[/bold] for commands",
        border_style="cyan",
    ))

    while True:
        try:
            cmd = Prompt.ask("\n[bold cyan]sports[/bold cyan]")
            await handle_command(cmd)
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Goodbye![/yellow]")
            break


if __name__ == "__main__":
    asyncio.run(main())
