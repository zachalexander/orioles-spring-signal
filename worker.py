import os
import json
import datetime
import pandas as pd
import numpy as np
from pybaseball import statcast

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

SPRING_2026_START = "2026-02-15"
SPRING_2025_START = "2025-02-15"
REG_2025_START = "2025-03-20"
REG_2025_END = "2025-10-01"

TODAY = datetime.date.today().strftime("%Y-%m-%d")


def safe_statcast(start, end):
    try:
        df = statcast(start_dt=start, end_dt=end)
        if df is None or df.empty:
            print(f"No data returned for {start} to {end}")
            return pd.DataFrame()
        return df
    except Exception as e:
        print(f"Statcast error for {start} to {end}: {e}")
        return pd.DataFrame()


def filter_orioles(df):
    if df.empty:
        return df

    team_cols = [col for col in df.columns if "team" in col.lower()]
    for col in team_cols:
        try:
            filtered = df[df[col] == "BAL"]
            if not filtered.empty:
                return filtered
        except:
            continue

    print("No team column found; returning empty dataframe.")
    return pd.DataFrame()


def hitter_metrics(df):
    if df.empty:
        return pd.DataFrame()

    required = ["player_name", "events", "launch_speed"]
    for col in required:
        if col not in df.columns:
            print(f"Missing column: {col}")
            return pd.DataFrame()

    grouped = df.groupby("player_name").agg(
        PA=("events", "count"),
        EV=("launch_speed", "mean"),
    )

    return grouped.dropna()


def confidence_score(delta, sample):
    if sample <= 0:
        return 0.0
    weight = min(sample / 50.0, 1.0)
    return float(delta * weight)


def run():

    print("Pulling 2025 Regular...")
    reg_2025 = filter_orioles(safe_statcast(REG_2025_START, REG_2025_END))

    print("Pulling 2025 Spring...")
    spring_2025 = filter_orioles(safe_statcast(SPRING_2025_START, REG_2025_START))

    print("Pulling 2026 Spring...")
    spring_2026 = filter_orioles(safe_statcast(SPRING_2026_START, TODAY))

    reg_hit = hitter_metrics(reg_2025)
    spr25_hit = hitter_metrics(spring_2025)
    spr26_hit = hitter_metrics(spring_2026)

    results = []

    if spr26_hit.empty or reg_hit.empty:
        print("Insufficient data. Saving empty file.")
        with open(f"{DATA_DIR}/signals_2026.json", "w") as f:
            json.dump([], f)
        return

    for player in spr26_hit.index:

        if player not in reg_hit.index:
            continue

        raw_delta = spr26_hit.loc[player]["EV"] - reg_hit.loc[player]["EV"]

        bias = 0.0
        if player in spr25_hit.index:
            bias = spr25_hit.loc[player]["EV"] - reg_hit.loc[player]["EV"]

        adjusted = raw_delta - bias
        sample_size = spr26_hit.loc[player]["PA"]
        conf = confidence_score(adjusted, sample_size)

        results.append({
            "player": player,
            "raw_delta_EV": float(raw_delta),
            "bias_EV": float(bias),
            "adjusted_delta_EV": float(adjusted),
            "confidence_index": float(conf)
        })

    results = sorted(results, key=lambda x: x["confidence_index"], reverse=True)

    with open(f"{DATA_DIR}/signals_2026.json", "w") as f:
        json.dump(results, f)

    print("Signals saved successfully.")


if __name__ == "__main__":
    run()
