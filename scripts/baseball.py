#!/usr/bin/env python3
"""
Baseball — MLB game schedules, live status, and box scores.

Usage:
    python scripts/baseball.py games [--team PHI] [--date MM/DD/YYYY] [--format text|json]
    python scripts/baseball.py live <gamePk_or_team> [--date MM/DD/YYYY] [--format text|json]
    python scripts/baseball.py score <gamePk_or_team> [--date MM/DD/YYYY] [--format text|json]
"""

import argparse
import json
import sys
from datetime import datetime, timedelta

from mlb_api import fetch_schedule, fetch_live_game, lookup_team, MLB_TEAMS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_start_time(dt):
    """Format a datetime as a short local time string like '7:10 PM'."""
    if dt is None:
        return "TBD"
    return dt.strftime("%I:%M %p").lstrip("0")


def _ordinal(n):
    """Return ordinal string: 1 -> '1st', 2 -> '2nd', etc."""
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _resolve_game_pk(arg, date=None):
    """Resolve a game PK from a numeric string or team abbreviation.

    If arg is numeric, return it as an integer.
    If alphabetic, look up the schedule for that team's game on the given date
    (defaults to today).
    """
    if arg.isdigit():
        return int(arg)

    abbr, team_info = lookup_team(arg)
    if abbr is None:
        print(f"Error: Unknown team '{arg}'.", file=sys.stderr)
        print("Run 'baseball.py teams' to see valid abbreviations.", file=sys.stderr)
        sys.exit(1)

    team_name = team_info["name"]
    lookup_date = date if date else datetime.now().strftime("%m/%d/%Y")
    games = fetch_schedule(lookup_date)

    if not games:
        print(f"Error: No games scheduled for {lookup_date}.", file=sys.stderr)
        sys.exit(1)

    for game in games:
        if game.away_team.abbreviation == abbr or game.home_team.abbreviation == abbr:
            return game.game_pk

    print(f"Error: {team_name} ({abbr}) is not playing on {lookup_date}.", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# games subcommand
# ---------------------------------------------------------------------------

def _status_display(game):
    """Short status string for the games table."""
    status = game.status
    if status == "Final":
        if game.away_score or game.home_score:
            return f"Final ({game.away_score}-{game.home_score})"
        return "Final"
    if status in ("In Progress", "Manager Challenge"):
        return "In Progress"
    if status in ("Scheduled", "Pre-Game", "Warmup"):
        return _format_start_time(game.start_time)
    return status


def cmd_games(args):
    start_date = args.date if args.date else datetime.now().strftime("%m/%d/%Y")
    end_date = None

    if args.days and args.days > 1:
        try:
            start_dt = datetime.strptime(start_date, "%m/%d/%Y")
        except ValueError:
            print(f"Error: Invalid date format '{start_date}'. Use MM/DD/YYYY.", file=sys.stderr)
            sys.exit(1)
        end_dt = start_dt + timedelta(days=args.days - 1)
        end_date = end_dt.strftime("%m/%d/%Y")

    games = fetch_schedule(start_date, end_date)

    # Filter by team
    team_abbr = None
    if args.team:
        team_abbr, _ = lookup_team(args.team)
        if team_abbr is None:
            print(f"Error: Unknown team '{args.team}'.", file=sys.stderr)
            print("Run 'baseball.py teams' to see valid abbreviations.", file=sys.stderr)
            sys.exit(1)
        games = [
            g for g in games
            if g.away_team.abbreviation == team_abbr or g.home_team.abbreviation == team_abbr
        ]

    date_label = start_date if not end_date else f"{start_date} - {end_date}"

    if not games:
        msg = f"No games found for {date_label}"
        if args.team:
            msg += f" (team: {args.team.upper()})"
        if args.format == "json":
            print(json.dumps({"date": date_label, "games": []}, indent=2))
        else:
            print(msg)
        return

    if args.format == "json":
        output = {
            "date": date_label,
            "games": [g.to_dict() for g in games],
        }
        print(json.dumps(output, indent=2))
    else:
        _output_games_text(date_label, games, multi_day=bool(end_date))


def _output_games_text(date_label, games, multi_day=False):
    print(f"MLB Games - {date_label}")
    header = f"{'Away':<17} {'Record':<10} {'Home':<17} {'Record':<10} {'Time':<10} {'Status':<20} {'Game ID'}"
    print(header)
    print("-" * 95)

    current_date = None
    for g in games:
        # Print date separator for multi-day ranges
        if multi_day:
            game_date = getattr(g, "date_label", "")
            if game_date and game_date != current_date:
                if current_date is not None:
                    print()
                print(f"  {game_date}")
                current_date = game_date

        away_label = f"{g.away_team.abbreviation} {g.away_team.name.split()[-1]}"
        home_label = f"{g.home_team.abbreviation} {g.home_team.name.split()[-1]}"
        time_str = _format_start_time(g.start_time)
        status = _status_display(g)
        print(
            f"{away_label:<17} {g.away_record:<10} "
            f"{home_label:<17} {g.home_record:<10} "
            f"{time_str:<10} {status:<20} {g.game_pk}"
        )


# ---------------------------------------------------------------------------
# live subcommand
# ---------------------------------------------------------------------------

def cmd_live(args):
    game_pk = _resolve_game_pk(args.game, date=args.date)
    game = fetch_live_game(game_pk)

    if game is None:
        print(f"Error: Could not fetch live data for game {game_pk}.", file=sys.stderr)
        sys.exit(1)

    if args.format == "json":
        print(json.dumps(game.to_dict(), indent=2))
    else:
        _output_live_text(game)


def _output_live_text(game):
    away = game.away_team
    home = game.home_team

    # Header line
    away_label = f"{away.abbreviation} {away.name.split()[-1]}"
    home_label = f"{home.abbreviation} {home.name.split()[-1]}"
    print(f"{away_label} {game.away_score}  @  {home_label} {game.home_score}")

    # Status line
    if game.status in ("In Progress", "Manager Challenge"):
        half = "Top" if game.inning_half == "Top" else "Bot"
        inning_str = _ordinal(game.inning)
        outs_str = f"{game.outs} out{'s' if game.outs != 1 else ''}"
        count_str = f"{game.balls}-{game.strikes} count"
        print(f"  {half} {inning_str}  |  {outs_str}  |  {count_str}")

        # Runners
        first = "[X]" if game.runners["first"] else "[ ]"
        second = "[X]" if game.runners["second"] else "[ ]"
        third = "[X]" if game.runners["third"] else "[ ]"
        print(f"  Bases: 1B {first}  2B {second}  3B {third}")

        # Matchup
        if game.matchup:
            print(f"  AB: {game.matchup.batter_name}  vs  P: {game.matchup.pitcher_name}")

        # Last play
        if game.last_play and game.last_play.description:
            print(f"  Last: {game.last_play.description}")
    else:
        print(f"  Status: {game.status}")

    print()
    _output_linescore_text(game)


def _output_linescore_text(game):
    """Print the box score line score."""
    innings = game.line_score.innings
    num_innings = max(len(innings), 9)

    # Header
    header = "    "
    for i in range(1, num_innings + 1):
        header += f"{i:>3}"
    header += "    R  H  E"
    print(header)

    # Away line
    away_line = f"{game.away_team.abbreviation:<4}"
    for i in range(num_innings):
        if i < len(innings):
            away_line += f"{innings[i].away_runs:>3}"
        else:
            away_line += "  -"
    away_line += f"  {game.line_score.away_runs:>3}{game.line_score.away_hits:>3}{game.line_score.away_errors:>3}"
    print(away_line)

    # Home line
    home_line = f"{game.home_team.abbreviation:<4}"
    for i in range(num_innings):
        if i < len(innings):
            # If current inning, top half, and this is the last inning — home hasn't batted yet
            if (i == len(innings) - 1
                    and game.line_score.is_top_inning
                    and game.status in ("In Progress", "Manager Challenge")):
                home_line += "  -"
            else:
                home_line += f"{innings[i].home_runs:>3}"
        else:
            home_line += "  -"
    home_line += f"  {game.line_score.home_runs:>3}{game.line_score.home_hits:>3}{game.line_score.home_errors:>3}"
    print(home_line)


# ---------------------------------------------------------------------------
# score subcommand
# ---------------------------------------------------------------------------

def cmd_score(args):
    game_pk = _resolve_game_pk(args.game, date=args.date)
    game = fetch_live_game(game_pk)

    if game is None:
        print(f"Error: Could not fetch data for game {game_pk}.", file=sys.stderr)
        sys.exit(1)

    if args.format == "json":
        print(json.dumps(game.to_dict(), indent=2))
    else:
        _output_score_text(game)


def _output_score_text(game):
    away = game.away_team
    home = game.home_team

    away_label = f"{away.abbreviation} {away.name.split()[-1]}"
    home_label = f"{home.abbreviation} {home.name.split()[-1]}"

    if game.status == "Final":
        print(f"Final: {away_label} {game.away_score}  @  {home_label} {game.home_score}")
    else:
        print(f"{game.status}: {away_label} {game.away_score}  @  {home_label} {game.home_score}")

    print()
    _output_linescore_text(game)


# ---------------------------------------------------------------------------
# teams subcommand
# ---------------------------------------------------------------------------

def cmd_teams(args):
    teams = sorted(MLB_TEAMS.items(), key=lambda t: t[0])

    if args.format == "json":
        output = [{"abbreviation": abbr, "name": info["name"]} for abbr, info in teams]
        print(json.dumps({"teams": output}, indent=2))
    else:
        print(f"{'Abbr':<6} {'Team Name'}")
        print("-" * 35)
        for abbr, info in teams:
            print(f"{abbr:<6} {info['name']}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="MLB game schedules, live status, and box scores"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # teams
    teams_parser = subparsers.add_parser("teams", help="List all MLB team abbreviations")
    teams_parser.add_argument(
        "--format", choices=["text", "json"], default="text",
        help="Output format (default: text)"
    )

    # games
    games_parser = subparsers.add_parser("games", help="List games for a date")
    games_parser.add_argument("--team", help="Filter by team abbreviation (e.g., PHI)")
    games_parser.add_argument("--date", help="Start date in MM/DD/YYYY format (default: today)")
    games_parser.add_argument("--days", type=int, help="Number of days to show (e.g., 7 for a week)")
    games_parser.add_argument(
        "--format", choices=["text", "json"], default="text",
        help="Output format (default: text)"
    )

    # live
    live_parser = subparsers.add_parser("live", help="Live game status with count, runners, matchup")
    live_parser.add_argument("game", help="Game PK (numeric) or team abbreviation (e.g., PHI)")
    live_parser.add_argument("--date", help="Date to look up team's game (MM/DD/YYYY, default: today)")
    live_parser.add_argument(
        "--format", choices=["text", "json"], default="text",
        help="Output format (default: text)"
    )

    # score
    score_parser = subparsers.add_parser("score", help="Box score for a game")
    score_parser.add_argument("game", help="Game PK (numeric) or team abbreviation (e.g., PHI)")
    score_parser.add_argument("--date", help="Date to look up team's game (MM/DD/YYYY, default: today)")
    score_parser.add_argument(
        "--format", choices=["text", "json"], default="text",
        help="Output format (default: text)"
    )

    args = parser.parse_args()

    if args.command == "teams":
        cmd_teams(args)
    elif args.command == "games":
        cmd_games(args)
    elif args.command == "live":
        cmd_live(args)
    elif args.command == "score":
        cmd_score(args)


if __name__ == "__main__":
    main()
