from http.server import BaseHTTPRequestHandler
import json
import random
import numpy as np

# ==========================================
# 1. THE MASTER EVENT DATABASE
# ==========================================
# Structure: ID -> { Text, Choices [ {Text, Mods, TriggerSubPlot?} ] }

EVENTS = {
    # --- STARTING DAYS ---
    "start_1": {
        "text": "DAY 1: PATIENT ZERO\nSurveillance satellites detected a bio-anomaly in Sector 4. General Kael urges a total blockade. Dr. Aris suggests contact tracing.",
        "choices": [
            {"text": "[KAEL] Total Blockade (High Eco Dmg)", "mods": {"eco": -10, "inf": -5, "trust": -5, "kael_loyalty": 10}},
            {"text": "[ARIS] Contact Tracing (Slow)", "mods": {"eco": -2, "inf": 5, "trust": 5, "aris_loyalty": 10}},
            {"text": "Ignore it. It's just the flu.", "mods": {"eco": 5, "inf": 15, "trust": 0}}
        ]
    },
    
    # --- SUB-PLOT: THE GENERAL'S COUP (Triggered if Trust < 30) ---
    "coup_1": {
        "text": "SUB-PLOT: RED FLAG\nGeneral Kael has deployed tanks around the capitol without your order. He claims it's for 'Protection'.",
        "choices": [
            {"text": "Order him to stand down.", "mods": {"trust": 5, "kael_loyalty": -20}, "next_fixed": "coup_2a"},
            {"text": "Authorize the deployment.", "mods": {"trust": -10, "inf": -5, "kael_loyalty": 10}, "next_fixed": "coup_2b"},
            {"text": "Flee the capital.", "mods": {"trust": -50}, "next_fixed": "ending_coward"}
        ]
    },
    "coup_2a": { # Stand Down Path
        "text": "SUB-PLOT: THE STANDOFF\nKael refuses. His troops are aiming at the palace. He demands you hand over full control.",
        "choices": [
            {"text": "Resign (Game Over).", "mods": {}, "next_fixed": "ending_coup_loss"},
            {"text": "Call the Air Force (Civil War).", "mods": {"pop": -20, "eco": -50}, "next_fixed": "coup_3_war"}
        ]
    },

    # --- SUB-PLOT: OPERATION PHOENIX (Trust Recovery) ---
    "trust_op_1": {
        "text": "SUB-PLOT: OPERATION PHOENIX\nAdvisors suggest a risky transparency campaign to regain public trust. We would declassify all virus data.",
        "choices": [
            {"text": "Declassify everything (High Risk).", "mods": {"trust": 20, "eco": -5}, "next_fixed": "trust_op_success"},
            {"text": "Edit the data first (Safe).", "mods": {"trust": 5, "eco": 0}, "next_fixed": "random"}
        ]
    },
    "trust_op_success": {
        "text": "RESULT: OPERATION PHOENIX\nThe public appreciates the honesty. Approval ratings are soaring, but panic has slightly increased.",
        "choices": [{"text": "Excellent.", "mods": {"trust": 15, "inf": 2}}]
    },

    # --- RANDOM POOL EVENTS ---
    "e_mask_riot": {
        "text": "CRISIS: ANTI-MASK RIOTS\nA large group is burning masks in the city square.",
        "choices": [
            {"text": "Arrest them (Force).", "mods": {"trust": -10, "inf": -2}},
            {"text": "Let them protest (Freedom).", "mods": {"trust": 5, "inf": 8}},
            {"text": "Distribute free N95s instead.", "mods": {"eco": -5, "trust": 5, "inf": -5}}
        ]
    },
    "e_vaccine_rush": {
        "text": "SCIENCE: VACCINE BREAKTHROUGH\nDr. Aris has a prototype. It's untested.",
        "choices": [
            {"text": "Human Trials (Dangerous).", "mods": {"cure": 25, "pop": -2, "trust": -5}},
            {"text": "Animal Trials (Safe but Slow).", "mods": {"cure": 5}},
            {"text": "Sell the patent to Pharma.", "mods": {"eco": 20, "cure": -10, "trust": -20}}
        ]
    },
    "e_market_crash": {
        "text": "ECONOMY: BLACK MONDAY\nThe stock market is in freefall.",
        "choices": [
            {"text": "Bailout Banks (Costly).", "mods": {"eco": 10, "trust": -10}},
            {"text": "Let it crash.", "mods": {"eco": -20, "trust": -5}},
            {"text": "Seize private assets.", "mods": {"eco": 15, "trust": -30}}
        ]
    },
    "e_super_spreader": {
        "text": "CRISIS: RELIGIOUS FESTIVAL\nA mega-church plans a 50,000 person gathering.",
        "choices": [
            {"text": "Ban it.", "mods": {"trust": -15, "inf": -5}},
            {"text": "Allow it.", "mods": {"inf": 20, "trust": 5}},
            {"text": "Compromise: Outdoor only.", "mods": {"inf": 5, "trust": 0}}
        ]
    },
    "e_oxygen": {
        "text": "LOGISTICS: OXYGEN SHORTAGE\nHospitals are running dry.",
        "choices": [
            {"text": "Divert industrial oxygen (Hurt Industry).", "mods": {"eco": -8, "load": -10}},
            {"text": "Triage (Let weak die).", "mods": {"pop": -5, "load": -5}},
            {"text": "Buy from rivals (Diplomatic Cost).", "mods": {"eco": -15, "load": -15}}
        ]
    }
}

# ==========================================
# 2. SIMULATION ENGINE (MATH)
# ==========================================
def run_simulation(current_stats, choice_mods):
    stats = current_stats.copy()
    
    # 1. Apply Choice Immediate Effects
    for key, val in choice_mods.items():
        if key in stats:
            stats[key] = max(0, min(100, stats[key] + val))
    
    # 2. Complex Biological Simulation
    # Infection Rate isn't static. It depends on Trust (Compliance) and Eco (Activity)
    # High Eco = High Contact Rate. High Trust = High Mask Compliance.
    
    # Base Transmission Rate
    r0 = 1.5 
    
    # Modifiers
    compliance = stats['trust'] / 100.0
    activity = stats['eco'] / 100.0
    
    # Effective R: (Base * Activity) reduced by Compliance
    r_effective = (r0 * (0.5 + 0.5 * activity)) * (1.0 - (0.4 * compliance))
    
    # Growth Calculation (Logistic-ish)
    inf = stats['inf']
    growth = (r_effective * inf) - inf
    
    # Cure Progress reduces infection capability
    if stats.get('cure', 0) > 50:
        growth -= (stats['cure'] - 50) * 0.1
        
    # Apply Noise (Random fluctuation)
    growth += np.random.normal(0, 1.5)
    
    new_inf = max(0, min(100, inf + growth))
    stats['inf'] = round(new_inf, 1)

    # 3. Healthcare & Mortality
    # If Inf > Load Capacity (fixed at 40 initially), deaths skyrocket
    capacity = 40 + (stats['eco'] * 0.2) # Richer countries have better hospitals
    load = stats['inf'] * 1.2
    
    overload = max(0, load - capacity)
    mortality_rate = 0.05 + (overload * 0.05) # 0.05% base, plus massive penalty for overload
    
    stats['pop'] = round(max(0, stats['pop'] - mortality_rate), 1)
    stats['load'] = round(min(100, load), 1)

    # 4. Economy Decay
    # Eco decays naturally, but decays faster if Infection is high (Fear)
    decay = 0.2
    if stats['inf'] > 30: decay += 0.5
    stats['eco'] = round(max(0, stats['eco'] - decay), 1)

    return stats

# ==========================================
# 3. GAME MANAGER (DECISION LOGIC)
# ==========================================
def get_next_event_id(stats, last_event):
    # A. Check for Forced Paths (Sub-plot chains)
    if "next_fixed" in last_event:
        return last_event["next_fixed"]

    # B. Check for Game Over Conditions
    if stats['pop'] < 10: return "ending_extinction"
    if stats['trust'] < 5: return "ending_revolution"
    if stats['eco'] < 5: return "ending_collapse"
    
    # C. Check for Victory
    # Hard Victory: Cure > 95 AND Inf < 1
    if stats.get('cure', 0) > 95 and stats['inf'] < 1:
        return "ending_victory_science"
    
    # D. Trigger Sub-Plots dynamically
    if stats['trust'] < 30 and random.random() < 0.4:
        return "coup_1" # Trigger Coup
    
    if stats['trust'] < 40 and stats['eco'] > 60 and random.random() < 0.3:
        return "trust_op_1" # Trigger Recovery Op

    # E. Default: Pick Random Event
    pool = ["e_mask_riot", "e_vaccine_rush", "e_market_crash", "e_super_spreader", "e_oxygen"]
    return random.choice(pool)

def get_ending_text(ending_id):
    endings = {
        "ending_extinction": "ENDING: SILENT EARTH\nThe population has collapsed. There is no one left to govern.",
        "ending_revolution": "ENDING: THE GUILLOTINE\nThe people stormed the palace. You did not survive the night.",
        "ending_collapse": "ENDING: DARK AGES\nThe economy has vaporized. Electricity is gone. Survival is the only currency.",
        "ending_victory_science": "ENDING: A NEW DAWN\nThe virus has been eradicated via scientific breakthrough. You are hailed as the Savior of Humanity.",
        "ending_coup_loss": "ENDING: MILITARY STATE\nGeneral Kael rules now. You are rotting in a cell."
    }
    return endings.get(ending_id, "GAME OVER")

# ==========================================
# 4. VERCEL HANDLER
# ==========================================
class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_len = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_len)
            data = json.loads(body)
            
            # Extract Data
            stats = data.get('stats', {})
            choice_idx = data.get('choice_index')
            last_event_id = data.get('last_event_id')
            is_init = data.get('is_init', False)

            # --- INIT GAME ---
            if is_init:
                # Start fresh
                next_event_id = "start_1"
                next_event = EVENTS[next_event_id]
                new_stats = {"pop": 100, "trust": 70, "eco": 80, "inf": 5, "cure": 0, "load": 10}
            
            # --- PROCESS TURN ---
            else:
                # 1. Look up the event the user just played
                prev_event = EVENTS.get(last_event_id, {})
                
                # 2. Get the specific mods for the choice they made
                choice_mods = {}
                next_fixed = None
                
                if prev_event and "choices" in prev_event and choice_idx is not None:
                    if choice_idx < len(prev_event["choices"]):
                        selected_choice = prev_event["choices"][choice_idx]
                        choice_mods = selected_choice.get("mods", {})
                        next_fixed = selected_choice.get("next_fixed", None)
                
                # 3. Run Math Simulation
                new_stats = run_simulation(stats, choice_mods)
                
                # 4. Decide Next Event
                if next_fixed:
                    next_event_id = next_fixed
                else:
                    next_event_id = get_next_event_id(new_stats, {"next_fixed": next_fixed})
                
                # 5. Handle Endings
                if "ending_" in next_event_id:
                    narrative = get_ending_text(next_event_id)
                    response = {
                        "stats": new_stats,
                        "narrative": narrative,
                        "choices": [], # No choices = Game Over
                        "event_id": next_event_id
                    }
                    self.send_json(response)
                    return

                next_event = EVENTS[next_event_id]

            # --- BUILD RESPONSE ---
            response = {
                "stats": new_stats,
                "narrative": next_event["text"],
                "choices": next_event["choices"],
                "event_id": next_event_id
            }
            self.send_json(response)

        except Exception as e:
            self.send_response(500)
            self.wfile.write(str(e).encode('utf-8'))

    def send_json(self, data):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))
