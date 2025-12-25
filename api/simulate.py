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
    pass # Silent fail is better for logs

def get_virus_action(inf, trust, cure):
    inf_lvl = 0 if inf < 30 else (1 if inf < 70 else 2)
    trust_lvl = 0 if trust < 30 else (1 if trust < 70 else 2)
    cure_lvl = 0 if cure < 30 else (1 if cure < 70 else 2)
    
    key = f"{inf_lvl}{trust_lvl}{cure_lvl}"
    if key in VIRUS_BRAIN:
        return int(np.argmax(VIRUS_BRAIN[key]))
    return 0 

# ==========================================
# 1. MASTER EVENT DATABASE
# ==========================================
STORY_ARCS = {
    1: {
        "text": "DAY 1: PATIENT ZERO\nSurveillance satellites detected a bio-anomaly in Sector 4.",
        "choices": [
            {"text": "[KAEL] Total Blockade. (Trust -10, Eco -10)", "mods": {"eco": -10, "inf": -5, "trust": -10}},
            {"text": "[ARIS] Contact Tracing. (Eco -2, Trust +5)", "mods": {"eco": -2, "inf": 5, "trust": 5}},
            {"text": "Cover it up. (Trust -5)", "mods": {"inf": 10, "trust": -5}},
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

MUTATION_ARC = {
    # --- ARC START ---
    "mut_start": {
        "text": "CRISIS: MUTATED STRAIN DETECTED\nLaboratories report a new, aggressive variant 'Omega' appearing in clusters.",
        "choices": [
            {"text": "Prioritize Omega Strain. (High Risk, High Reward)", "mods": {"inf": 10, "cure": 5}, "next_fixed": "mut_strategy_focus"},
            {"text": "Ignore. Focus on Delta. (Safer now, worse later)", "mods": {"inf": 5}, "next_fixed": "mut_strategy_ignore"}
        ]
    },
    "mut_strategy_focus": {
        "text": "STRATEGY: OMEGA PROTOCOL\nWe are shifting all resources to the new strain. Infection will spike while we retool.",
        "choices": [{"text": "Understood.", "mods": {"inf": 15, "cure": 10}}] # Activates mutation arc
    },
    "mut_strategy_ignore": {
        "text": "STRATEGY: STAY THE COURSE\nWe can't afford to pivot now. Omega will burn through the population.",
        "choices": [{"text": "God help us.", "mods": {"trust": -10, "pop": -2}}] # Activates mutation arc (Hard mode)
    },

    # --- THE POOL (10 Events - Game picks 5) ---
    "mut_p1": { "text": "MUTATION: VACCINE RESISTANCE\nThe new strain bypasses our current blockers.", "choices": [{"text": "Start over.", "mods": {"cure": -10, "trust": -5}}, {"text": "Push flawed vaccine.", "mods": {"trust": -20, "pop": -2}}] },
    "mut_p2": { "text": "MUTATION: SYMPTOM CLUSTER\nPatients are bleeding from the eyes. Panic is widespread.", "choices": [{"text": "Censor images.", "mods": {"trust": -5, "eco": 2}}, {"text": "Tell the truth.", "mods": {"trust": 5, "eco": -10}}] },
    "mut_p3": { "text": "MUTATION: LAB ACCIDENT\nFatigue caused a containment breach in our main research lab.", "choices": [{"text": "Cover it up.", "mods": {"trust": -10, "inf": 5}}, {"text": "Evacuate sector.", "mods": {"eco": -5, "inf": -2}}] },
    "mut_p4": { "text": "MUTATION: CHILDREN AFFECTED\nOmega is targeting the youth. Schools are hotspots.", "choices": [{"text": "Close all schools.", "mods": {"eco": -5, "inf": -5}}, {"text": "Remote learning only.", "mods": {"eco": -2, "trust": -2}}] },
    "mut_p5": { "text": "MUTATION: SUPPLY CHAIN COLLAPSE\nTruckers refuse to enter Omega hot-zones.", "choices": [{"text": "Military convoys.", "mods": {"trust": 5, "eco": -5}}, {"text": "Double pay.", "mods": {"eco": -10}}] },
    "mut_p6": { "text": "MUTATION: FALSE HOPE\nA promising treatment turned out to be toxic.", "choices": [{"text": "Recall immediately.", "mods": {"cure": -5, "trust": 5}}, {"text": "Quietly discontinue.", "mods": {"trust": -15, "pop": -1}}] },
    "mut_p7": { "text": "MUTATION: BLACK MARKET CURE\nFake 'Omega Boosters' are killing people.", "choices": [{"text": "Raids.", "mods": {"trust": -5}}, {"text": "PSA Campaign.", "mods": {"eco": -2}}] },
    "mut_p8": { "text": "MUTATION: ANIMAL RESERVOIRS\nHouse pets are carrying the strain.", "choices": [{"text": "Cull pets.", "mods": {"trust": -25, "inf": -5}}, {"text": "Warning only.", "mods": {"inf": 5}}] },
    "mut_p9": { "text": "MUTATION: MEDICAL WALKOUT\nDoctors are exhausted and quitting en masse.", "choices": [{"text": "Draft them.", "mods": {"trust": -15}}, {"text": "Import doctors.", "mods": {"eco": -10, "cure": 5}}] },
    "mut_p10":{ "text": "MUTATION: DATA CORRUPTION\nWe lost a week of Omega tracking data.", "choices": [{"text": "Guess.", "mods": {"inf": 5}}, {"text": "Reboot grid.", "mods": {"eco": -5}}] },

    # --- FINALE ---
    "mut_finale_win": { "text": "ARC END: THE TIDE TURNS\nOur gamble paid off. We have decoded the Omega strain.", "choices": [{"text": "Excellent.", "mods": {"cure": 25, "inf": -20, "trust": 10}}] },
    "mut_finale_fail": { "text": "ARC END: TOTAL COLLAPSE\nOmega has overwhelmed us. We have lost control.", "choices": [{"text": "It's over.", "mods": {"pop": -10, "trust": -20}}] }
}

RANDOM_POOL = {
    "e1": { "text": "SITUATION: OXYGEN LEAK\nMain tank ruptured.", "choices": [{"text": "Divert industrial oxygen.", "mods": {"eco": -5}}, {"text": "Ration oxygen.", "mods": {"pop": -2, "trust": -10}}, {"text": "Import at 300% cost.", "mods": {"eco": -15, "trust": 5}}] },
    "e2": { "text": "SITUATION: PRISON OUTBREAK", "choices": [{"text": "Release non-violent.", "mods": {"trust": -5}}, {"text": "Lockdown.", "mods": {"trust": -5}}, {"text": "Ignore.", "mods": {"inf": 5}}] },
    "e3": { "text": "SITUATION: TRANSPORT STRIKE", "choices": [{"text": "Pay them.", "mods": {"eco": -5}}, {"text": "Military drivers.", "mods": {"trust": -5}}, {"text": "Arrest leaders.", "mods": {"trust": -15}}] },
    "e4": { "text": "SITUATION: CELEBRITY HOAX", "choices": [{"text": "Arrest pop star.", "mods": {"trust": -5}}, {"text": "Ignore.", "mods": {"inf": 5}}, {"text": "Counter-campaign.", "mods": {"eco": -2}}] },
    "e5": { "text": "SITUATION: BLACK MARKET MEDICINE", "choices": [{"text": "Raids.", "mods": {"trust": -5}}, {"text": "Buy back.", "mods": {"eco": -10}}, {"text": "Legalize.", "mods": {"eco": 5}}] },
    "e6": { "text": "SITUATION: FOREIGN SPIES", "choices": [{"text": "Execute.", "mods": {"trust": 5}}, {"text": "Trade.", "mods": {"trust": -10}}, {"text": "Double agent.", "mods": {"inf": 2}}] },
    "e7": { "text": "SITUATION: BANK RUN", "choices": [{"text": "Freeze banks.", "mods": {"trust": -15}}, {"text": "Print money.", "mods": {"eco": -15}}, {"text": "Bailout.", "mods": {"eco": -10}}] },
    "e8": { "text": "SITUATION: TEACHERS STRIKE", "choices": [{"text": "Close schools.", "mods": {"eco": -5}}, {"text": "Fire them.", "mods": {"trust": -10}}, {"text": "Hybrid classes.", "mods": {"eco": -2}}] },
    "e9": { "text": "SITUATION: REFUGEES", "choices": [{"text": "Let them in.", "mods": {"inf": 8}}, {"text": "Turn back.", "mods": {"trust": -5}}, {"text": "Camps.", "mods": {"eco": -5}}] },
    "e10": { "text": "SITUATION: PRICE GOUGING", "choices": [{"text": "Seize stock.", "mods": {"trust": 5}}, {"text": "Free market.", "mods": {"trust": -10}}, {"text": "Subsidize.", "mods": {"eco": -5}}] },
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

    # 1. Apply choice mods
    for k, v in choice_mods.items():
        if k in stats:
            stats[k] = max(0, min(100, stats[k] + v))

    stats['day'] = stats.get('day', 1) + 1

    # --- 2. AI VIRUS LOGIC (EVERY 5 DAYS ONLY) ---
    narrative_flavor = ""
    r0 = 1.5
    
    # Only run AI on Day 5, 10, 15, 20...
    if stats['day'] % 5 == 0:
        ai_action = get_virus_action(stats['inf'], stats['trust'], stats.get('cure', 0))

        if ai_action == 0:
            narrative_flavor = "Virus spreading steadily."
        elif ai_action == 1:
            # Aggressive Mutation (Bad for User)
            r0 = 2.8 
            stats['inf'] += 5
            narrative_flavor = "CRITICAL: Virus has mutated for aggressive spread."
        elif ai_action == 2:
            # Viral Weakness / Dormant (Good for User)
            r0 = 0.5
            stats['cure'] = min(100, stats.get('cure', 0) + 5)
            narrative_flavor = "OPPORTUNITY: Viral genetic structure destabilized. Cure research accelerated."
    else:
        # Normal days
        narrative_flavor = "" 

    # --- 3. MATH & POPULATION FIX ---
    compliance = stats['trust'] / 100.0
    activity = stats['eco'] / 100.0

    if stats.get('mutated_strain_active'):
        r0 += 1.0

    # Infection Growth
    r_eff = (r0 * (0.5 + 0.5 * activity)) * (1 - 0.4 * compliance)
    inf = stats['inf']
    growth = (r_eff * inf) - inf

    if stats.get('cure', 0) > 50:
        growth -= (stats['cure'] - 50) * 0.1

    growth += np.random.normal(0, 1.5)
    stats['inf'] = round(max(0, min(100, inf + growth)), 1)

    # POPULATION MORTALITY FIX
    # Base death rate (0.1%) + High Infection penalty
    mortality = 0.1
    if stats['inf'] > 50: mortality += 0.5
    if stats['inf'] > 80: mortality += 1.5 # Massive die-off at high infection
    
    # Healthcare collapse penalty
    capacity = 40 + (stats['eco'] * 0.2)
    load = stats['inf'] * 1.2
    if load > capacity: 
        mortality += 2.0 # Hospitals full = people die
        
    stats['pop'] = round(max(0, stats['pop'] - mortality), 1)

    # Eco Decay
    decay = 0.2 + (0.5 if stats['inf'] > 30 else 0)
    stats['eco'] = round(max(0, stats['eco'] - decay), 1)

    return stats, narrative_flavor

# ==========================================
# 3. GAME MANAGER (FIXED LOGIC)
# ==========================================

def get_next_event(stats, used_events, forced_next):
    # 1. Forced Next (Sub-plots)
    if forced_next and forced_next in MUTATION_ARC:
        if forced_next == "mut_treat_1":
            stats['mutated_strain_active'] = True
            stats['mutated_strain_curing'] = True
        elif forced_next == "mut_ignore":
            stats['mutated_strain_active'] = True
            stats['mutated_strain_curing'] = False
        return forced_next, MUTATION_ARC[forced_next]

    # 2. ENDING TRIGGERS (PRIORITY)
    if stats['inf'] >= 99: return "ending_extinction", {"text": "ENDING: TOTAL INFECTION\nThe virus has consumed the population. Society has collapsed.", "choices": []}
    if stats['pop'] < 10: return "ending_extinction", {"text": "ENDING: SILENT EARTH\nPopulation collapsed below critical levels.", "choices": []}
    if stats['trust'] <= 10: return "ending_revolution", {"text": "ENDING: THE GUILLOTINE\nThe military has seized control. You are under arrest.", "choices": []}
    if stats['eco'] <= 5: return "ending_collapse", {"text": "ENDING: DARK AGES\nEconomy destroyed. Electricity and food distribution failed.", "choices": []}
    
    # Victory Trigger
    if stats.get('cure', 0) >= 95 or (stats['inf'] <= 0 and stats['day'] > 10):
        return "ending_victory", {"text": "ENDING: VICTORY\nThe virus has been eradicated. Humanity survives.", "choices": []}

    # 3. Mutation Arc Trigger
    if stats['day'] > 15 and "mut_start" not in used_events and random.random() < 0.3:
        return "mut_start", MUTATION_ARC["mut_start"]

    # 4. Main Story Arcs
    day = stats.get('day', 1)
    if day in STORY_ARCS:
        return f"day_{day}", STORY_ARCS[day]

    # 5. Random Pool
    available = [k for k in RANDOM_POOL.keys() if used_events.count(k) < 2]
    if available:
        eid = random.choice(available)
        return eid, RANDOM_POOL[eid]

    # Fallback
    return "quiet_day", {
        "text": "STATUS: QUIET DAY\nNo major incidents reported.",
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
                new_stats = {"day": 1, "pop": 100, "trust": 70, "eco": 80, "inf": 5, "cure": 0}
                next_id = "day_1"
                next_event = STORY_ARCS[1]
                used_events = ["day_1"]
                flavor = ""
            else:
                # Resolve Previous Event
                prev = None
                if last_event_id:
                    if last_event_id.startswith("day_"):
                        # Safe integer conversion
                        try:
                            day_num = int(last_event_id.split("_")[1])
                            prev = STORY_ARCS.get(day_num)
                        except:
                            prev = None
                    elif last_event_id in MUTATION_ARC:
                        prev = MUTATION_ARC[last_event_id]
                    elif last_event_id in RANDOM_POOL:
                        prev = RANDOM_POOL[last_event_id]

                choice_mods = {}
                next_fixed = None
                if prev and choice_idx is not None and 0 <= choice_idx < len(prev["choices"]):
                    sel = prev["choices"][choice_idx]
                    choice_mods = sel.get("mods", {})
                    next_fixed = sel.get("next_fixed")

                new_stats, flavor = run_simulation(stats, choice_mods)
                next_id, next_event = get_next_event(new_stats, used_events, next_fixed)
                
                # Only add if not quiet day to avoid bloating list
                if next_id != "quiet_day":
                    used_events.append(next_id)

            text = next_event["text"]
            # FIX: Only append AI analysis if it's NOT a Quiet Day AND flavor exists
            if flavor and next_id != "quiet_day":
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
