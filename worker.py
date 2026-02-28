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
REG_2025_END   = "2025-10-01"

TODAY = datetime.date.today().strftime("%Y-%m-%d")

def filter_orioles(df):
    return df[(df["home_team"] == "BAL") | (df["away_team"] == "BAL")]

def hitter_metrics(df):
    grouped = df.groupby("player_name").agg(
        PA=("events", "count"),
        EV=("launch_speed", "mean"),
        BarrelRate=("launch_speed", lambda x: np.mean(x > 98)),
        WhiffRate=("description", lambda x: np.mean(x == "swinging_strike")),
    )
    return grouped.dropna()

def pitcher_metrics(df):
    grouped = df.groupby("pitcher").agg(
        Velo=("release_speed", "mean"),
        KRate=("events", lambda x: np.mean(x == "strikeout")),
    )
    return grouped.dropna()

def compute_bias(spring, regular):
    bias = spring - regular
    return bias

def confidence_score(delta, sample):
    weight = min(sample / 50, 1)
    score = delta * weight
    return score

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

    for player in spr26_hit.index:
        if player not in reg_hit.index:
            continue

        raw_delta = spr26_hit.loc[player]["EV"] - reg_hit.loc[player]["EV"]

        bias = 0
        if player in spr25_hit.index:
            bias = spr25_hit.loc[player]["EV"] - reg_hit.loc[player]["EV"]

        adjusted = raw_delta - bias
        conf = confidence_score(adjusted, spr26_hit.loc[player]["PA"])

        results.append({
            "player": player,
            "raw_delta_EV": float(raw_delta),
            "bias_EV": float(bias),
            "adjusted_delta_EV": float(adjusted),
            "confidence_index": float(conf)
        })

    with open(f"{DATA_DIR}/signals_2026.json", "w") as f:
        json.dump(results, f)

    print("Signals saved.")

if __name__ == "__main__":
    run()
