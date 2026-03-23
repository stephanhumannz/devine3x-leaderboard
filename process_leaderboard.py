#!/usr/bin/env python3
# ============================================================
#  process_leaderboard.py
#  Runs inside GitHub Actions — reads raw_players.json from
#  the Rust server, resolves Steam names, writes leaderboard.json
# ============================================================

import json
import os
import requests
from datetime import datetime, timezone

RAW_FILE       = "raw_players.json"
OUTPUT_FILE    = "leaderboard.json"
TOP_N          = 10
STEAM_API_KEY  = os.environ.get("STEAM_API_KEY", "")

# ── Load raw plugin data ──────────────────────────────────────────────────────
try:
    with open(RAW_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)
except FileNotFoundError:
    print(f"ERROR: {RAW_FILE} not found — SFTP download may have failed.")
    exit(1)
except json.JSONDecodeError as e:
    print(f"ERROR: Could not parse {RAW_FILE}: {e}")
    exit(1)

# ── raw is a dict of { "steamId": { "TotalKills": N, "CurrentStreak": N } }
# Sort by TotalKills descending, take top 10
sorted_players = sorted(
    raw.items(),
    key=lambda x: x[1].get("TotalKills", 0),
    reverse=True
)[:TOP_N]

if not sorted_players:
    print("No player data found — writing empty leaderboard.")
    result = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "wipe":    "Current Wipe",
        "players": []
    }
    with open(OUTPUT_FILE, "w") as f:
        json.dump(result, f, indent=2)
    exit(0)

steam_ids = [pid for pid, _ in sorted_players]

# ── Resolve Steam names via Steam API ────────────────────────────────────────
name_map = {}

if STEAM_API_KEY:
    try:
        ids_str = ",".join(steam_ids)
        url     = f"https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/?key={STEAM_API_KEY}&steamids={ids_str}"
        res     = requests.get(url, timeout=10)
        data    = res.json()

        for profile in data.get("response", {}).get("players", []):
            name_map[profile["steamid"]] = profile.get("personaname", profile["steamid"])

        print(f"Resolved {len(name_map)} Steam names.")
    except Exception as e:
        print(f"WARNING: Steam API lookup failed: {e}. Using Steam IDs as names.")
else:
    print("WARNING: No STEAM_API_KEY set — using Steam IDs as player names.")
    print("         Add it as a GitHub Secret to show real player names.")

# ── Build leaderboard entries ─────────────────────────────────────────────────
players_out = []
for steam_id, pdata in sorted_players:
    kills  = pdata.get("TotalKills", 0)
    streak = pdata.get("CurrentStreak", 0)
    name   = name_map.get(steam_id, f"Player_{steam_id[-4:]}")

    players_out.append({
        "name":   name,
        "clan":   "",        # Clan data not in player file — leave blank
        "kills":  kills,
        "streak": streak,
        "id":     steam_id
    })

# ── Read previous leaderboard to preserve wipe field ─────────────────────────
wipe_label = "Current Wipe"
try:
    with open(OUTPUT_FILE, "r") as f:
        prev = json.load(f)
        wipe_label = prev.get("wipe", wipe_label)
except Exception:
    pass

# ── Write output ──────────────────────────────────────────────────────────────
result = {
    "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    "wipe":    wipe_label,
    "players": players_out
}

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(result, f, indent=2, ensure_ascii=False)

print(f"leaderboard.json written with {len(players_out)} players.")
for i, p in enumerate(players_out, 1):
    print(f"  {i:2}. {p['name']:<24} {p['kills']:>4} kills")
