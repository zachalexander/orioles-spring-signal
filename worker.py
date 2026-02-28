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


# ----------------------------
# Utility: Safe Orioles Filter
# ----------------------------
def filter_orioles(df):
    if df is None or df.empty:
        return pd.DataFrame()

    possible_cols = [
        "home_team",
        "away_team",
        "batting_team",
        "fielding_team",
        "player_team"
    ]

    for col in possible_cols:
        if col in df.columns:
            return df[df[col] == "BAL"]

    # If no recognizable team column exists,
    # return empty (safer than crashing)
    return pd.DataFrame()


# ----------------------------
# Hitter Metrics
# ----------------------------
def hitter_metrics(df):
    if df.empty:
        return pd.DataFrame()

    required_cols = ["player_name", "events", "launch_speed", "description"]

    for col in required_cols:
        if col not in df.columns:
            return pd.DataFrame()

    grouped = df.groupby("player_name").agg(
        PA=("events", "count"),
        EV=("launch_speed", "mean"),
        BarrelRate=("launch_speed", lambda x: np.mean(x > 98)),
        WhiffRate=("description", lambda x: np.mean(x == "swinging_strike")),
    )

    return grouped.dropna()


# ----------------------------
# Confidence Shrinkage
# ----------------------------
def confidence_score(delta, sample_size):
    if sample_size <= 0:
        return 0.0

    weight = min(sample_size / 50.0, 1.0)
    return float(delta * weight)


# ----------------------------
# Main Worker
# ----------------------------
def run():

    print("Pulling 2025 Regular...")
    reg_2025 = filter_orioles(statcast(REG_2025_START, REG_2025_END))

    print("Pulling 2025 Spring...")
    spring_2025 = filter_orioles(statcast(SPRING_2025_START, REG_2025_START))

    print("Pulling 2026 Spring...")
    spring_2026 = filter_orioles(statcast(SPRING_2026_START, TODAY))

    reg_hit = hitter_metrics(reg_2025)
    spr25_hit = hitter_metrics(spring_2025)
    spr26_hit = hitter_metrics(spring_2026)

    results = []

    if spr26_hit.empty or reg_hit.empty:
        print("No usable data found. Saving empty signal file.")
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
