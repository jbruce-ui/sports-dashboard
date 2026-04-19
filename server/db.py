import duckdb
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "sports.duckdb")

def get_connection():
    return duckdb.connect(DB_PATH)

def init_db():
    con = get_connection()
    con.execute("""
        CREATE TABLE IF NOT EXISTS leagues (
            id VARCHAR PRIMARY KEY,
            name VARCHAR,
            sport VARCHAR,
            country VARCHAR,
            season VARCHAR,
            logo_url VARCHAR,
            updated_at TIMESTAMP DEFAULT current_timestamp
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS teams (
            id VARCHAR PRIMARY KEY,
            name VARCHAR,
            league_id VARCHAR,
            sport VARCHAR,
            badge_url VARCHAR,
            stadium VARCHAR,
            updated_at TIMESTAMP DEFAULT current_timestamp
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id VARCHAR PRIMARY KEY,
            name VARCHAR,
            league_id VARCHAR,
            season VARCHAR,
            round VARCHAR,
            home_team_id VARCHAR,
            home_team VARCHAR,
            away_team_id VARCHAR,
            away_team VARCHAR,
            home_score VARCHAR,
            away_score VARCHAR,
            event_date VARCHAR,
            event_time VARCHAR,
            venue VARCHAR,
            status VARCHAR,
            thumb_url VARCHAR,
            updated_at TIMESTAMP DEFAULT current_timestamp
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS favorite_teams (
            team_id VARCHAR PRIMARY KEY,
            team_name VARCHAR,
            league_key VARCHAR,
            added_at TIMESTAMP DEFAULT current_timestamp
        )
    """)
    con.close()
