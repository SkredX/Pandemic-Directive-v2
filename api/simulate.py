from http.server import BaseHTTPRequestHandler
import json
import random
import numpy as np
import os
import sys

# ==========================================
# 0. ROBUST DATABASE SETUP
# ==========================================
VIRUS_BRAIN = {}
try:
    with open('virus_brain.json', 'r') as f:
        VIRUS_BRAIN = json.load(f)
except:
    pass

# GLOBAL DB STATE
DB_STATUS = "Initializing..."
client = None
db = None
global_choices = None
leaderboard_col = None

try:
    from pymongo import MongoClient
    
    if 'MONGODB_URI' in os.environ:
        # TIMEOUT FIX: Fail fast (3s) so Vercel doesn't kill the process
        client = MongoClient(os.environ['MONGODB_URI'], serverSelectionTimeoutMS=3000)
        
        # Lazy Ping: We won't crash if this fails, just go offline
        try:
            client.admin.command('ping')
            db = client['zero_hour_game']
            global_choices = db['player_choices']
            leaderboard_col = db['leaderboard']
            DB_STATUS = "ONLINE"
        except:
            DB_STATUS = "OFFLINE_TIMEOUT"
    else:
        DB_STATUS = "MISSING_URI"
except ImportError:
    DB_STATUS = "MISSING_PACKAGES"
except Exception as e:
    DB_STATUS = f"ERROR: {str(e)}"

# ==========================================
# 1. SCORING & AI
# ==========================================
def get_virus_action(inf, trust, cure):
    inf_lvl = 0 if inf < 30 else (1 if inf < 70 else 2)
    trust_lvl = 0 if trust < 30 else (1 if trust < 70 else 2)
    cure_lvl = 0 if cure < 30 else (1 if cure < 70 else 2)
    key = f"{inf_lvl}{trust_lvl}{cure_lvl}"
    if key in VIRUS_BRAIN: return int(np.argmax(VIRUS_BRAIN[key]))
    return 0 

def calculate_score(stats, ending_type):
    score = (stats['day'] * 100) + (stats['pop'] * 50) + (stats['trust'] * 20) + (stats.get('cure',0) * 10)
    if ending_type == "ending_victory": score += 5000
    elif ending_type == "ending_extinction": score -= 2000
    elif ending_type == "ending_revolution": score -= 1000
    return int(score)

# ==========================================
# 2. EVENT LIBRARY
# ==========================================
STORY_ARCS = {
    1: { "text": "DAY 1: PATIENT ZERO\nSurveillance satellites detected a bio-anomaly in Sector 4.", "choices": [{"text": "[KAEL] Total Blockade.", "mods": {"eco": -10, "inf": -5, "trust": -10}}, {"text": "[ARIS] Contact Tracing Team.", "mods": {"eco": -2, "inf": 5, "trust": 5}}, {"text": "Cover it up to prevent panic.", "mods": {"inf": 10, "trust": -5}}, {"text": "Request WHO intervention.", "mods": {"eco": -5, "trust": 2}}] },
    5: { "text": "DAY 5: CONTAINMENT BREACH\nThe virus has crossed state lines.", "choices": [{"text": "Close domestic borders.", "mods": {"eco": -15, "trust": -5}}, {"text": "Screen travelers.", "mods": {"inf": 8, "trust": 5}}, {"text": "Do nothing.", "mods": {"inf": 15, "trust": -10}}] }
}

MUTATION_ARC = {
    "mut_start": { 
        "text": "CRISIS: MUTATED STRAIN DETECTED\nLaboratories report a new variant 'Omega'. It is highly lethal.", 
        "choices": [
            # High Cure reward, but infection spikes
            {"text": "Prioritize Omega Strain.", "mods": {"inf": 15, "cure": 15}, "next_fixed": "mut_strategy_focus"}, 
            {"text": "Ignore. Focus on Delta.", "mods": {"inf": 5}, "next_fixed": "mut_strategy_ignore"}
        ] 
    },
    "mut_strategy_focus": { 
        "text": "STRATEGY: OMEGA PROTOCOL\nWe are shifting all resources to the new strain.", 
        "choices": [{"text": "Understood.", "mods": {"inf": 15, "cure": 10}}] 
    },
    "mut_strategy_ignore": { 
        "text": "STRATEGY: STAY THE COURSE\nWe can't afford to pivot now. The Omega strain is spreading unchecked.", 
        "choices": [
            # PUNISHMENT for ignoring
            {"text": "I decide to focus on the existing strain.", "mods": {"trust": -10, "pop": -15}} 
        ] 
    },
    "mut_finale_win": { "text": "ARC END: THE TIDE TURNS\nOur gamble paid off.", "choices": [{"text": "Excellent.", "mods": {"cure": 30, "inf": -25, "trust": 15}}] },
    "mut_finale_fail": { "text": "ARC END: TOTAL COLLAPSE\nOmega has overwhelmed us.", "choices": [{"text": "It's over.", "mods": {"pop": -25, "trust": -25}}] }
}
# Add specific mutation events
for i in range(1, 11): 
    MUTATION_ARC[f"mut_p{i}"] = { 
        "text": f"MUTATION EVENT {i}\nOmega Strain is resisting standard treatment.", 
        "choices": [
            {"text": "Burn bodies to stop spread.", "mods": {"trust": -15, "pop": -2}}, 
            {"text": "Desperate experimental drug.", "mods": {"cure": 5, "pop": -5}}
        ] 
    }

RANDOM_POOL = {
    # 1. CURE & RESEARCH (10 Events)
    "cure_1": { "text": "RESEARCH: AI BREAKTHROUGH\nDeepMind has folded the virus protein structure.", "choices": [{"text": "Mass produce treatment.", "mods": {"cure": 15, "eco": -10}}, {"text": "Verify data first.", "mods": {"cure": 5, "trust": 5}}] },
    "cure_2": { "text": "RESEARCH: HUMAN TRIALS\n3,000 volunteers are ready to test a risky vaccine.", "choices": [{"text": "Authorize immediately.", "mods": {"cure": 20, "pop": -2}}, {"text": "Wait for safety checks.", "mods": {"cure": 5, "trust": 2}}] },
    "cure_3": { "text": "RESEARCH: ROGUE DATA\nHackers stole vaccine data from a rival nation.", "choices": [{"text": "Use the stolen data.", "mods": {"cure": 12, "trust": -5}}, {"text": "Delete it.", "mods": {"trust": 5}}] },
    "cure_4": { "text": "RESEARCH: GLOBAL SUMMIT\nWorld scientists want to merge databases.", "choices": [{"text": "Share all intel.", "mods": {"cure": 10, "trust": 5}}, {"text": "Keep our secrets.", "mods": {"trust": -5, "eco": 5}}] },
    "cure_5": { "text": "RESEARCH: IMMUNITY GENE\nWe found a survivor with natural immunity.", "choices": [{"text": "Aggressive extraction.", "mods": {"cure": 15, "trust": -10}}, {"text": "Pay for blood samples.", "mods": {"cure": 8, "eco": -2}}] },
    "cure_6": { "text": "RESEARCH: FUNGAL COMPOUND\nA rare fungus shows anti-viral properties.", "choices": [{"text": "Strip mine the forest.", "mods": {"cure": 10, "eco": -10}}, {"text": "Synthesize slowly.", "mods": {"cure": 4, "eco": -2}}] },
    "cure_7": { "text": "RESEARCH: ALIEN SIGNAL\n(Rare) A signal from space contains a DNA sequence.", "choices": [{"text": "Print the sequence.", "mods": {"cure": 25, "trust": -5}}, {"text": "Delete it.", "mods": {"trust": 5}}] },
    "cure_8": { "text": "RESEARCH: FAILED STATE\nA collapsed neighbor offers data for food.", "choices": [{"text": "Send food for data.", "mods": {"cure": 10, "eco": -5}}, {"text": "Just take the data.", "mods": {"cure": 10, "trust": -10}}] },
    "cure_9": { "text": "RESEARCH: CRYO-LAB\nUnfreezing old samples might help.", "choices": [{"text": "Do it.", "mods": {"cure": 5}}, {"text": "Too risky.", "mods": {"trust": 2}}] },
    "cure_10": { "text": "RESEARCH: MIRACLE CHILD\nA child healed herself overnight.", "choices": [{"text": "Study her.", "mods": {"cure": 15, "trust": -5}}, {"text": "Leave her alone.", "mods": {"trust": 10}}] },

    # 2. INFRASTRUCTURE & DISASTERS (10 Events)
    "e1": { "text": "SITUATION: OXYGEN LEAK\nICU alarms are blaring.", "choices": [{"text": "Divert industrial oxygen.", "mods": {"eco": -5}}, {"text": "Ration oxygen (Triage).", "mods": {"pop": -5, "trust": -10}}, {"text": "Import at 300% cost.", "mods": {"eco": -15, "trust": 5}}] },
    "e13": { "text": "SITUATION: WATER CONTAMINATION\nFiltration missed.", "choices": [{"text": "Fix immediately.", "mods": {"eco": -8}}, {"text": "Ration water.", "mods": {"trust": -10}}, {"text": "Cover up.", "mods": {"pop": -5, "trust": -20}}] },
    "e14": { "text": "SITUATION: INTERNET BLACKOUT\nCyber-attack.", "choices": [{"text": "Restore civilian.", "mods": {"eco": -5}}, {"text": "Prioritize military.", "mods": {"trust": -10}}, {"text": "Blame enemies.", "mods": {"trust": 5, "eco": -2}}] },
    "e21": { "text": "SITUATION: WILDFIRES\nBlaze near suburbs.", "choices": [{"text": "Evacuate.", "mods": {"inf": 5}}, {"text": "Stay put.", "mods": {"pop": -2}}, {"text": "Cloud seed.", "mods": {"eco": -5}}] },
    "e23": { "text": "SITUATION: OIL SPILL\nTanker run aground.", "choices": [{"text": "Clean up.", "mods": {"eco": -5}}, {"text": "Ignore.", "mods": {"trust": -5}}, {"text": "Burn it.", "mods": {"pop": -1}}] },
    "e28": { "text": "SITUATION: SATELLITE DEBRIS\nCrashed in city.", "choices": [{"text": "Salvage.", "mods": {"eco": 5}}, {"text": "Warn public.", "mods": {"trust": 2}}, {"text": "Secret recovery.", "mods": {"trust": -2}}] },
    "e36": { "text": "SITUATION: NUCLEAR LEAK\nPower plant coolant failure.", "choices": [{"text": "Shutdown plant.", "mods": {"eco": -15}}, {"text": "Vent radiation.", "mods": {"pop": -2, "trust": -10}}, {"text": "Cover up.", "mods": {"pop": -5, "trust": -20}}] },
    "e37": { "text": "SITUATION: DAM CRACK\nHeavy rains threaten breach.", "choices": [{"text": "Evacuate valley.", "mods": {"eco": -5, "inf": 2}}, {"text": "Emergency repairs.", "mods": {"eco": -10}}, {"text": "Pray.", "mods": {"pop": -5}}] },
    "e38": { "text": "SITUATION: BRIDGE COLLAPSE\nMain trade route severed.", "choices": [{"text": "Rebuild fast.", "mods": {"eco": -10}}, {"text": "Use ferries.", "mods": {"inf": 5}}, {"text": "Ignore.", "mods": {"eco": -5, "trust": -5}}] },
    "e39": { "text": "SITUATION: GPS FAILURE\nGlobal navigation down.", "choices": [{"text": "Ground flights.", "mods": {"eco": -5}}, {"text": "Manual navigation.", "mods": {"pop": -1}}, {"text": "Wait it out.", "mods": {"trust": -2}}] },

    # 3. SOCIAL UNREST & CRIME (10 Events)
    "e2": { "text": "SITUATION: PRISON OUTBREAK\nGuards are fleeing.", "choices": [{"text": "Release non-violent.", "mods": {"trust": -5, "inf": 2}}, {"text": "Total Lockdown.", "mods": {"trust": -5}}, {"text": "Ignore.", "mods": {"inf": 5, "trust": -10}}] },
    "e15": { "text": "SITUATION: LOOTING WAVE\nRiots downtown.", "choices": [{"text": "Shoot on sight.", "mods": {"pop": -5, "trust": -20}}, {"text": "Curfew.", "mods": {"eco": -5, "inf": -2}}, {"text": "Let it burn.", "mods": {"eco": -10}}] },
    "e5": { "text": "SITUATION: BLACK MARKET MEDICINE\nGangs selling stolen ventilators.", "choices": [{"text": "Authorized Raids.", "mods": {"trust": -5}}, {"text": "Buy back stock.", "mods": {"eco": -10}}, {"text": "Legalize & Tax.", "mods": {"eco": 5, "trust": -10}}] },
    "e11": { "text": "SITUATION: RELIGIOUS CULT\nMass gatherings.", "choices": [{"text": "Raid compound.", "mods": {"trust": -10, "pop": -1}}, {"text": "Ignore.", "mods": {"inf": 5}}, {"text": "Negotiate.", "mods": {"trust": 2, "inf": 2}}] },
    "e33": { "text": "SITUATION: MASS SUICIDE PACT\nDoomsday cult.", "choices": [{"text": "Intervene.", "mods": {"trust": 5}}, {"text": "Ignore.", "mods": {"pop": -1}}, {"text": "Censor news.", "mods": {"trust": -5}}] },
    "e40": { "text": "SITUATION: SOCIAL MEDIA CHALLENGE\nKids licking doorknobs.", "choices": [{"text": "Ban app.", "mods": {"trust": -5}}, {"text": "PSA Campaign.", "mods": {"eco": -2}}, {"text": "Arrest influencers.", "mods": {"trust": -2}}] },
    "e41": { "text": "SITUATION: DIGITAL CULT\nBelieves virus is a simulation.", "choices": [{"text": "Shut down servers.", "mods": {"trust": -5}}, {"text": "Ignore.", "mods": {"inf": 5}}, {"text": "Infiltrate.", "mods": {"trust": 2}}] },
    "e42": { "text": "SITUATION: VIGILANTE JUSTICE\nCitizens arresting 'infected'.", "choices": [{"text": "Stop them.", "mods": {"trust": -5}}, {"text": "Deputize them.", "mods": {"trust": -15, "inf": -2}}, {"text": "Ignore.", "mods": {"pop": -1}}] },
    "e43": { "text": "SITUATION: FOOD RIOTS\nSupermarkets empty.", "choices": [{"text": "Ration cards.", "mods": {"trust": -5}}, {"text": "Military distribution.", "mods": {"trust": 5, "eco": -5}}, {"text": "Free market.", "mods": {"pop": -2}}] },
    "e44": { "text": "SITUATION: SQUATTERS\nOccupying empty luxury hotels.", "choices": [{"text": "Evict force.", "mods": {"trust": -5}}, {"text": "Allow it.", "mods": {"trust": 5, "eco": -5}}, {"text": "Tax them.", "mods": {"eco": 2}}] },

    # 4. POLITICS & ECONOMY (10 Events)
    "e7": { "text": "SITUATION: BANK RUN\nThousands at ATMs.", "choices": [{"text": "Freeze withdrawals.", "mods": {"trust": -15}}, {"text": "Print money.", "mods": {"eco": -15}}, {"text": "Bailout.", "mods": {"eco": -10, "trust": -5}}] },
    "e10": { "text": "SITUATION: PRICE GOUGING\nMeds up 500%.", "choices": [{"text": "Seize stock.", "mods": {"trust": 5, "eco": -2}}, {"text": "Free market.", "mods": {"trust": -10}}, {"text": "Subsidize.", "mods": {"eco": -5}}] },
    "e19": { "text": "SITUATION: SENATOR SCANDAL\nCaught partying.", "choices": [{"text": "Force resignation.", "mods": {"trust": 5}}, {"text": "Cover up.", "mods": {"trust": -15}}, {"text": "Blame media.", "mods": {"trust": -5}}] },
    "e20": { "text": "SITUATION: CRYPTO CRASH\nEconomy hit.", "choices": [{"text": "Bailout.", "mods": {"eco": -5}}, {"text": "Ignore.", "mods": {"trust": -5}}, {"text": "Investigate.", "mods": {"eco": -2}}] },
    "e27": { "text": "SITUATION: GOLD RESERVES\nCurrency devaluing.", "choices": [{"text": "Sell gold.", "mods": {"eco": 10, "trust": -5}}, {"text": "Hold.", "mods": {"trust": 2}}, {"text": "Buy more.", "mods": {"eco": -10}}] },
    "e45": { "text": "SITUATION: ELECTION YEAR\nOpponent demands reopening.", "choices": [{"text": "Delay election.", "mods": {"trust": -20}}, {"text": "Reopen economy.", "mods": {"inf": 10, "eco": 10}}, {"text": "Smear campaign.", "mods": {"trust": -5}}] },
    "e46": { "text": "SITUATION: TRADE WAR\nAlly tariffs medical supplies.", "choices": [{"text": "Pay tariffs.", "mods": {"eco": -10}}, {"text": "Retaliate.", "mods": {"eco": -5, "trust": 5}}, {"text": "Smuggle.", "mods": {"trust": -5}}] },
    "e47": { "text": "SITUATION: PENSION FUND\nCollapsed.", "choices": [{"text": "Bailout.", "mods": {"eco": -10}}, {"text": "Cut payouts.", "mods": {"trust": -15}}, {"text": "Ignore.", "mods": {"trust": -10}}] },
    "e48": { "text": "SITUATION: UNION STRIKE\nGeneral labor stoppage.", "choices": [{"text": "Meet demands.", "mods": {"eco": -10}}, {"text": "Break strike.", "mods": {"trust": -10}}, {"text": "Negotiate.", "mods": {"eco": -2}}] },
    "e49": { "text": "SITUATION: BILLIONAIRE BUNKER\nRich fleeing tax base.", "choices": [{"text": "Exit tax.", "mods": {"eco": 10, "trust": -5}}, {"text": "Seize assets.", "mods": {"trust": 5, "eco": 5}}, {"text": "Let them go.", "mods": {"eco": -5}}] },

    # 5. MISC & WILD CARDS (10 Events)
    "e4": { "text": "SITUATION: CELEBRITY HOAX\nPop star claims virus is fake.", "choices": [{"text": "Arrest the star.", "mods": {"trust": -5}}, {"text": "Ignore it.", "mods": {"inf": 5}}, {"text": "Counter-campaign.", "mods": {"eco": -2}}] },
    "e6": { "text": "SITUATION: FOREIGN SPIES\nStealing vaccine data.", "choices": [{"text": "Execute publicly.", "mods": {"trust": 5, "eco": -5}}, {"text": "Trade for supplies.", "mods": {"trust": -10, "eco": 5}}, {"text": "Turn them.", "mods": {"inf": 2}}] },
    "e12": { "text": "SITUATION: ZOO ANIMALS\nStarving.", "choices": [{"text": "Divert food.", "mods": {"eco": -2}}, {"text": "Euthanize.", "mods": {"trust": -5}}, {"text": "Release.", "mods": {"trust": -2}}] },
    "e17": { "text": "SITUATION: CRUISE SHIP\nInfected offshore.", "choices": [{"text": "Allow docking.", "mods": {"inf": 5, "trust": 5}}, {"text": "Refuse entry.", "mods": {"trust": -5}}, {"text": "Quarantine offshore.", "mods": {"eco": -5}}] },
    "e25": { "text": "SITUATION: ROGUE SCIENTIST\nTesting on homeless.", "choices": [{"text": "Use data.", "mods": {"cure": 10, "trust": -10}}, {"text": "Arrest him.", "mods": {"trust": 5}}, {"text": "Secretly fund.", "mods": {"eco": -5, "cure": 5}}] },
    "e29": { "text": "SITUATION: HERBAL REMEDY FAD\nFake cure rumor.", "choices": [{"text": "Ban it.", "mods": {"trust": -5}}, {"text": "PSA.", "mods": {"eco": -1}}, {"text": "Tax it.", "mods": {"eco": 2, "pop": -1}}] },
    "e31": { "text": "SITUATION: GHOST TOWNS\n0% survival reported.", "choices": [{"text": "Burn bodies.", "mods": {"trust": -5}}, {"text": "Seal area.", "mods": {"trust": -2}}, {"text": "Loot supplies.", "mods": {"eco": 5, "trust": -10}}] },
    "e35": { "text": "SITUATION: AI PREDICTION\nPredicts collapse.", "choices": [{"text": "Trust AI (Cull).", "mods": {"eco": 5, "trust": -25, "pop": -5}}, {"text": "Trust Humans.", "mods": {"trust": 5}}, {"text": "Shut down AI.", "mods": {"eco": -5}}] },
    "e50": { "text": "SITUATION: ANCIENT RUINS\nArtifact found.", "choices": [{"text": "Sell it.", "mods": {"eco": 10}}, {"text": "Museum.", "mods": {"trust": 2}}, {"text": "Cursed?", "mods": {"trust": -2}}] },
    "e51": { "text": "SITUATION: METEOR SHOWER\nSpectacle distracts public.", "choices": [{"text": "Encourage viewing.", "mods": {"trust": 5, "inf": 2}}, {"text": "Stay inside.", "mods": {"trust": -2}}, {"text": "Ignore.", "mods": {}}] },
}

# PROCEDURAL GENERATION (Creates 100+ Unique Events)
sectors = ["North", "South", "East", "West", "Central", "Industrial", "Slum", "Tech", "Port", "Rural"]
issues = ["Food Riots", "Power Failure", "Medical Shortage", "Militia Uprising", "Infection Spike", "Water Crisis", "Fire Outbreak", "Supply Raid"]
flavor_text = ["Command awaits orders.", "Situation critical.", "Locals are panicking.", "Casualties rising."]

for i in range(105):
    sec = sectors[i % len(sectors)]
    iss = issues[i % len(issues)]
    flav = random.choice(flavor_text)
    
    # Procedurally generate ID and content
    eid = f"proc_{i}"
    RANDOM_POOL[eid] = {
        "text": f"REPORT: {sec} Sector\nAlert: {iss} reported.\n{flav}",
        "choices": [
            {"text": "Send Military Aid.", "mods": {"trust": 2, "eco": -3}},
            {"text": "Enforce Quarantine.", "mods": {"inf": -2, "pop": -1, "trust": -2}},
            {"text": "Do Nothing.", "mods": {"trust": -5, "pop": -2}}
        ]
    }

# ==========================================
# 3. LOGIC ENGINE
# ==========================================
def run_simulation(current_stats, choice_mods):
    stats = current_stats.copy()
    for k, v in choice_mods.items():
        if k in stats: stats[k] = max(0, min(100, stats[k] + v))
    stats['day'] = stats.get('day', 1) + 1

    # AI LOGIC
    narrative_flavor = ""; r0 = 1.5
    if stats['day'] % 5 == 0:
        ai_action = get_virus_action(stats['inf'], stats['trust'], stats.get('cure', 0))
        if ai_action == 1:
            r0 = 2.8; stats['inf'] += 5; narrative_flavor = "CRITICAL: Virus has mutated for aggressive spread."
        elif ai_action == 2:
            r0 = 0.5; stats['cure'] = min(100, stats.get('cure', 0) + 5); narrative_flavor = "OPPORTUNITY: Viral genetic structure destabilized."

    # EPIDEMIOLOGY MATH
    compliance = stats['trust'] / 100.0; activity = stats['eco'] / 100.0
    if stats.get('mutated_strain_active'): r0 += 1.5 # Increased from 1.0

    r_eff = (r0 * (0.5 + 0.5 * activity)) * (1 - 0.4 * compliance)
    inf = stats['inf']; growth = (r_eff * inf) - inf
    
    # CURE IMPACT
    if stats.get('cure', 0) > 20: growth -= (stats['cure'] * 0.2) # Cure now fights virus harder
    
    growth += np.random.normal(0, 1.5)
    stats['inf'] = round(max(0, min(100, inf + growth)), 1)

    # MORTALITY MATH (Aggressive Update)
    mortality = 0.1
    # If Infection is high, people die faster
    if stats['inf'] > 40: mortality += 1.0 
    if stats['inf'] > 70: mortality += 3.0
    if stats['inf'] > 90: mortality += 5.0
    
    # Hospital Collapse Check
    hospital_capacity = 40 + (stats['eco'] * 0.2)
    load = stats['inf'] * 1.5
    if load > hospital_capacity: 
        mortality += 2.0 # Collapse penalty
        narrative_flavor += "\n[WARNING]: Hospitals overwhelmed."

    stats['pop'] = round(max(0, stats['pop'] - mortality), 1)

    decay = 0.2 + (0.5 if stats['inf'] > 30 else 0)
    stats['eco'] = round(max(0, stats['eco'] - decay), 1)

    return stats, narrative_flavor
    
def get_next_event(stats, used_events, forced_next):
    # ENDINGS
    if stats['inf'] >= 99: return "ending_extinction", {"text": "ENDING: TOTAL INFECTION\nThe virus has consumed the population. Society has collapsed.", "choices": []}
    if stats['pop'] < 10: return "ending_extinction", {"text": "ENDING: SILENT EARTH\nPopulation collapsed below critical levels.", "choices": []}
    if stats['trust'] <= 10: return "ending_revolution", {"text": "ENDING: THE GUILLOTINE\nThe military has seized control. You are under arrest.", "choices": []}
    if stats['eco'] <= 5: return "ending_collapse", {"text": "ENDING: DARK AGES\nEconomy destroyed. Electricity and food distribution failed.", "choices": []}
    if stats.get('cure', 0) >= 95: return "ending_victory", {"text": "ENDING: VICTORY\nThe virus has been eradicated. Humanity survives.", "choices": []}

    # FORCED / ARC
    if forced_next and forced_next in MUTATION_ARC:
        if "strategy" in forced_next: stats['mutated_strain_active'] = True
        return forced_next, MUTATION_ARC[forced_next]

    # MUTATION LOGIC
    if stats.get('mutated_strain_active'):
        mut_keys = [k for k in MUTATION_ARC.keys() if k.startswith("mut_p")]
        played = [k for k in used_events if k in mut_keys]
        if len(played) >= 5:
            stats['mutated_strain_active'] = False; return "mut_finale_win", MUTATION_ARC["mut_finale_win"]
        avail = [k for k in mut_keys if k not in used_events]
        if avail: return random.choice(avail), MUTATION_ARC[random.choice(avail)]

    if stats['day'] > 15 and "mut_start" not in used_events and random.random() < 0.3:
        return "mut_start", MUTATION_ARC["mut_start"]

    # MAIN / RANDOM (Updated for STRICT NO REPETITION)
    day = stats.get('day', 1)
    if day in STORY_ARCS: return f"day_{day}", STORY_ARCS[day]

    # Filter: strict "not in used_events"
    available = [k for k in RANDOM_POOL.keys() if k not in used_events]
    
    if available: 
        eid = random.choice(available)
        return eid, RANDOM_POOL[eid]

    # Fallback if we somehow run out of 130 events
    return "quiet_day", {"text": "STATUS: QUIET DAY\nNo major incidents reported.", "choices": [{"text": "Rest and Reorganize.", "mods": {"trust": 2, "eco": 1}}]}
# ==========================================
# 4. HANDLER (FINAL)
# ==========================================
class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            l = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(l))
            
            # --- LEADERBOARD ---
            if data.get('action') == 'get_leaderboard':
                if DB_STATUS == "ONLINE" and leaderboard_col is not None:
                    try:
                        scores = list(leaderboard_col.find({}, {'_id': 0}).sort("score", -1).limit(10))
                        self.send_json({"leaderboard": scores})
                    except:
                        self.send_json({"leaderboard": []})
                else:
                    self.send_json({"leaderboard": []})
                return

            # --- SUBMIT SCORE ---
            if data.get('action') == 'submit_score':
                uid = data.get('user_id'); name = data.get('name'); s = data.get('stats'); ending = data.get('ending')
                if DB_STATUS == "ONLINE" and leaderboard_col is not None and uid:
                    score = calculate_score(s, ending)
                    exist = leaderboard_col.find_one({"user_id": uid})
                    if not exist or score > exist['score']:
                        leaderboard_col.update_one({"user_id": uid}, {"$set": {"name": name, "score": score, "days": s['day'], "ending": ending}}, upsert=True)
                    self.send_json({"status": "saved", "score": score})
                else:
                    self.send_json({"status": "offline"})
                return

            # --- GAME TURN ---
            stats = data.get('stats', {})
            choice_idx = data.get('choice_index')
            last_event_id = data.get('last_event_id')
            used_events = data.get('used_events', [])
            is_init = data.get('is_init', False)

            # GLOBAL INTEL (TRACKING ONLY - SILENT)
            # We removed the 'global_msg' string logic so it never shows in text.
            if DB_STATUS == "ONLINE" and not is_init and global_choices is not None and last_event_id and choice_idx is not None:
                try:
                    k = f"{last_event_id}_{choice_idx}"; tk = f"{last_event_id}_total"
                    global_choices.update_one({"_id": k}, {"$inc": {"count": 1}}, upsert=True)
                    global_choices.update_one({"_id": tk}, {"$inc": {"count": 1}}, upsert=True)
                except: pass

            if is_init:
                new_stats = {"day": 1, "pop": 100, "trust": 70, "eco": 80, "inf": 5, "cure": 0}
                next_id = "day_1"; next_event = STORY_ARCS[1]; used_events = ["day_1"]; flavor = ""
            else:
                prev = None
                if last_event_id:
                    if last_event_id.startswith("day_"): prev = STORY_ARCS.get(int(last_event_id.split("_")[1]))
                    elif last_event_id in MUTATION_ARC: prev = MUTATION_ARC[last_event_id]
                    elif last_event_id in RANDOM_POOL: prev = RANDOM_POOL[last_event_id]
                
                c_mods = {}; next_fixed = None
                if prev and choice_idx is not None and 0 <= choice_idx < len(prev["choices"]):
                    sel = prev["choices"][choice_idx]
                    c_mods = sel.get("mods", {}); next_fixed = sel.get("next_fixed")
                
                new_stats, flavor = run_simulation(stats, c_mods)
                next_id, next_event = get_next_event(new_stats, used_events, next_fixed)
                if next_id != "quiet_day": used_events.append(next_id)

            text = next_event["text"]
            # REMOVED: if global_msg: text += global_msg
            if flavor: text += f"\n\n[AI ANALYSIS]: {flavor}"

            self.send_json({"stats": new_stats, "narrative": text, "choices": next_event["choices"], "event_id": next_id, "used_events": used_events})

        except Exception as e:
            err_response = {
                "stats": {"day":0,"pop":0,"trust":0,"eco":0,"inf":0},
                "narrative": f"SYSTEM FAILURE RECOVERED: {str(e)}",
                "choices": [{"text": "REBOOT SEQUENCE", "mods": {}}],
                "event_id": "error",
                "used_events": []
            }
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(json.dumps(err_response).encode())

    def send_json(self, d):
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(json.dumps(d).encode())
