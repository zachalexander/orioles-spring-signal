import os
import json
import datetime
import pandas as pd
import numpy as np
import requests
from pybaseball import statcast

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

SPRING_2026_START = "2026-02-15"
SPRING_2025_START = "2025-02-15"
REG_2025_START = "2025-03-20"
REG_2025_END = "2025-10-01"

TODAY = datetime.date.today().strftime("%Y-%m-%d")

ORIOLES_TEAM_ID = 110


# ----------------------------
# Pull Current Orioles Roster
# ----------------------------
def get_orioles_roster_ids():
    url = f"https://statsapi.mlb.com/api/v1/teams/{ORIOLES_TEAM_ID}/roster/active"
    response = requests.get(url)
    data = response.json()

    ids = []
    names = {}

    for player in data.get("roster", []):
        pid = player["person"]["id"]
        pname = player["person"]["fullName"]
        ids.append(pid)
        names[pid] = pname

    return set(ids), names


# ----------------------------
# Safe Statcast Pull
# ----------------------------
def safe_statcast(start, end):
    try:
        df = statcast(start_dt=start, end_dt=end)
        if df is None or df.empty:
            return pd.DataFrame()
        return df
    except Exception as e:
        print("Statcast error:", e)
        return pd.DataFrame()


# ----------------------------
# Filter by Orioles Player IDs
# ----------------------------
def filter_by_roster(df, roster_ids):
    if df.empty:
        return df

    cols = df.columns

    hitter_df = pd.DataFrame()
    pitcher_df = pd.DataFrame()

    if "batter" in cols:
        hitter_df = df[df["batter"].isin(roster_ids)]

    if "pitcher" in cols:
        pitcher_df = df[df["pitcher"].isin(roster_ids)]

    return hitter_df, pitcher_df


# ----------------------------
# Hitter Metrics
# ----------------------------
def hitter_metrics(df):
    if df.empty:
        return pd.DataFrame()

    grouped = df.groupby("batter").agg(
        PA=("events", "count"),
        EV=("launch_speed", "mean"),
        BarrelRate=("launch_speed", lambda x: np.mean(x > 98)),
    )

    return grouped.dropna()


# ----------------------------
# Pitcher Metrics
# ----------------------------
def pitcher_metrics(df):
    if df.empty:
        return pd.DataFrame()

    grouped = df.groupby("pitcher").agg(
        BF=("events", "count"),
        Velo=("release_speed", "mean"),
        KRate=("events", lambda x: np.mean(x == "strikeout")),
    )

    return grouped.dropna()


# ----------------------------
# Confidence Shrinkage
# ----------------------------
def confidence_score(delta, sample):
    if sample <= 0:
        return 0.0
    weight = min(sample / 50.0, 1.0)
    return float(delta * weight)


# ----------------------------
# Main Worker
# ----------------------------
def run():

    print("Fetching Orioles roster...")
    roster_ids, name_map = get_orioles_roster_ids()

    print("Pulling 2025 Regular...")
    reg_2025 = safe_statcast(REG_2025_START, REG_2025_END)

    print("Pulling 2025 Spring...")
    spring_2025 = safe_statcast(SPRING_2025_START, REG_2025_START)

    print("Pulling 2026 Spring...")
    spring_2026 = safe_statcast(SPRING_2026_START, TODAY)

    reg_hit, reg_pitch = filter_by_roster(reg_2025, roster_ids)
    spr25_hit, spr25_pitch = filter_by_roster(spring_2025, roster_ids)
    spr26_hit, spr26_pitch = filter_by_roster(spring_2026, roster_ids)

    reg_hit_m = hitter_metrics(reg_hit)
    spr25_hit_m = hitter_metrics(spr25_hit)
    spr26_hit_m = hitter_metrics(spr26_hit)

    reg_pitch_m = pitcher_metrics(reg_pitch)
    spr25_pitch_m = pitcher_metrics(spr25_pitch)
    spr26_pitch_m = pitcher_metrics(spr26_pitch)

    results = []

    # -------- Hitters --------
    for pid in spr26_hit_m.index:
        if pid not in reg_hit_m.index:
            continue

        raw_delta = spr26_hit_m.loc[pid]["EV"] - reg_hit_m.loc[pid]["EV"]

        bias = 0.0
        if pid in spr25_hit_m.index:
            bias = spr25_hit_m.loc[pid]["EV"] - reg_hit_m.loc[pid]["EV"]

        adjusted = raw_delta - bias
        sample_size = spr26_hit_m.loc[pid]["PA"]
        conf = confidence_score(adjusted, sample_size)

        results.append({
            "player": name_map.get(pid, str(pid)),
            "type": "hitter",
            "raw_delta_EV": float(raw_delta),
            "adjusted_delta_EV": float(adjusted),
            "confidence_index": float(conf)
        })

    # -------- Pitchers --------
    for pid in spr26_pitch_m.index:
        if pid not in reg_pitch_m.index:
            continue

        raw_delta = spr26_pitch_m.loc[pid]["Velo"] - reg_pitch_m.loc[pid]["Velo"]

        bias = 0.0
        if pid in spr25_pitch_m.index:
            bias = spr25_pitch_m.loc[pid]["Velo"] - reg_pitch_m.loc[pid]["Velo"]

        adjusted = raw_delta - bias
        sample_size = spr26_pitch_m.loc[pid]["BF"]
        conf = confidence_score(adjusted, sample_size)

        results.append({
            "player": name_map.get(pid, str(pid)),
            "type": "pitcher",
            "raw_delta_Velo": float(raw_delta),
            "adjusted_delta_Velo": float(adjusted),
            "confidence_index": float(conf)
        })

    results = sorted(results, key=lambda x: x["confidence_index"], reverse=True)

    with open(f"{DATA_DIR}/signals_2026.json", "w") as f:
        json.dump(results, f)

    print("Signals saved successfully.")


if __name__ == "__main__":
    run()
