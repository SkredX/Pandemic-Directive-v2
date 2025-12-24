from http.server import BaseHTTPRequestHandler
import json
import random
import numpy as np

# ==========================================
# 1. THE MASTER EVENT DATABASE
# ==========================================
STORY_ARCS = {
    1: {
        "text": "DAY 1: PATIENT ZERO\nSurveillance satellites detected a bio-anomaly in Sector 4. General Kael urges a total blockade. Dr. Aris suggests contact tracing.",
        "choices": [
            {"text": "[KAEL] Total Blockade (High Eco Dmg)", "mods": {"eco": -10, "inf": -5, "trust": -5, "kael_loyalty": 10}},
            {"text": "[ARIS] Contact Tracing (Slow)", "mods": {"eco": -2, "inf": 5, "trust": 5, "aris_loyalty": 10}},
            {"text": "Ignore it. It's just the flu.", "mods": {"eco": 5, "inf": 15, "trust": 0}}
        ]
    },
    5: {
        "text": "DAY 5: CONTAINMENT BREACH\nThe virus has crossed state lines. Panic is setting in.",
        "choices": [
            {"text": "Close domestic borders.", "mods": {"eco": -15, "trust": -5}},
            {"text": "Screen travelers only.", "mods": {"inf": 8, "trust": 5}}
        ]
    },
    12: {
        "text": "DAY 12: THE SHORTAGE\nOut of ventilators. Critical care units are overflowing.",
        "choices": [
            {"text": "Prioritize workers (Utilitarian).", "mods": {"trust": -15, "kael_loyalty": 15}},
            {"text": "Lottery system (Fairness).", "mods": {"trust": 5, "aris_loyalty": 10}}
        ]
    },
    18: {
        "text": "DAY 18: VACCINE TRIALS\nA risky prototype is ready. It hasn't been tested on humans.",
        "choices": [
            {"text": "Human testing (Fast/Risky).", "mods": {"cure": 35, "trust": -10, "pop": -2}},
            {"text": "Wait for animal trials (Safe/Slow).", "mods": {"cure": 5}}
        ]
    }
}

# Sub-plots and Endings are treated as "Special Events"
SPECIAL_EVENTS = {
    "coup_1": {
        "text": "SUB-PLOT: RED FLAG\nGeneral Kael has deployed tanks around the capitol without your order.",
        "choices": [
            {"text": "Order him to stand down.", "mods": {"trust": 5}, "next_fixed": "coup_2a"},
            {"text": "Authorize the deployment.", "mods": {"trust": -10, "inf": -5}, "next_fixed": "coup_2b"}
        ]
    },
    "coup_2a": { 
        "text": "SUB-PLOT: THE STANDOFF\nKael refuses. His troops are aiming at the palace.",
        "choices": [
            {"text": "Resign (Game Over).", "mods": {}, "next_fixed": "ending_coup_loss"},
            {"text": "Call the Air Force (Civil War).", "mods": {"pop": -20}, "next_fixed": "coup_3_war"}
        ]
    },
    "coup_2b": {
        "text": "SUB-PLOT: MARTIAL LAW\nThe streets are quiet. Kael suggests canceling elections.",
        "choices": [
            {"text": "Agree.", "mods": {"trust": -20}, "next_fixed": "ending_coup_loss"},
            {"text": "Refuse.", "mods": {"trust": 5}, "next_fixed": "coup_2a"}
        ]
    },
    "coup_3_war": { "text": "ENDING: CIVIL WAR\nThe nation has fallen.", "choices": [] },
    "ending_coup_loss": { "text": "ENDING: MILITARY STATE\nGeneral Kael rules now.", "choices": [] }
}

# Random Pool (IDs must match what we store in used_events)
RANDOM_POOL = {
    "e1": { "text": "SITUATION: OXYGEN LEAK\nA main oxygen tank has ruptured.", "choices": [{"text": "Divert industrial oxygen.", "mods": {"eco": -5}}, {"text": "Ration oxygen.", "mods": {"pop": -2, "trust": -10}}] },
    "e2": { "text": "SITUATION: PRISON OUTBREAK\nInfection spreading in maximum security.", "choices": [{"text": "Release non-violent offenders.", "mods": {"trust": -10, "inf": 2}}, {"text": "Lock them in.", "mods": {"trust": -5}}] },
    "e3": { "text": "SITUATION: TRANSPORT STRIKE\nTruckers refuse to drive.", "choices": [{"text": "Triple hazard pay.", "mods": {"eco": -8}}, {"text": "Military drivers.", "mods": {"trust": -5}}] },
    "e4": { "text": "SITUATION: CELEBRITY INFLUENCER\nA pop star calls the virus a hoax.", "choices": [{"text": "Arrest them.", "mods": {"trust": -5}}, {"text": "Ignore it.", "mods": {"inf": 5}}] },
    "e5": { "text": "SITUATION: BLACK MARKET\nGangs selling stolen medicine.", "choices": [{"text": "Raids.", "mods": {"trust": -5}}, {"text": "Buy it back.", "mods": {"eco": -10}}] },
    "e6": { "text": "SITUATION: FOREIGN SPIES\nAgents stealing data.", "choices": [{"text": "Execute them.", "mods": {"trust": 5, "eco": -5}}, {"text": "Trade for supplies.", "mods": {"trust": -10}}] },
    "e7": { "text": "SITUATION: BANK RUN\nPeople draining ATMs.", "choices": [{"text": "Freeze withdrawals.", "mods": {"trust": -15}}, {"text": "Print money.", "mods": {"eco": -15}}] },
    "e8": { "text": "SITUATION: TEACHERS UNION\nRefusing to open schools.", "choices": [{"text": "Close schools.", "mods": {"eco": -5, "inf": -3}}, {"text": "Fire them.", "mods": {"trust": -10, "inf": 5}}] },
    "e9": { "text": "SITUATION: BORDER REFUGEES\nThousands fleeing neighbor state.", "choices": [{"text": "Let them in.", "mods": {"inf": 10}}, {"text": "Turn back.", "mods": {"trust": -5}}] },
    "e10": { "text": "SITUATION: MASK PRICE GOUGING\nPharmacy prices up 500%.", "choices": [{"text": "Seize stock.", "mods": {"trust": 5, "eco": -2}}, {"text": "Free market.", "mods": {"trust": -10}}] }
}

# ==========================================
# 2. SIMULATION ENGINE
# ==========================================
def run_simulation(current_stats, choice_mods):
    stats = current_stats.copy()
    
    # 1. Apply Choice Mods
    for key, val in choice_mods.items():
        if key in stats:
            stats[key] = max(0, min(100, stats[key] + val))
            
    # 2. Math Simulation (Only runs if we are NOT in a sub-plot/ending)
    # If the user is just answering a text prompt, time moves forward.
    stats['day'] = stats.get('day', 1) + 1
    
    # Infection Math
    r0 = 1.5 
    compliance = stats['trust'] / 100.0
    activity = stats['eco'] / 100.0
    r_effective = (r0 * (0.5 + 0.5 * activity)) * (1.0 - (0.4 * compliance))
    
    inf = stats['inf']
    growth = (r_effective * inf) - inf
    if stats.get('cure', 0) > 50: growth -= (stats['cure'] - 50) * 0.1
    growth += np.random.normal(0, 1.5)
    
    stats['inf'] = round(max(0, min(100, inf + growth)), 1)
    
    # Economy & Decay
    decay = 0.2
    if stats['inf'] > 30: decay += 0.5
    stats['eco'] = round(max(0, stats['eco'] - decay), 1)

    return stats

# ==========================================
# 3. GAME MANAGER
# ==========================================
def get_next_event(stats, used_events, forced_next):
    # A. Priority: Forced Path (Sub-plot)
    if forced_next:
        # Check Special Events
        if forced_next in SPECIAL_EVENTS:
            return forced_next, SPECIAL_EVENTS[forced_next]
        # Check Endings
        if "ending_" in forced_next:
            return forced_next, get_ending_content(forced_next)

    # B. Priority: Game Over Conditions
    if stats['pop'] < 10: return "ending_extinction", get_ending_content("ending_extinction")
    if stats['trust'] < 5: return "ending_revolution", get_ending_content("ending_revolution")
    
    # C. Priority: Main Story Arc (Fixed Days)
    day = stats.get('day', 1)
    if day in STORY_ARCS:
        return f"day_{day}", STORY_ARCS[day]
    
    # D. Priority: Trigger Sub-Plots
    if stats['trust'] < 30 and "coup_1" not in used_events and random.random() < 0.4:
        return "coup_1", SPECIAL_EVENTS["coup_1"]

    # E. Fallback: Random Event (Unique)
    # Filter out events we have already used
    available = [eid for eid in RANDOM_POOL.keys() if eid not in used_events]
    
    if not available:
        return "quiet_day", {"text": "STATUS: QUIET DAY\nNo major incidents reported.", "choices": [{"text": "Fortify Economy", "mods": {"eco": 2}}, {"text": "Boost Health", "mods": {"pop": 1}}]}
    
    eid = random.choice(available)
    return eid, RANDOM_POOL[eid]

def get_ending_content(ending_id):
    endings = {
        "ending_extinction": {"text": "ENDING: SILENT EARTH\nThe population has collapsed.", "choices": []},
        "ending_revolution": {"text": "ENDING: THE GUILLOTINE\nThe people stormed the palace.", "choices": []},
        "ending_coup_loss": {"text": "ENDING: MILITARY STATE\nGeneral Kael rules now.", "choices": []}
    }
    return endings.get(ending_id, {"text": "GAME OVER", "choices": []})

# ==========================================
# 4. VERCEL HANDLER
# ==========================================
class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_len = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_len)
            data = json.loads(body)
            
            stats = data.get('stats', {})
            choice_idx = data.get('choice_index')
            last_event_id = data.get('last_event_id')
            used_events = data.get('used_events', []) # Frontend must send this!
            is_init = data.get('is_init', False)

            if is_init:
                # RESET EVERYTHING
                new_stats = {"day": 1, "pop": 100, "trust": 70, "eco": 80, "inf": 5, "cure": 0}
                next_id = "day_1"
                next_event = STORY_ARCS[1]
                used_events = ["day_1"]
            else:
                # 1. Retrieve the Event we just finished
                prev_event = None
                
                # Check where the previous event came from
                if last_event_id.startswith("day_"):
                    day_num = int(last_event_id.split("_")[1])
                    prev_event = STORY_ARCS.get(day_num)
                elif last_event_id in SPECIAL_EVENTS:
                    prev_event = SPECIAL_EVENTS[last_event_id]
                elif last_event_id in RANDOM_POOL:
                    prev_event = RANDOM_POOL[last_event_id]
                
                # 2. Apply Consequences
                choice_mods = {}
                next_fixed = None
                
                if prev_event and choice_idx is not None and 0 <= choice_idx < len(prev_event["choices"]):
                    sel = prev_event["choices"][choice_idx]
                    choice_mods = sel.get("mods", {})
                    next_fixed = sel.get("next_fixed")

                # 3. Simulate World
                new_stats = run_simulation(stats, choice_mods)
                
                # 4. Pick Next Event
                next_id, next_event = get_next_event(new_stats, used_events, next_fixed)
                
                # 5. Update History
                if next_id not in used_events:
                    used_events.append(next_id)

            self.send_json({
                "stats": new_stats, 
                "narrative": next_event["text"], 
                "choices": next_event["choices"], 
                "event_id": next_id,
                "used_events": used_events
            })

        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode('utf-8'))

    def send_json(self, data):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))
