from http.server import BaseHTTPRequestHandler
import json
import random
import numpy as np

# ==========================================
# 1. THE MASTER EVENT DATABASE (35+ EVENTS)
# ==========================================
STORY_ARCS = {
    1: {
        "text": "DAY 1: PATIENT ZERO\nSurveillance satellites detected a bio-anomaly in Sector 4. The initial reports are confusing.",
        "choices": [
            {"text": "[KAEL] Total Blockade. (Trust -10, Eco -10, Inf -5)", "mods": {"eco": -10, "inf": -5, "trust": -10, "kael_loyalty": 10}},
            {"text": "[ARIS] Contact Tracing Team. (Eco -2, Trust +5)", "mods": {"eco": -2, "inf": 5, "trust": 5, "aris_loyalty": 10}},
            {"text": "Cover it up to prevent panic. (Trust -5, Inf +10)", "mods": {"eco": 2, "inf": 10, "trust": -5}},
            {"text": "Request WHO intervention. (Trust +2, Eco -5)", "mods": {"eco": -5, "trust": 2, "inf": -2}}
        ]
    },
    # ... (Day 5, 12, etc. remain as fixed anchor points) ...
    5: { "text": "DAY 5: CONTAINMENT BREACH\nThe virus has crossed state lines.", "choices": [{"text": "Close domestic borders.", "mods": {"eco": -15, "trust": -5}}, {"text": "Screen travelers.", "mods": {"inf": 8, "trust": 5}}, {"text": "Do nothing.", "mods": {"inf": 15, "trust": -10}}] },
}

# --- SPECIAL ARC: THE MUTATED STRAIN ---
MUTATION_ARC = {
    "mut_start": {
        "text": "CRISIS: MUTATED STRAIN DETECTED\nA new, more aggressive variant is spreading. Standard treatments are failing.",
        "choices": [
            {"text": "Focus on Original Strain (Stable short-term).", "mods": {"inf": 5}, "next_fixed": "mut_ignore"},
            {"text": "Prioritize New Strain (High Inf Spike now, Cure later).", "mods": {"inf": 15, "cure": 10}, "next_fixed": "mut_treat_1"},
            {"text": "Lockdown everything to study it.", "mods": {"eco": -20, "inf": -5}, "next_fixed": "mut_treat_1"}
        ]
    },
    "mut_ignore": {
        "text": "RESULT: THE WAVE\nIgnoring the new strain was a mistake. Hospitals are overwhelmed.",
        "choices": [
            {"text": "Build field hospitals.", "mods": {"eco": -10, "pop": -2}},
            {"text": "Triage patients.", "mods": {"trust": -20, "pop": -5}}
        ]
    },
    "mut_treat_1": {
        "text": "RESULT: SHORT TERM PAIN\nInfection is spreading fast while labs re-tool, but we are learning its weakness.",
        "choices": [
            {"text": "Hold the line.", "mods": {"inf": 10, "cure": 15}},
            {"text": "Release experimental blockers.", "mods": {"pop": -2, "cure": 20}}
        ]
    },
    "mut_treat_success": {
        "text": "VICTORY: BREAKTHROUGH\nThe new protocols are working. The virus is collapsing.",
        "choices": [{"text": "Excellent.", "mods": {"inf": -20, "cure": 10, "trust": 10}}]
    }
}

# --- RANDOM POOL (35+ EVENTS) ---
RANDOM_POOL = {
    "e1": { "text": "SITUATION: OXYGEN LEAK\nMain tank ruptured.", "choices": [{"text": "Divert industrial oxygen.", "mods": {"eco": -5}}, {"text": "Ration oxygen.", "mods": {"pop": -2, "trust": -10}}, {"text": "Import at 300% cost.", "mods": {"eco": -15, "trust": 5}}] },
    "e2": { "text": "SITUATION: PRISON OUTBREAK", "choices": [{"text": "Release non-violent.", "mods": {"trust": -5, "inf": 2}}, {"text": "Lockdown.", "mods": {"trust": -5}}, {"text": "Ignore.", "mods": {"inf": 5, "trust": -10}}] },
    "e3": { "text": "SITUATION: TRANSPORT STRIKE", "choices": [{"text": "Pay them.", "mods": {"eco": -5}}, {"text": "Military drivers.", "mods": {"trust": -5}}, {"text": "Arrest leaders.", "mods": {"trust": -15, "eco": -5}}] },
    "e4": { "text": "SITUATION: CELEBRITY HOAX", "choices": [{"text": "Arrest pop star.", "mods": {"trust": -5}}, {"text": "Ignore.", "mods": {"inf": 5}}, {"text": "Counter-campaign.", "mods": {"eco": -2}}] },
    "e5": { "text": "SITUATION: BLACK MARKET MEDICINE", "choices": [{"text": "Raids.", "mods": {"trust": -5}}, {"text": "Buy back stock.", "mods": {"eco": -10}}, {"text": "Legalize & Tax.", "mods": {"eco": 5, "trust": -10, "pop": -2}}] },
    "e6": { "text": "SITUATION: FOREIGN SPIES", "choices": [{"text": "Execute.", "mods": {"trust": 5, "eco": -5}}, {"text": "Trade.", "mods": {"trust": -10, "eco": 5}}, {"text": "Double agent.", "mods": {"inf": 2}}] },
    "e7": { "text": "SITUATION: BANK RUN", "choices": [{"text": "Freeze banks.", "mods": {"trust": -15}}, {"text": "Print money.", "mods": {"eco": -15}}, {"text": "Bailout.", "mods": {"eco": -10, "trust": -5}}] },
    "e8": { "text": "SITUATION: TEACHERS STRIKE", "choices": [{"text": "Close schools.", "mods": {"eco": -5, "inf": -2}}, {"text": "Fire them.", "mods": {"trust": -10}}, {"text": "Hybrid classes.", "mods": {"eco": -2, "inf": 2}}] },
    "e9": { "text": "SITUATION: REFUGEES", "choices": [{"text": "Let them in.", "mods": {"inf": 8, "trust": 5}}, {"text": "Turn back.", "mods": {"trust": -5}}, {"text": "Camps.", "mods": {"eco": -5, "inf": 2}}] },
    "e10": { "text": "SITUATION: PRICE GOUGING", "choices": [{"text": "Seize stock.", "mods": {"trust": 5, "eco": -2}}, {"text": "Free market.", "mods": {"trust": -10}}, {"text": "Subsidize.", "mods": {"eco": -5}}] },
    "e11": { "text": "SITUATION: RELIGIOUS CULT", "choices": [{"text": "Raid compound.", "mods": {"trust": -10, "pop": -1}}, {"text": "Ignore.", "mods": {"inf": 5}}, {"text": "Negotiate.", "mods": {"trust": 2, "inf": 2}}] },
    "e12": { "text": "SITUATION: ZOO ANIMALS STARVING", "choices": [{"text": "Feed them.", "mods": {"eco": -2}}, {"text": "Euthanize.", "mods": {"trust": -5}}, {"text": "Release herbivores.", "mods": {"trust": -2}}] },
    "e13": { "text": "SITUATION: WATER CONTAMINATION", "choices": [{"text": "Fix immediately.", "mods": {"eco": -8}}, {"text": "Ration water.", "mods": {"trust": -10}}, {"text": "Cover up.", "mods": {"pop": -5, "trust": -20}}] },
    "e14": { "text": "SITUATION: INTERNET BLACKOUT", "choices": [{"text": "Restore grid.", "mods": {"eco": -5}}, {"text": "Prioritize military.", "mods": {"trust": -10}}, {"text": "Blame enemies.", "mods": {"trust": 5, "eco": -2}}] },
    "e15": { "text": "SITUATION: LOOTING WAVE", "choices": [{"text": "Shoot on sight.", "mods": {"pop": -2, "trust": -20}}, {"text": "Curfew.", "mods": {"eco": -5, "inf": -2}}, {"text": "Ignore.", "mods": {"eco": -10}}] },
    "e16": { "text": "SITUATION: FARMER PROTEST", "choices": [{"text": "Subsidies.", "mods": {"eco": -5}}, {"text": "Import food.", "mods": {"eco": -10}}, {"text": "Force harvest.", "mods": {"trust": -15}}] },
    "e17": { "text": "SITUATION: CRUISE SHIP DOCKING", "choices": [{"text": "Allow.", "mods": {"inf": 5, "trust": 5}}, {"text": "Refuse.", "mods": {"trust": -5}}, {"text": "Quarantine offshore.", "mods": {"eco": -5}}] },
    "e18": { "text": "SITUATION: TRASH PILEUP", "choices": [{"text": "Burn it.", "mods": {"pop": -1}}, {"text": "Army cleanup.", "mods": {"trust": 5, "eco": -2}}, {"text": "Ignore.", "mods": {"trust": -5, "inf": 2}}] },
    "e19": { "text": "SITUATION: SENATOR SCANDAL", "choices": [{"text": "Resign.", "mods": {"trust": 5}}, {"text": "Cover up.", "mods": {"trust": -15}}, {"text": "Blame media.", "mods": {"trust": -5}}] },
    "e20": { "text": "SITUATION: CRYPTO CRASH", "choices": [{"text": "Bailout.", "mods": {"eco": -5}}, {"text": "Ignore.", "mods": {"trust": -5}}, {"text": "Investigate.", "mods": {"eco": -2}}] },
    "e21": { "text": "SITUATION: WILDFIRES", "choices": [{"text": "Evacuate.", "mods": {"inf": 5}}, {"text": "Stay put.", "mods": {"pop": -2}}, {"text": "Cloud seed.", "mods": {"eco": -5}}] },
    "e22": { "text": "SITUATION: HACKER ATTACK", "choices": [{"text": "Pay ransom.", "mods": {"eco": -10}}, {"text": "Rebuild data.", "mods": {"eco": -5, "trust": -5}}, {"text": "Counter-attack.", "mods": {"eco": -8}}] },
    "e23": { "text": "SITUATION: OIL SPILL", "choices": [{"text": "Clean up.", "mods": {"eco": -5}}, {"text": "Ignore.", "mods": {"trust": -5}}, {"text": "Burn it.", "mods": {"pop": -1}}] },
    "e24": { "text": "SITUATION: SPORTING FINALS", "choices": [{"text": "Cancel.", "mods": {"trust": -10, "eco": -5}}, {"text": "Play empty.", "mods": {"eco": -2}}, {"text": "Full crowd.", "mods": {"inf": 10, "eco": 10}}] },
    "e25": { "text": "SITUATION: ROGUE SCIENTIST", "choices": [{"text": "Use data.", "mods": {"cure": 10, "trust": -10}}, {"text": "Arrest.", "mods": {"trust": 5}}, {"text": "Fund him.", "mods": {"eco": -5, "cure": 5}}] },
    "e26": { "text": "SITUATION: BORDER WALL", "choices": [{"text": "Reinforce.", "mods": {"eco": -5}}, {"text": "Open gates.", "mods": {"inf": 5}}, {"text": "Drones.", "mods": {"eco": -2}}] },
    "e27": { "text": "SITUATION: GOLD RESERVES", "choices": [{"text": "Sell.", "mods": {"eco": 10, "trust": -5}}, {"text": "Hold.", "mods": {"trust": 2}}, {"text": "Buy more.", "mods": {"eco": -10}}] },
    "e28": { "text": "SITUATION: SATELLITE DEBRIS", "choices": [{"text": "Salvage.", "mods": {"eco": 5}}, {"text": "Warn public.", "mods": {"trust": 2}}, {"text": "Secret recovery.", "mods": {"trust": -2}}] },
    "e29": { "text": "SITUATION: HERBAL REMEDY FAD", "choices": [{"text": "Ban it.", "mods": {"trust": -5}}, {"text": "PSA.", "mods": {"eco": -1}}, {"text": "Tax it.", "mods": {"eco": 2, "pop": -1}}] },
    "e30": { "text": "SITUATION: ARMY DESERTION", "choices": [{"text": "Court martial.", "mods": {"trust": -10}}, {"text": "Pay bonus.", "mods": {"eco": -5}}, {"text": "Ignore.", "mods": {"trust": -5}}] },
    "e31": { "text": "SITUATION: GHOST TOWNS", "choices": [{"text": "Burn.", "mods": {"trust": -5}}, {"text": "Seal.", "mods": {"trust": -2}}, {"text": "Loot.", "mods": {"eco": 5, "trust": -10}}] },
    "e32": { "text": "SITUATION: DATA LEAK", "choices": [{"text": "Deny.", "mods": {"trust": -10}}, {"text": "Apologize.", "mods": {"trust": 5}}, {"text": "Distract.", "mods": {"eco": -5}}] },
    "e33": { "text": "SITUATION: MASS SUICIDE PACT", "choices": [{"text": "Intervene.", "mods": {"trust": 5}}, {"text": "Ignore.", "mods": {"pop": -1}}, {"text": "Censor news.", "mods": {"trust": -5}}] },
    "e34": { "text": "SITUATION: CLIMATE PROTEST", "choices": [{"text": "Arrest.", "mods": {"trust": -5}}, {"text": "Listen.", "mods": {"eco": -2}}, {"text": "Ignore.", "mods": {"trust": -2}}] },
    "e35": { "text": "SITUATION: AI PREDICTION", "choices": [{"text": "Trust AI.", "mods": {"eco": 5, "trust": -5}}, {"text": "Trust Humans.", "mods": {"trust": 5}}, {"text": "Shut it down.", "mods": {"eco": -5}}] }
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
            
    # 2. Time Progression
    stats['day'] = stats.get('day', 1) + 1
    
    # 3. Biology Math
    r0 = 1.5
    compliance = stats['trust'] / 100.0
    activity = stats['eco'] / 100.0
    
    # Mutated Strain Logic (If active, R0 is higher)
    if stats.get('mutated_strain_active', False):
        r0 = 2.5 # Aggressive
        if stats.get('mutated_strain_curing', False):
            r0 = 0.5 # Dropping fast because we treated it

    r_effective = (r0 * (0.5 + 0.5 * activity)) * (1.0 - (0.4 * compliance))
    
    inf = stats['inf']
    growth = (r_effective * inf) - inf
    
    if stats.get('cure', 0) > 50: growth -= (stats['cure'] - 50) * 0.1
    growth += np.random.normal(0, 1.5)
    
    stats['inf'] = round(max(0, min(100, inf + growth)), 1)
    
    # 4. Economy Decay
    decay = 0.2
    if stats['inf'] > 30: decay += 0.5
    stats['eco'] = round(max(0, stats['eco'] - decay), 1)

    return stats

# ==========================================
# 3. GAME MANAGER
# ==========================================
def get_next_event(stats, used_events, forced_next):
    # A. Priority: Forced Path (Sub-plot/Mutation)
    if forced_next:
        if forced_next in MUTATION_ARC:
            # Handle Mutation Logic Flags
            if forced_next == "mut_treat_1":
                stats['mutated_strain_active'] = True
                stats['mutated_strain_curing'] = True
            elif forced_next == "mut_ignore":
                stats['mutated_strain_active'] = True
                stats['mutated_strain_curing'] = False
            return forced_next, MUTATION_ARC[forced_next]
        
        # Check standard endings...
        if "ending_" in forced_next: return forced_next, get_ending_content(forced_next)

    # B. Priority: Mutation Trigger (Day 20 or High Inf)
    if stats['day'] > 15 and "mut_start" not in used_events and random.random() < 0.3:
        return "mut_start", MUTATION_ARC["mut_start"]

    # C. Priority: Standard Story Arc
    day = stats.get('day', 1)
    if day in STORY_ARCS:
        return f"day_{day}", STORY_ARCS[day]

    # D. Priority: Random Event (Max 2 occurrences)
    # Get all events where count < 2
    available = []
    for eid in RANDOM_POOL.keys():
        count = used_events.count(eid)
        if count < 2:
            available.append(eid)
            
    if not available:
        return "quiet_day", {"text": "STATUS: QUIET DAY\nNo major incidents reported.", "choices": [{"text": "Fortify Economy", "mods": {"eco": 2}}, {"text": "Boost Health", "mods": {"pop": 1}}, {"text": "Rest.", "mods": {"trust": 1}}]}
    
    eid = random.choice(available)
    return eid, RANDOM_POOL[eid]

def get_ending_content(ending_id):
    endings = {
        "ending_extinction": {"text": "ENDING: SILENT EARTH\nPopulation Collapsed.", "choices": []},
        "ending_revolution": {"text": "ENDING: THE GUILLOTINE\nTrust Collapsed.", "choices": []},
        "ending_coup_loss": {"text": "ENDING: MILITARY STATE\nCoup Successful.", "choices": []},
        "ending_victory": {"text": "ENDING: VICTORY\nVirus Eradicated.", "choices": []}
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
            used_events = data.get('used_events', [])
            is_init = data.get('is_init', False)

            if is_init:
                new_stats = {"day": 1, "pop": 100, "trust": 70, "eco": 80, "inf": 5, "cure": 0}
                next_id = "day_1"
                next_event = STORY_ARCS[1]
                used_events = ["day_1"]
            else:
                # Retrieve Previous Event
                prev_event = None
                if last_event_id in MUTATION_ARC: prev_event = MUTATION_ARC[last_event_id]
                elif last_event_id.startswith("day_"): prev_event = STORY_ARCS.get(int(last_event_id.split("_")[1]))
                elif last_event_id in RANDOM_POOL: prev_event = RANDOM_POOL[last_event_id]
                
                # Apply Mods
                choice_mods = {}
                next_fixed = None
                if prev_event and choice_idx is not None and 0 <= choice_idx < len(prev_event["choices"]):
                    sel = prev_event["choices"][choice_idx]
                    choice_mods = sel.get("mods", {})
                    next_fixed = sel.get("next_fixed")

                new_stats = run_simulation(stats, choice_mods)
                
                # Pick Next
                next_id, next_event = get_next_event(new_stats, used_events, next_fixed)
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
