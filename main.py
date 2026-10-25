import os
import sys
import time
import requests

# 1. Read keys from environment variables (Secrets)
# (Fallback to pasted strings if running outside GitHub Actions)
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "PASTE_WEBHOOK_IF_TESTING_LOCALLY")
TORN_API_KEY = os.environ.get("TORN_API_KEY", "PASTE_KEY_IF_TESTING_LOCALLY")
PING_TARGET = "@here"

if not DISCORD_WEBHOOK_URL or "PASTE" in DISCORD_WEBHOOK_URL:
    print("Missing DISCORD_WEBHOOK_URL secret.")
    sys.exit(1)

# Milestones configuration
CHAIN_MILESTONES = [
    20, 40, 85, 90, 95, 100, 
    120, 150, 200, 210, 220, 225, 230, 235, 240, 245, 250
]
MAJOR_BONUSES = {10, 25, 50, 100, 250, 500}

# --- STARTUP TEST MESSAGE ---
# This fires once as soon as GitHub Actions spins up
try:
    test_payload = {
        "content": "🟢 **Radar Online!** Cloud connection verified. Watching for enemy chains...",
        "username": "Faction War Radar"
    }
    requests.post(DISCORD_WEBHOOK_URL, json=test_payload, timeout=10)
    print("Discord test message delivered successfully!")
except Exception as e:
    print(f"Failed to post test message: {e}")
# ----------------------------

notified_milestones = set()
last_chain_count = 0
current_war_id = None

def send_alert(enemy_name, hits, is_bonus=False):
    if is_bonus:
        headline = f"🚨 **CRITICAL: {enemy_name.upper()} HIT BONUS AT {hits} HITS!**"
        action = "**LOCK DOWN!** Enemy landed a bonus. Check revives are OFF and stay in hosp."
    elif hits >= 85 and hits < 100:
        headline = f"⚠️ **HIGH ALERT: {enemy_name} at {hits}/100!**"
        action = "**SELF-HOSP NOW!** They are pushing for the 100-hit bonus. Blood bag / travel!"
    elif hits >= 220 and hits < 250:
        headline = f"⚠️ **EXTREME DANGER: {enemy_name} at {hits}/250!**"
        action = "**STAY IN HOSP!** They are closing in on the 250-hit bonus!"
    else:
        headline = f"⚔️ **Enemy Chain: {enemy_name} reached {hits} hits**"
        action = "Offline/idle members must self-hosp so you do not leak free hits."

    payload = {
        "content": f"{PING_TARGET}\n{headline}\n📊 **Chain:** `{hits}`\n🎯 **Action:** {action}",
        "username": "Faction War Radar"
    }
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
    except Exception as e:
        print(f"Webhook error: {e}")

print("Faction War Radar active. Waiting for / monitoring wars...")

while True:
    try:
        faction_url = f"https://api.torn.com/faction/?selections=rankedwars,basic&key={TORN_API_KEY}"
        res = requests.get(faction_url, timeout=10).json()

        if "error" in res:
            print(f"Torn API error: {res['error']}")
            time.sleep(30)
            continue

        my_faction_id = res.get("ID")
        ranked_wars = res.get("rankedwars", {})

        if not ranked_wars:
            print("No active ranked war. Checking again in 60s...")
            time.sleep(60)
            continue

        active_war_id = list(ranked_wars.keys())[0]
        war_info = ranked_wars[active_war_id]
        factions_in_war = war_info.get("factions", {})

        enemy_id = None
        for fid in factions_in_war.keys():
            if str(fid) != str(my_faction_id):
                enemy_id = str(fid)
                break

        if not enemy_id:
            time.sleep(15)
            continue

        if active_war_id != current_war_id:
            current_war_id = active_war_id
            notified_milestones.clear()
            last_chain_count = 0
            enemy_name = factions_in_war[enemy_id].get("name", "Enemy")
            print(f"Active Ranked War detected against {enemy_name} [{enemy_id}]!")

        enemy_chain_url = f"https://api.torn.com/faction/{enemy_id}?selections=chain,basic&key={TORN_API_KEY}"
        enemy_data = requests.get(enemy_chain_url, timeout=10).json()
        
        enemy_name = enemy_data.get("name", "Enemy")
        chain_info = enemy_data.get("chain", {})
        current_hits = chain_info.get("current", 0)

        if current_hits < last_chain_count:
            notified_milestones.clear()

        for milestone in CHAIN_MILESTONES:
            if current_hits >= milestone and milestone not in notified_milestones:
                send_alert(enemy_name, current_hits, is_bonus=(milestone in MAJOR_BONUSES))
                notified_milestones.add(milestone)

        last_chain_count = current_hits

    except Exception as e:
        print(f"Loop error: {e}")

    time.sleep(15)
