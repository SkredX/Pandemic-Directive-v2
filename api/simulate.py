from http.server import BaseHTTPRequestHandler
import json
import random
import numpy as np
import os
from pymongo import MongoClient

# ==========================================
# 0. SETUP DATABASE & AI
# ==========================================
VIRUS_BRAIN = {}
try:
    with open('virus_brain.json', 'r') as f:
        VIRUS_BRAIN = json.load(f)
except:
    pass

# CONNECT TO MONGODB
try:
    # This reads the key you just added to Vercel
    client = MongoClient(os.environ['MONGODB_URI'])
    db = client['zero_hour_game']
    global_choices = db['player_choices']
    print("DB Connected")
except:
    global_choices = None
    print("DB Connection Failed (Running Offline Mode)")

def get_virus_action(inf, trust, cure):
    inf_lvl = 0 if inf < 30 else (1 if inf < 70 else 2)
    trust_lvl = 0 if trust < 30 else (1 if trust < 70 else 2)
    cure_lvl = 0 if cure < 30 else (1 if cure < 70 else 2)
    key = f"{inf_lvl}{trust_lvl}{cure_lvl}"
    if key in VIRUS_BRAIN:
        return int(np.argmax(VIRUS_BRAIN[key]))
    return 0 

# ==========================================
# 1. EVENT LIBRARY
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
    "mut_start": {
        "text": "CRISIS: MUTATED STRAIN DETECTED\nLaboratories report a new, aggressive variant 'Omega' appearing in clusters.",
        "choices": [
            {"text": "Prioritize Omega Strain. (High Risk, High Reward)", "mods": {"inf": 10, "cure": 5}, "next_fixed": "mut_strategy_focus"},
            {"text": "Ignore. Focus on Delta. (Safer now, worse later)", "mods": {"inf": 5}, "next_fixed": "mut_strategy_ignore"}
        ]
    },
    "mut_strategy_focus": { "text": "STRATEGY: OMEGA PROTOCOL\nWe are shifting all resources to the new strain.", "choices": [{"text": "Understood.", "mods": {"inf": 15, "cure": 10}}] },
    "mut_strategy_ignore": { "text": "STRATEGY: STAY THE COURSE\nWe can't afford to pivot now.", "choices": [{"text": "God help us.", "mods": {"trust": -10, "pop": -2}}] },
    "mut_finale_win": { "text": "ARC END: THE TIDE TURNS\nOur gamble paid off. We have decoded the Omega strain.", "choices": [{"text": "Excellent.", "mods": {"cure": 25, "inf": -20, "trust": 10}}] },
    "mut_finale_fail": { "text": "ARC END: TOTAL COLLAPSE\nOmega has overwhelmed us.", "choices": [{"text": "It's over.", "mods": {"pop": -10, "trust": -20}}] }
}

# The expanded Mutation Pool you requested
for i in range(1, 11):
    MUTATION_ARC[f"mut_p{i}"] = { "text": f"MUTATION EVENT {i}\nStandard protocols failing.", "choices": [{"text": "Option A", "mods": {"trust": -5}}, {"text": "Option B", "mods": {"eco": -5}}] }

RANDOM_POOL = {
    "e1": { "text": "SITUATION: OXYGEN LEAK\nA critical supply tank at Central Hospital has ruptured.", "choices": [{"text": "Divert industrial oxygen.", "mods": {"eco": -5}}, {"text": "Ration oxygen.", "mods": {"pop": -2, "trust": -10}}, {"text": "Import at 300% cost.", "mods": {"eco": -15, "trust": 5}}] },
    "e2": { "text": "SITUATION: PRISON OUTBREAK\nThe virus has breached the Maximum Security Wing.", "choices": [{"text": "Release non-violent offenders.", "mods": {"trust": -5, "inf": 2}}, {"text": "Total Lockdown.", "mods": {"trust": -5}}, {"text": "Ignore the situation.", "mods": {"inf": 5, "trust": -10}}] },
    "e3": { "text": "SITUATION: TRANSPORT STRIKE\nThe National Truckers Union is refusing to enter infected zones.", "choices": [{"text": "Pay double wages.", "mods": {"eco": -5}}, {"text": "Deploy Military drivers.", "mods": {"trust": -5}}, {"text": "Arrest strike leaders.", "mods": {"trust": -15}}] },
    "e4": { "text": "SITUATION: CELEBRITY HOAX\nA pop star is claiming the virus is fake.", "choices": [{"text": "Arrest the star.", "mods": {"trust": -5}}, {"text": "Ignore it.", "mods": {"inf": 5}}, {"text": "Launch counter-campaign.", "mods": {"eco": -2}}] },
    "e5": { "text": "SITUATION: BLACK MARKET MEDICINE\nGangs are selling stolen ventilators.", "choices": [{"text": "Authorized Raids.", "mods": {"trust": -5}}, {"text": "Buy back stock.", "mods": {"eco": -10}}, {"text": "Legalize & Tax.", "mods": {"eco": 5}}] },
    "e6": { "text": "SITUATION: FOREIGN SPIES\nAgents caught stealing vaccine data.", "choices": [{"text": "Execute publicly.", "mods": {"trust": 5}}, {"text": "Trade for supplies.", "mods": {"trust": -10}}, {"text": "Turn them.", "mods": {"inf": 2}}] },
    "e7": { "text": "SITUATION: BANK RUN\nThousands are lining up at ATMs.", "choices": [{"text": "Freeze withdrawals.", "mods": {"trust": -15}}, {"text": "Print money.", "mods": {"eco": -15}}, {"text": "Bailout.", "mods": {"eco": -10}}] },
    "e8": { "text": "SITUATION: TEACHERS STRIKE\nUnion refuses to return to class.", "choices": [{"text": "Close schools.", "mods": {"eco": -5}}, {"text": "Fire teachers.", "mods": {"trust": -10}}, {"text": "Hybrid classes.", "mods": {"eco": -2}}] },
    "e9": { "text": "SITUATION: REFUGEES\n5,000 refugees at the border.", "choices": [{"text": "Let them in.", "mods": {"inf": 8}}, {"text": "Turn them back.", "mods": {"trust": -5}}, {"text": "Camps.", "mods": {"eco": -5}}] },
    "e10": { "text": "SITUATION: PRICE GOUGING\nMedicine prices up 500%.", "choices": [{"text": "Seize stock.", "mods": {"trust": 5}}, {"text": "Free market.", "mods": {"trust": -10}}, {"text": "Subsidize.", "mods": {"eco": -5}}] },
    "e11": { "text": "SITUATION: RELIGIOUS CULT\nMass prayer gatherings ignoring lockdown.", "choices": [{"text": "Raid compound.", "mods": {"trust": -10}}, {"text": "Ignore.", "mods": {"inf": 5}}, {"text": "Negotiate.", "mods": {"trust": 2}}] },
    "e12": { "text": "SITUATION: ZOO ANIMALS STARVING\nSupply lines failed.", "choices": [{"text": "Divert food.", "mods": {"eco": -2}}, {"text": "Euthanize.", "mods": {"trust": -5}}, {"text": "Release herbivores.", "mods": {"trust": -2}}] },
    "e13": { "text": "SITUATION: WATER CONTAMINATION\nFiltration cycle missed.", "choices": [{"text": "Fix immediately.", "mods": {"eco": -8}}, {"text": "Ration water.", "mods": {"trust": -10}}, {"text": "Cover up.", "mods": {"pop": -5, "trust": -20}}] },
    "e14": { "text": "SITUATION: INTERNET BLACKOUT\nCyber-attack on the capital.", "choices": [{"text": "Restore civilian grid.", "mods": {"eco": -5}}, {"text": "Prioritize military.", "mods": {"trust": -10}}, {"text": "Blame enemies.", "mods": {"trust": 5}}] },
    "e15": { "text": "SITUATION: LOOTING WAVE\nRiots in downtown.", "choices": [{"text": "Shoot on sight.", "mods": {"pop": -2, "trust": -20}}, {"text": "Curfew.", "mods": {"eco": -5}}, {"text": "Let it burn.", "mods": {"eco": -10}}] },
    "e16": { "text": "SITUATION: FARMER PROTEST\nBurning crops.", "choices": [{"text": "Subsidies.", "mods": {"eco": -5}}, {"text": "Import food.", "mods": {"eco": -10}}, {"text": "Force harvest.", "mods": {"trust": -15}}] },
    "e17": { "text": "SITUATION: CRUISE SHIP DOCKING\n3,000 souls on board.", "choices": [{"text": "Allow docking.", "mods": {"inf": 5}}, {"text": "Refuse.", "mods": {"trust": -5}}, {"text": "Quarantine offshore.", "mods": {"eco": -5}}] },
    "e18": { "text": "SITUATION: TRASH PILEUP\nSanitation workers sick.", "choices": [{"text": "Burn it.", "mods": {"pop": -1}}, {"text": "Army engineers.", "mods": {"trust": 5}}, {"text": "Ignore.", "mods": {"trust": -5}}] },
    "e19": { "text": "SITUATION: SENATOR SCANDAL\nCaught partying.", "choices": [{"text": "Resign.", "mods": {"trust": 5}}, {"text": "Cover up.", "mods": {"trust": -15}}, {"text": "Blame media.", "mods": {"trust": -5}}] },
    "e20": { "text": "SITUATION: CRYPTO CRASH\nMarket collapse.", "choices": [{"text": "Bailout.", "mods": {"eco": -5}}, {"text": "Ignore.", "mods": {"trust": -5}}, {"text": "Investigate.", "mods": {"eco": -2}}] },
    "e21": { "text": "SITUATION: WILDFIRES\nBlaze near suburbs.", "choices": [{"text": "Evacuate.", "mods": {"inf": 5}}, {"text": "Stay put.", "mods": {"pop": -2}}, {"text": "Cloud seeding.", "mods": {"eco": -5}}] },
    "e22": { "text": "SITUATION: HACKER ATTACK\nDebt records encrypted.", "choices": [{"text": "Pay ransom.", "mods": {"eco": -10}}, {"text": "Rebuild.", "mods": {"eco": -5}}, {"text": "Counter-attack.", "mods": {"eco": -8}}] },
    "e23": { "text": "SITUATION: OIL SPILL\nTanker run aground.", "choices": [{"text": "Clean up.", "mods": {"eco": -5}}, {"text": "Ignore.", "mods": {"trust": -5}}, {"text": "Burn slick.", "mods": {"pop": -1}}] },
    "e24": { "text": "SITUATION: SPORTING FINALS\nChampionship game.", "choices": [{"text": "Cancel.", "mods": {"trust": -10}}, {"text": "Empty stadium.", "mods": {"eco": -2}}, {"text": "Full crowd.", "mods": {"inf": 10}}] },
    "e25": { "text": "SITUATION: ROGUE SCIENTIST\nTesting on homeless.", "choices": [{"text": "Use data.", "mods": {"cure": 10}}, {"text": "Arrest.", "mods": {"trust": 5}}, {"text": "Fund him.", "mods": {"eco": -5}}] },
    "e26": { "text": "SITUATION: BORDER WALL\nCitizens breaking out.", "choices": [{"text": "Reinforce.", "mods": {"eco": -5}}, {"text": "Open gates.", "mods": {"inf": 5}}, {"text": "Drones.", "mods": {"eco": -2}}] },
    "e27": { "text": "SITUATION: GOLD RESERVES\nCurrency devaluing.", "choices": [{"text": "Sell gold.", "mods": {"eco": 10}}, {"text": "Hold.", "mods": {"trust": 2}}, {"text": "Buy more.", "mods": {"eco": -10}}] },
    "e28": { "text": "SITUATION: SATELLITE DEBRIS\nCrashed in city.", "choices": [{"text": "Salvage.", "mods": {"eco": 5}}, {"text": "Warn public.", "mods": {"trust": 2}}, {"text": "Secret recovery.", "mods": {"trust": -2}}] },
    "e29": { "text": "SITUATION: HERBAL REMEDY FAD\nFake cure rumor.", "choices": [{"text": "Ban it.", "mods": {"trust": -5}}, {"text": "PSA.", "mods": {"eco": -1}}, {"text": "Tax it.", "mods": {"eco": 2}}] },
    "e30": { "text": "SITUATION: ARMY DESERTION\nSoldiers leaving.", "choices": [{"text": "Court martial.", "mods": {"trust": -10}}, {"text": "Pay bonus.", "mods": {"eco": -5}}, {"text": "Ignore.", "mods": {"trust": -5}}] },
    "e31": { "text": "SITUATION: GHOST TOWNS\n0% survival reported.", "choices": [{"text": "Burn bodies.", "mods": {"trust": -5}}, {"text": "Seal area.", "mods": {"trust": -2}}, {"text": "Loot supplies.", "mods": {"eco": 5}}] },
    "e32": { "text": "SITUATION: DATA LEAK\nReal numbers leaked.", "choices": [{"text": "Deny.", "mods": {"trust": -10}}, {"text": "Apologize.", "mods": {"trust": 5}}, {"text": "Distract.", "mods": {"eco": -5}}] },
    "e33": { "text": "SITUATION: MASS SUICIDE PACT\nDoomsday cult.", "choices": [{"text": "Intervene.", "mods": {"trust": 5}}, {"text": "Ignore.", "mods": {"pop": -1}}, {"text": "Censor news.", "mods": {"trust": -5}}] },
    "e34": { "text": "SITUATION: CLIMATE PROTEST\nBlocking highway.", "choices": [{"text": "Arrest.", "mods": {"trust": -5}}, {"text": "Listen.", "mods": {"eco": -2}}, {"text": "Ignore.", "mods": {"trust": -2}}] },
    "e35": { "text": "SITUATION: AI PREDICTION\nPredicts collapse.", "choices": [{"text": "Trust AI (Cull).", "mods": {"trust": -25}}, {"text": "Trust Humans.", "mods": {"trust": 5}}, {"text": "Shut down AI.", "mods": {"eco": -5}}] }
}

# ==========================================
# 2. ENGINE
# ==========================================
def run_simulation(current_stats, choice_mods):
    stats = current_stats.copy()

    for k, v in choice_mods.items():
        if k in stats: stats[k] = max(0, min(100, stats[k] + v))

    stats['day'] = stats.get('day', 1) + 1

    # AI LOGIC (Day 5, 10, 15...)
    narrative_flavor = ""
    r0 = 1.5
    
    if stats['day'] % 5 == 0:
        ai_action = get_virus_action(stats['inf'], stats['trust'], stats.get('cure', 0))
        if ai_action == 1:
            r0 = 2.8; stats['inf'] += 5
            narrative_flavor = "CRITICAL: Virus has mutated for aggressive spread."
        elif ai_action == 2:
            r0 = 0.5; stats['cure'] = min(100, stats.get('cure', 0) + 5)
            narrative_flavor = "OPPORTUNITY: Viral genetic structure destabilized."

    # MATH
    compliance = stats['trust'] / 100.0
    activity = stats['eco'] / 100.0
    if stats.get('mutated_strain_active'): r0 += 1.0

    r_eff = (r0 * (0.5 + 0.5 * activity)) * (1 - 0.4 * compliance)
    inf = stats['inf']
    growth = (r_eff * inf) - inf
    if stats.get('cure', 0) > 50: growth -= (stats['cure'] - 50) * 0.1
    growth += np.random.normal(0, 1.5)
    stats['inf'] = round(max(0, min(100, inf + growth)), 1)

    # MORTALITY
    mortality = 0.1
    if stats['inf'] > 50: mortality += 0.5
    if stats['inf'] > 80: mortality += 1.5
    load = stats['inf'] * 1.2
    capacity = 40 + (stats['eco'] * 0.2)
    if load > capacity: mortality += 2.0
    stats['pop'] = round(max(0, stats['pop'] - mortality), 1)

    decay = 0.2 + (0.5 if stats['inf'] > 30 else 0)
    stats['eco'] = round(max(0, stats['eco'] - decay), 1)

    return stats, narrative_flavor

# ==========================================
# 3. MANAGER
# ==========================================
def get_next_event(stats, used_events, forced_next):
    # ENDINGS
    if stats['inf'] >= 99: return "ending_extinction", {"text": "ENDING: TOTAL INFECTION\nThe virus has consumed the population.", "choices": []}
    if stats['pop'] < 10: return "ending_extinction", {"text": "ENDING: SILENT EARTH\nPopulation collapsed.", "choices": []}
    if stats['trust'] <= 10: return "ending_revolution", {"text": "ENDING: THE GUILLOTINE\nMilitary coup successful.", "choices": []}
    if stats['eco'] <= 5: return "ending_collapse", {"text": "ENDING: DARK AGES\nEconomy destroyed.", "choices": []}
    if stats.get('cure', 0) >= 95: return "ending_victory", {"text": "ENDING: VICTORY\nVirus eradicated.", "choices": []}

    # FORCED / ARC
    if forced_next and forced_next in MUTATION_ARC:
        if "strategy" in forced_next:
            stats['mutated_strain_active'] = True
        return forced_next, MUTATION_ARC[forced_next]

    # MUTATION LOGIC
    if stats.get('mutated_strain_active'):
        mut_keys = [k for k in MUTATION_ARC.keys() if k.startswith("mut_p")]
        played = [k for k in used_events if k in mut_keys]
        if len(played) >= 5:
            stats['mutated_strain_active'] = False
            return "mut_finale_win", MUTATION_ARC["mut_finale_win"] # Simple win for now
        avail = [k for k in mut_keys if k not in used_events]
        if avail: return random.choice(avail), MUTATION_ARC[random.choice(avail)]

    if stats['day'] > 15 and "mut_start" not in used_events and random.random() < 0.3:
        return "mut_start", MUTATION_ARC["mut_start"]

    # MAIN / RANDOM
    day = stats.get('day', 1)
    if day in STORY_ARCS: return f"day_{day}", STORY_ARCS[day]

    available = [k for k in RANDOM_POOL.keys() if used_events.count(k) < 2]
    if available:
        eid = random.choice(available)
        return eid, RANDOM_POOL[eid]

    return "quiet_day", {"text": "STATUS: QUIET DAY", "choices": [{"text": "Rest.", "mods": {"trust": 1}}]}

# ==========================================
# 4. HANDLER (WITH MONGO STATS)
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

            global_msg = ""

            # --- MONGODB TRACKING ---
            if not is_init and global_choices and last_event_id and choice_idx is not None:
                try:
                    # 1. Increment Count
                    key = f"{last_event_id}_{choice_idx}"
                    global_choices.update_one({"_id": key}, {"$inc": {"count": 1}}, upsert=True)
                    
                    # 2. Update Total
                    total_key = f"{last_event_id}_total"
                    global_choices.update_one({"_id": total_key}, {"$inc": {"count": 1}}, upsert=True)
                    
                    # 3. Get Stats
                    choice_doc = global_choices.find_one({"_id": key})
                    total_doc = global_choices.find_one({"_id": total_key})
                    
                    if choice_doc and total_doc and total_doc['count'] > 0:
                        pct = int((choice_doc['count'] / total_doc['count']) * 100)
                        global_msg = f"\n[GLOBAL INTEL]: {pct}% of commanders chose this."
                except:
                    pass # Don't crash game if DB lags

            if is_init:
                new_stats = {"day": 1, "pop": 100, "trust": 70, "eco": 80, "inf": 5, "cure": 0}
                next_id = "day_1"; next_event = STORY_ARCS[1]; used_events = ["day_1"]; flavor = ""
            else:
                prev = None
                if last_event_id:
                    if last_event_id.startswith("day_"): prev = STORY_ARCS.get(int(last_event_id.split("_")[1]))
                    elif last_event_id in MUTATION_ARC: prev = MUTATION_ARC[last_event_id]
                    elif last_event_id in RANDOM_POOL: prev = RANDOM_POOL[last_event_id]

                choice_mods = {}; next_fixed = None
                if prev and choice_idx is not None:
                    sel = prev["choices"][choice_idx]
                    choice_mods = sel.get("mods", {}); next_fixed = sel.get("next_fixed")

                new_stats, flavor = run_simulation(stats, choice_mods)
                next_id, next_event = get_next_event(new_stats, used_events, next_fixed)
                if next_id != "quiet_day": used_events.append(next_id)

            text = next_event["text"]
            # Append Global Stats FIRST, then AI
            if global_msg: text += global_msg
            if flavor: text += f"\n\n[AI ANALYSIS]: {flavor}"

            self.send_json({
                "stats": new_stats, "narrative": text, 
                "choices": next_event["choices"], 
                "event_id": next_id, "used_events": used_events
            })
        except Exception as e:
            self.send_response(500); self.wfile.write(str(e).encode())

    def send_json(self, d):
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(json.dumps(d).encode())
