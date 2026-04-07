"""
Generate sample music streaming data for Feast.

Inspired by the Spotify Tracks Dataset:
https://www.kaggle.com/datasets/maharshipandya/-spotify-tracks-dataset

Generates two tables:
  - listener_stats: aggregated user behavior (plays, skip rate, top genre, etc.)
  - track_features: per-track audio features (danceability, energy, valence, tempo, etc.)
"""

import random
from datetime import datetime, timedelta, timezone

import pandas as pd

random.seed(42)

GENRES = ["pop", "hip-hop", "rock", "indie", "electronic", "r&b", "jazz", "latin", "classical", "metal"]

# Sample tracks with realistic audio feature profiles
TRACKS = [
    {"track_id": "t001", "track_name": "Midnight Drive", "artist_name": "Luna Park", "genre": "electronic"},
    {"track_id": "t002", "track_name": "Golden Hour", "artist_name": "Rosa Vega", "genre": "pop"},
    {"track_id": "t003", "track_name": "Concrete Jungle", "artist_name": "Ghost Protocol", "genre": "hip-hop"},
    {"track_id": "t004", "track_name": "Velvet Sky", "artist_name": "Ama Diallo", "genre": "r&b"},
    {"track_id": "t005", "track_name": "Static Bloom", "artist_name": "Neon Bridges", "genre": "indie"},
    {"track_id": "t006", "track_name": "Thunder Road", "artist_name": "The Midnight Waves", "genre": "rock"},
    {"track_id": "t007", "track_name": "Paper Lanterns", "artist_name": "Kira Sato", "genre": "jazz"},
    {"track_id": "t008", "track_name": "Fuego", "artist_name": "Rosa Vega", "genre": "latin"},
    {"track_id": "t009", "track_name": "Broken Mirrors", "artist_name": "Ghost Protocol", "genre": "hip-hop"},
    {"track_id": "t010", "track_name": "Daylight", "artist_name": "Luna Park", "genre": "electronic"},
    {"track_id": "t011", "track_name": "Slow Burn", "artist_name": "Ama Diallo", "genre": "r&b"},
    {"track_id": "t012", "track_name": "Neon Rain", "artist_name": "Neon Bridges", "genre": "indie"},
    {"track_id": "t013", "track_name": "Afterglow", "artist_name": "Kira Sato", "genre": "jazz"},
    {"track_id": "t014", "track_name": "Wildfire", "artist_name": "The Midnight Waves", "genre": "rock"},
    {"track_id": "t015", "track_name": "Crystal", "artist_name": "Luna Park", "genre": "electronic"},
    {"track_id": "t016", "track_name": "Streetlight Serenade", "artist_name": "Rosa Vega", "genre": "pop"},
    {"track_id": "t017", "track_name": "Phantom Limb", "artist_name": "Ghost Protocol", "genre": "hip-hop"},
    {"track_id": "t018", "track_name": "Honey", "artist_name": "Ama Diallo", "genre": "r&b"},
    {"track_id": "t019", "track_name": "Atlas", "artist_name": "Neon Bridges", "genre": "indie"},
    {"track_id": "t020", "track_name": "Undertow", "artist_name": "The Midnight Waves", "genre": "rock"},
]

# Genre-based audio feature profiles (mean values — we add noise per track)
GENRE_PROFILES = {
    "pop":        {"danceability": 0.68, "energy": 0.65, "valence": 0.60, "tempo": 120, "acousticness": 0.15, "instrumentalness": 0.02},
    "hip-hop":    {"danceability": 0.75, "energy": 0.70, "valence": 0.50, "tempo": 130, "acousticness": 0.10, "instrumentalness": 0.03},
    "rock":       {"danceability": 0.50, "energy": 0.80, "valence": 0.45, "tempo": 128, "acousticness": 0.12, "instrumentalness": 0.05},
    "indie":      {"danceability": 0.55, "energy": 0.55, "valence": 0.50, "tempo": 118, "acousticness": 0.35, "instrumentalness": 0.10},
    "electronic": {"danceability": 0.78, "energy": 0.82, "valence": 0.45, "tempo": 128, "acousticness": 0.05, "instrumentalness": 0.40},
    "r&b":        {"danceability": 0.72, "energy": 0.55, "valence": 0.55, "tempo": 110, "acousticness": 0.25, "instrumentalness": 0.02},
    "jazz":       {"danceability": 0.50, "energy": 0.40, "valence": 0.55, "tempo": 115, "acousticness": 0.60, "instrumentalness": 0.30},
    "latin":      {"danceability": 0.80, "energy": 0.72, "valence": 0.70, "tempo": 125, "acousticness": 0.18, "instrumentalness": 0.02},
    "classical":  {"danceability": 0.25, "energy": 0.20, "valence": 0.35, "tempo": 100, "acousticness": 0.90, "instrumentalness": 0.85},
    "metal":      {"danceability": 0.40, "energy": 0.95, "valence": 0.30, "tempo": 140, "acousticness": 0.03, "instrumentalness": 0.10},
}

now = datetime.now(timezone.utc)
timestamps = [now - timedelta(hours=i) for i in range(0, 168, 6)]


def clamp(value, lo=0.0, hi=1.0):
    return max(lo, min(hi, value))


def generate_listener_stats():
    rows = []
    for user_id in range(1001, 1011):
        top_genre = random.choice(GENRES)
        for ts in timestamps:
            rows.append({
                "user_id": user_id,
                "total_plays_7d": random.randint(20, 500),
                "unique_tracks_7d": random.randint(10, 200),
                "unique_artists_7d": random.randint(5, 80),
                "avg_listen_minutes_daily": round(random.uniform(15.0, 180.0), 1),
                "skip_rate": round(random.uniform(0.05, 0.45), 3),
                "top_genre": top_genre,
                "avg_track_popularity": round(random.uniform(30.0, 85.0), 1),
                "event_timestamp": ts,
            })
    return pd.DataFrame(rows)


def generate_track_features():
    rows = []
    for track in TRACKS:
        profile = GENRE_PROFILES[track["genre"]]
        for ts in timestamps:
            rows.append({
                "track_id": track["track_id"],
                "track_name": track["track_name"],
                "artist_name": track["artist_name"],
                "genre": track["genre"],
                "popularity": random.randint(20, 95),
                "danceability": round(clamp(profile["danceability"] + random.gauss(0, 0.08)), 3),
                "energy": round(clamp(profile["energy"] + random.gauss(0, 0.08)), 3),
                "valence": round(clamp(profile["valence"] + random.gauss(0, 0.10)), 3),
                "tempo": round(profile["tempo"] + random.gauss(0, 8), 1),
                "acousticness": round(clamp(profile["acousticness"] + random.gauss(0, 0.08)), 3),
                "instrumentalness": round(clamp(profile["instrumentalness"] + random.gauss(0, 0.05)), 3),
                "duration_ms": random.randint(150_000, 360_000),
                "event_timestamp": ts,
            })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    listener_df = generate_listener_stats()
    listener_df.to_parquet("feature_repo/data/listener_stats.parquet")
    print(f"Wrote listener_stats.parquet: {len(listener_df)} rows, users 1001-1010")

    track_df = generate_track_features()
    track_df.to_parquet("feature_repo/data/track_features.parquet")
    print(f"Wrote track_features.parquet: {len(track_df)} rows, {len(TRACKS)} tracks")
