from http.server import BaseHTTPRequestHandler
import json
import random
import numpy as np
import os

# ==========================================
# 0. LOAD THE ML BRAIN
# ==========================================
VIRUS_BRAIN = {}
try:
    with open('virus_brain.json', 'r') as f:
        VIRUS_BRAIN = json.load(f)
except:
    print("WARNING: ML Brain not found. Using default behavior.")

def get_virus_action(inf, trust, cure):
    """
    Decide virus strategy using Q-table.
    Returns:
    0 = Grow
    1 = Mutate (Aggressive)
    2 = Dormant (Stealth)
    """
    inf_lvl = 0 if inf < 30 else (1 if inf < 70 else 2)
    trust_lvl = 0 if trust < 30 else (1 if trust < 70 else 2)
    cure_lvl = 0 if cure < 30 else (1 if cure < 70 else 2)

    key = f"{inf_lvl}{trust_lvl}{cure_lvl}"

    if key in VIRUS_BRAIN:
        return int(np.argmax(VIRUS_BRAIN[key]))

    return 0  # safe fallback

# ==========================================
# 1. MASTER EVENT DATABASE
# (UNCHANGED – YOUR FULL EVENTS STAY AS IS)
# ==========================================
STORY_ARCS = {
    1: {
        "text": "DAY 1: PATIENT ZERO\nSurveillance satellites detected a bio-anomaly in Sector 4.",
        "choices": [
            {"text": "[KAEL] Total Blockade.", "mods": {"eco": -10, "inf": -5, "trust": -10}},
            {"text": "[ARIS] Contact Tracing.", "mods": {"eco": -2, "inf": 5, "trust": 5}},
            {"text": "Cover it up.", "mods": {"inf": 10, "trust": -5}},
            {"text": "Request WHO help.", "mods": {"eco": -5, "trust": 2}}
        ]
    },
    5: {
        "text": "DAY 5: CONTAINMENT BREACH\nThe virus has crossed state lines.",
        "choices": [
            {"text": "Close borders.", "mods": {"eco": -15, "trust": -5}},
            {"text": "Screen travelers.", "mods": {"inf": 8, "trust": 5}},
            {"text": "Do nothing.", "mods": {"inf": 15, "trust": -10}}
        ]
    }
}

# --- MUTATION ARC ---
MUTATION_ARC = {
    "mut_start": {
        "text": "CRISIS: MUTATED STRAIN DETECTED",
        "choices": [
            {"text": "Ignore it.", "mods": {"inf": 5}, "next_fixed": "mut_ignore"},
            {"text": "Prioritize new strain.", "mods": {"inf": 15, "cure": 10}, "next_fixed": "mut_treat_1"},
            {"text": "Total lockdown.", "mods": {"eco": -20, "inf": -5}, "next_fixed": "mut_treat_1"}
        ]
    },
    "mut_ignore": {
        "text": "RESULT: Hospitals overwhelmed.",
        "choices": [
            {"text": "Build field hospitals.", "mods": {"eco": -10}},
            {"text": "Triage.", "mods": {"trust": -20}}
        ]
    },
    "mut_treat_1": {
        "text": "RESULT: Labs racing against time.",
        "choices": [
            {"text": "Hold line.", "mods": {"inf": 10, "cure": 15}},
            {"text": "Experimental blockers.", "mods": {"cure": 20}}
        ]
    }
}

# --- RANDOM EVENTS ---
RANDOM_POOL = {
    "e1": {
        "text": "SITUATION: OXYGEN LEAK",
        "choices": [
            {"text": "Divert oxygen.", "mods": {"eco": -5}},
            {"text": "Ration.", "mods": {"trust": -10}},
            {"text": "Import.", "mods": {"eco": -15}}
        ]
    }
}

# ==========================================
# 2. ML-ENHANCED SIMULATION ENGINE
# ==========================================
def run_simulation(current_stats, choice_mods):
    stats = current_stats.copy()

    # Apply choice mods
    for k, v in choice_mods.items():
        if k in stats:
            stats[k] = max(0, min(100, stats[k] + v))

    stats['day'] = stats.get('day', 1) + 1

    # --- AI VIRUS DECISION ---
    ai_action = get_virus_action(
        stats['inf'],
        stats['trust'],
        stats.get('cure', 0)
    )

    narrative_flavor = ""
    r0 = 1.5

    if ai_action == 0:
        narrative_flavor = "Virus spreading steadily."
    elif ai_action == 1:
        r0 = 2.5
        stats['cure'] = min(100, stats.get('cure', 0) + 2)
        narrative_flavor = "Virus mutates aggressively."
    elif ai_action == 2:
        r0 = 0.8
        stats['trust'] = max(0, stats['trust'] - 2)
        narrative_flavor = "Virus activity drops unexpectedly."

    compliance = stats['trust'] / 100.0
    activity = stats['eco'] / 100.0

    if stats.get('mutated_strain_active'):
        r0 += 1.0

    r_eff = (r0 * (0.5 + 0.5 * activity)) * (1 - 0.4 * compliance)

    inf = stats['inf']
    growth = (r_eff * inf) - inf

    if stats.get('cure', 0) > 50:
        growth -= (stats['cure'] - 50) * 0.1

    growth += np.random.normal(0, 1.5)
    stats['inf'] = round(max(0, min(100, inf + growth)), 1)

    decay = 0.2 + (0.5 if stats['inf'] > 30 else 0)
    stats['eco'] = round(max(0, stats['eco'] - decay), 1)

    return stats, narrative_flavor

# ==========================================
# 3. GAME MANAGER (UNCHANGED)
# ==========================================
def get_next_event(stats, used_events, forced_next):
    if forced_next and forced_next in MUTATION_ARC:
        if forced_next == "mut_treat_1":
            stats['mutated_strain_active'] = True
            stats['mutated_strain_curing'] = True
        elif forced_next == "mut_ignore":
            stats['mutated_strain_active'] = True
            stats['mutated_strain_curing'] = False
        return forced_next, MUTATION_ARC[forced_next]

    if stats['day'] > 15 and "mut_start" not in used_events and random.random() < 0.3:
        return "mut_start", MUTATION_ARC["mut_start"]

    day = stats.get('day', 1)
    if day in STORY_ARCS:
        return f"day_{day}", STORY_ARCS[day]

    return "quiet_day", {
        "text": "STATUS: QUIET DAY",
        "choices": [
            {"text": "Fortify economy.", "mods": {"eco": 2}},
            {"text": "Boost health.", "mods": {"pop": 1}},
            {"text": "Rest.", "mods": {"trust": 1}}
        ]
    }

# ==========================================
# 4. VERCEL HANDLER
# ==========================================
class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            l = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(l))

            stats = data.get('stats', {})
            choice_idx = data.get('choice_index')
            last_event_id = data.get('last_event_id')
            used_events = data.get('used_events', [])
            is_init = data.get('is_init', False)

            if is_init:
                new_stats = {
                    "day": 1, "pop": 100, "trust": 70,
                    "eco": 80, "inf": 5, "cure": 0
                }
                next_id = "day_1"
                next_event = STORY_ARCS[1]
                used_events = ["day_1"]
                flavor = ""
            else:
                prev = (
                    MUTATION_ARC.get(last_event_id) or
                    STORY_ARCS.get(int(last_event_id.split("_")[1]))
                    if last_event_id.startswith("day_") else
                    RANDOM_POOL.get(last_event_id)
                )

                choice_mods = {}
                next_fixed = None
                if prev and choice_idx is not None:
                    sel = prev["choices"][choice_idx]
                    choice_mods = sel.get("mods", {})
                    next_fixed = sel.get("next_fixed")

                new_stats, flavor = run_simulation(stats, choice_mods)
                next_id, next_event = get_next_event(new_stats, used_events, next_fixed)
                used_events.append(next_id)

            text = next_event["text"]
            if flavor:
                text += f"\n\n[AI ANALYSIS]: {flavor}"

            self.send_json({
                "stats": new_stats,
                "narrative": text,
                "choices": next_event["choices"],
                "event_id": next_id,
                "used_events": used_events
            })

        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode())

    def send_json(self, d):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(d).encode())
