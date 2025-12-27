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
    # --- ARC STARTERS ---
    "mut_start": { 
        "text": "CRISIS: OMEGA VARIANT\nDeep sequencing confirms a new strain. It is airborne, highly aggressive, and bypassing current antibodies.", 
        "choices": [
            {"text": "Total Shift: All resources to Omega.", "mods": {"inf": 10, "cure": 5, "eco": -5}, "next_fixed": "mut_strategy_focus"}, 
            {"text": "Hybrid: Split resources.", "mods": {"inf": 5, "cure": 2}, "next_fixed": "mut_strategy_split"},
            {"text": "Ignore: Hope current vaccine works.", "mods": {"trust": -5}, "next_fixed": "mut_strategy_ignore"}
        ] 
    },
    "mut_strategy_focus": { "text": "STRATEGY: OMEGA PROTOCOL\nWe are retooling labs. Infection will spike while we pivot.", "choices": [{"text": "Proceed.", "mods": {"inf": 15, "cure": 10}}] },
    "mut_strategy_split": { "text": "STRATEGY: HYBRID DEFENSE\nWe will fight both strains simultaneously. Progress will be slow.", "choices": [{"text": "Proceed.", "mods": {"cure": 5, "eco": -2}}] },
    "mut_strategy_ignore": { "text": "STRATEGY: STAY THE COURSE\nGambling that Delta immunity covers Omega. Scientists are screaming.", "choices": [{"text": "Silence the scientists.", "mods": {"trust": -15, "pop": -5}}] },
    
    # --- ARC ENDINGS ---
    "mut_finale_win": { "text": "ARC END: THE OMEGA KEY\nWe have cracked the protein shell of the Omega strain.", "choices": [{"text": "Deploy Cure.", "mods": {"cure": 30, "inf": -25, "trust": 15}}] },
    "mut_finale_fail": { "text": "ARC END: VIRAL SUPREMACY\nOmega has mutated again. Our data is useless.", "choices": [{"text": "Fall back.", "mods": {"pop": -20, "trust": -25}}] },

    # --- THE 20 UNIQUE MUTATION EVENTS (Hand-Written) ---
    "mut_p1": { "text": "MUTATION: CYTOKINE STORM\nYoung, healthy adults are dying as their immune systems attack their own lungs.", "choices": [{"text": "Suppress immune systems (Risky).", "mods": {"pop": -2, "cure": 2}}, {"text": "Ration Ventilators.", "mods": {"trust": -10, "pop": -5}}, {"text": "Do Nothing.", "mods": {"pop": -8, "trust": -15}}] },
    "mut_p2": { "text": "MUTATION: CHILDREN AFFECTED\nOmega is targeting pediatric wards. Schools are becoming morgues.", "choices": [{"text": "Close all schools/daycares.", "mods": {"eco": -8, "inf": -5}}, {"text": "Remote learning only.", "mods": {"eco": -2, "trust": -5}}, {"text": "Keep open (Economy first).", "mods": {"pop": -5, "trust": -20}}] },
    "mut_p3": { "text": "MUTATION: WATERBORNE?\nTraces of Omega found in the reservoir. It might be surviving water treatment.", "choices": [{"text": "Shutdown water (Chaos).", "mods": {"eco": -20, "trust": -10}}, {"text": "Boil-water mandate.", "mods": {"inf": 2, "trust": -2}}, {"text": "Chemical bomb the reservoir.", "mods": {"eco": -10, "pop": -1}}] },
    "mut_p4": { "text": "MUTATION: FALSE NEGATIVES\nOmega is not showing up on standard PCR tests.", "choices": [{"text": "Treat everyone as positive.", "mods": {"eco": -15, "inf": -5}}, {"text": "Develop new test (Expensive).", "mods": {"eco": -10, "cure": 5}}, {"text": "Stop testing.", "mods": {"inf": 15, "trust": 5}}] },
    "mut_p5": { "text": "MUTATION: AGGRESSION\nOmega attacks the frontal lobe. Infected patients are becoming violent.", "choices": [{"text": "Sedate all patients.", "mods": {"eco": -5, "cure": -2}}, {"text": "Restrain/Chain them.", "mods": {"trust": -15}}, {"text": "Shoot if violent.", "mods": {"pop": -2, "trust": -20}}] },
    "mut_p6": { "text": "MUTATION: ANIMAL RESERVOIR\nHouse cats and dogs are transmitting Omega.", "choices": [{"text": "Mandatory pet cull.", "mods": {"trust": -30, "inf": -5}}, {"text": "Keep pets inside.", "mods": {"inf": 5}}, {"text": "Ignore.", "mods": {"inf": 10}}] },
    "mut_p7": { "text": "MUTATION: MEDICAL COLLAPSE\nDoctors are dying at 5x the rate of civilians.", "choices": [{"text": "Draft medical students.", "mods": {"trust": -5, "cure": 2}}, {"text": "Robotics automation.", "mods": {"eco": -10, "cure": 1}}, {"text": "Let them die.", "mods": {"pop": -10, "cure": -10}}] },
    "mut_p8": { "text": "MUTATION: CORPSE TOXICITY\nBodies remain contagious for weeks after death.", "choices": [{"text": "Mass cremation pits.", "mods": {"trust": -15, "inf": -5}}, {"text": "Seal mass graves with concrete.", "mods": {"eco": -5}}, {"text": "Standard burial.", "mods": {"inf": 10}}] },
    "mut_p9": { "text": "MUTATION: VACCINE ESCAPE\nPeople vaccinated for Delta are catching Omega.", "choices": [{"text": "Admit the failure.", "mods": {"trust": -20}}, {"text": "Blame the patients.", "mods": {"trust": -10, "pop": -2}}, {"text": "Suppress the data.", "mods": {"inf": 5, "trust": -5}}] },
    "mut_p10": { "text": "MUTATION: HEMORRHAGIC\nOmega now causes internal bleeding. It looks like Ebola.", "choices": [{"text": "Full Hazmat protocols.", "mods": {"eco": -10, "inf": -2}}, {"text": "Isolate the bleeding.", "mods": {"pop": -5}}, {"text": "Panic.", "mods": {"trust": -10}}] },
    "mut_p11": { "text": "MUTATION: SUPPLY CHAIN FEAR\nTruckers refuse to drive into Omega Red Zones.", "choices": [{"text": "Military convoys.", "mods": {"trust": 5, "eco": -5}}, {"text": "Triple hazard pay.", "mods": {"eco": -15}}, {"text": "Force them at gunpoint.", "mods": {"trust": -20}}] },
    "mut_p12": { "text": "MUTATION: RE-INFECTION\nSurvivors are catching it again within 2 weeks.", "choices": [{"text": "Permanent lockdown.", "mods": {"eco": -20, "inf": -10}}, {"text": "Herd immunity is impossible.", "mods": {"trust": -10}}, {"text": "Ignore.", "mods": {"pop": -5}}] },
    "mut_p13": { "text": "MUTATION: ELITE PANIC\nThe wealthy are fleeing to bunkers, spreading Omega to rural areas.", "choices": [{"text": "Shoot down private jets.", "mods": {"trust": 5, "pop": -1}}, {"text": "Ground all flights.", "mods": {"eco": -10}}, {"text": "Let them go.", "mods": {"inf": 10, "trust": -10}}] },
    "mut_p14": { "text": "MUTATION: RELIGIOUS HYSTERIA\nCults claim Omega is the Rapture. Promoting 'Infection Parties'.", "choices": [{"text": "Arrest leaders.", "mods": {"trust": -5, "inf": -2}}, {"text": "Designate as terrorists.", "mods": {"trust": -10, "pop": -2}}, {"text": "Ignore.", "mods": {"inf": 8}}] },
    "mut_p15": { "text": "MUTATION: DATA CORRUPTION\nOmega moves so fast our models are 4 days behind.", "choices": [{"text": "Guess.", "mods": {"inf": 5, "cure": -2}}, {"text": "Manual census (Slow).", "mods": {"eco": -5}}, {"text": "Halt all action.", "mods": {"pop": -5}}] },
    "mut_p16": { "text": "MUTATION: BORDER WAR\nNeighbors are shooting anyone trying to cross.", "choices": [{"text": "Return fire.", "mods": {"pop": -5, "eco": -5}}, {"text": "Close our side.", "mods": {"eco": -5}}, {"text": "Negotiate.", "mods": {"inf": 5}}] },
    "mut_p17": { "text": "MUTATION: POWER GRID\nNuclear plant crews are sick. Core temp rising.", "choices": [{"text": "Automated shutdown.", "mods": {"eco": -15}}, {"text": "Send sick crew back in.", "mods": {"pop": -1, "trust": -10}}, {"text": "Risk meltdown.", "mods": {"pop": -20}}] },
    "mut_p18": { "text": "MUTATION: PLAGUE RATS\nSanitation failed. Rats are spreading Omega into homes.", "choices": [{"text": "Poison the city.", "mods": {"eco": -5, "pop": -2}}, {"text": "Release cats.", "mods": {"inf": 2}}, {"text": "Ignore.", "mods": {"inf": 10}}] },
    "mut_p19": { "text": "MUTATION: INTERNET TROLLS\nViral challenge 'Catch Omega' is trending.", "choices": [{"text": "Shut down internet.", "mods": {"trust": -15, "eco": -10}}, {"text": "Trace and arrest.", "mods": {"trust": -5}}, {"text": "Ignore.", "mods": {"inf": 5, "pop": -2}}] },
    "mut_p20": { "text": "MUTATION: OMEGA BRAIN FOG\nKey government leaders are infected and making bad calls.", "choices": [{"text": "Remove them (Coup).", "mods": {"trust": -20}}, {"text": "Cover it up.", "mods": {"eco": -5, "cure": -5}}, {"text": "Follow orders.", "mods": {"pop": -5}}] }
}


RANDOM_POOL = {
    # ---------------------------------------------------------
    # 1. CURE & RESEARCH (30 Events)
    # ---------------------------------------------------------
    "cure_1": { "text": "RESEARCH: AI FOLDING\nDeepMind has simulated the viral protein structure.", "choices": [{"text": "Mass produce results.", "mods": {"cure": 15, "eco": -10}}, {"text": "Verify data first.", "mods": {"cure": 5, "trust": 5}}, {"text": "Sell data for funds.", "mods": {"eco": 10, "trust": -10}}] },
    "cure_2": { "text": "RESEARCH: HUMAN TRIALS\n3,000 volunteers ready for risky vaccine testing.", "choices": [{"text": "Authorize immediately.", "mods": {"cure": 20, "pop": -2}}, {"text": "Wait for safety checks.", "mods": {"cure": 5, "trust": 2}}, {"text": "Cancel trials.", "mods": {"trust": -5}}] },
    "cure_3": { "text": "RESEARCH: ROGUE DATA\nHackers stole vaccine data from a rival nation.", "choices": [{"text": "Use the stolen data.", "mods": {"cure": 12, "trust": -5}}, {"text": "Delete it.", "mods": {"trust": 5}}, {"text": "Expose the hackers.", "mods": {"trust": 2}}] },
    "cure_4": { "text": "RESEARCH: GLOBAL SUMMIT\nWorld scientists want to merge databases.", "choices": [{"text": "Share all intel.", "mods": {"cure": 10, "trust": 5}}, {"text": "Keep secrets.", "mods": {"trust": -5, "eco": 5}}, {"text": "Send fake data.", "mods": {"trust": -10, "eco": 5}}] },
    "cure_5": { "text": "RESEARCH: IMMUNITY GENE\nA survivor in Sector 4 shows natural immunity.", "choices": [{"text": "Aggressive extraction.", "mods": {"cure": 15, "trust": -10}}, {"text": "Pay for samples.", "mods": {"cure": 8, "eco": -2}}, {"text": "Clone the gene.", "mods": {"cure": 5, "eco": -5}}] },
    "cure_6": { "text": "RESEARCH: FUNGAL COMPOUND\nRare fungus shows anti-viral properties.", "choices": [{"text": "Strip mine forest.", "mods": {"cure": 10, "eco": -10}}, {"text": "Synthesize slowly.", "mods": {"cure": 4, "eco": -2}}, {"text": "Ignore.", "mods": {}}] },
    "cure_7": { "text": "RESEARCH: CRYO-LAB\nUnfreezing old 1990s samples might help.", "choices": [{"text": "Do it.", "mods": {"cure": 5}}, {"text": "Too risky.", "mods": {"trust": 2}}, {"text": "Destroy samples.", "mods": {"trust": -2}}] },
    "cure_8": { "text": "RESEARCH: MIRACLE CHILD\nA child healed herself overnight.", "choices": [{"text": "Study her.", "mods": {"cure": 15, "trust": -5}}, {"text": "Leave her alone.", "mods": {"trust": 10}}, {"text": "Publicize miracle.", "mods": {"trust": 5}}] },
    "cure_9": { "text": "RESEARCH: FAILED STATE\nA collapsed neighbor offers data for food.", "choices": [{"text": "Trade food.", "mods": {"cure": 10, "eco": -5}}, {"text": "Seize data.", "mods": {"cure": 10, "trust": -10}}, {"text": "Ignore request.", "mods": {"pop": -2}}] },
    "cure_10": { "text": "RESEARCH: LAB EXPLOSION\nData servers are burning.", "choices": [{"text": "Save the drives.", "mods": {"cure": 5, "pop": -1}}, {"text": "Save the staff.", "mods": {"trust": 5}}, {"text": "Contain the fire.", "mods": {"eco": -2}}] },
    "cure_11": { "text": "RESEARCH: ANIMAL TEST\nPrimates showing promising antibody response.", "choices": [{"text": "Accelerate testing.", "mods": {"cure": 8, "trust": -2}}, {"text": "Standard protocol.", "mods": {"cure": 3}}, {"text": "Stop animal testing.", "mods": {"trust": 2}}] },
    "cure_12": { "text": "RESEARCH: SYMPTOM BLOCKER\nA drug stops death, but doesn't cure.", "choices": [{"text": "Distribute it.", "mods": {"pop": 2, "inf": 5}}, {"text": "Focus on real cure.", "mods": {"cure": 2}}, {"text": "Ban it.", "mods": {"trust": -5}}] },
    "cure_13": { "text": "RESEARCH: BLACK MARKET\nCartels claim to have a working antiviral.", "choices": [{"text": "Buy a sample.", "mods": {"eco": -5, "cure": 5}}, {"text": "Raid them.", "mods": {"trust": 2}}, {"text": "Ignore.", "mods": {}}] },
    "cure_14": { "text": "RESEARCH: UNIVERSITY NETWORK\nStudents want to use dorm PCs for distributed computing.", "choices": [{"text": "Authorize grid.", "mods": {"cure": 6, "eco": -1}}, {"text": "Security risk.", "mods": {"trust": -2}}, {"text": "Fund upgrade.", "mods": {"eco": -5, "cure": 8}}] },
    "cure_15": { "text": "RESEARCH: ANCIENT TEXT\nHistory records a similar plague cure.", "choices": [{"text": "Investigate.", "mods": {"cure": 4}}, {"text": "Ignore myths.", "mods": {}}, {"text": "Burn the books.", "mods": {"trust": -2}}] },
    "cure_16": { "text": "RESEARCH: SIDE EFFECTS\nVaccine candidate causes blindness in 1% of cases.", "choices": [{"text": "Acceptable loss.", "mods": {"cure": 15, "trust": -15}}, {"text": "Scrap it.", "mods": {"cure": -5, "trust": 5}}, {"text": "Hide results.", "mods": {"trust": -10}}] },
    "cure_17": { "text": "RESEARCH: WEATHER PATTERNS\nCold slows the virus.", "choices": [{"text": "Cooling infrastructure.", "mods": {"inf": -5, "eco": -5}}, {"text": "Ignore.", "mods": {}}, {"text": "Research link.", "mods": {"cure": 2}}] },
    "cure_18": { "text": "RESEARCH: BLOOD BANK\nRunning low on plasma for testing.", "choices": [{"text": "Mandatory donation.", "mods": {"cure": 5, "trust": -5}}, {"text": "Paid donation.", "mods": {"cure": 5, "eco": -5}}, {"text": "Import plasma.", "mods": {"eco": -8}}] },
    "cure_19": { "text": "RESEARCH: PARASITE\nA parasite seems to eat the virus.", "choices": [{"text": "Infect patients.", "mods": {"cure": 10, "pop": -5}}, {"text": "Study safely.", "mods": {"cure": 2}}, {"text": "Destroy it.", "mods": {}}] },
    "cure_20": { "text": "RESEARCH: WHO GRANT\nFunding offered for data access.", "choices": [{"text": "Accept.", "mods": {"eco": 10, "cure": 2}}, {"text": "Deny.", "mods": {"trust": 5}}, {"text": "Negotiate more.", "mods": {"eco": 5}}] },
    "cure_21": { "text": "RESEARCH: SUPERCOMPUTER\nNeeds 50% of national power grid.", "choices": [{"text": "Divert power.", "mods": {"cure": 12, "trust": -10}}, {"text": "Too expensive.", "mods": {"eco": 2}}, {"text": "Use backup gen.", "mods": {"cure": 5, "eco": -5}}] },
    "cure_22": { "text": "RESEARCH: TWIN STUDY\nIdentical twins show different reactions.", "choices": [{"text": "Deep genetic scan.", "mods": {"cure": 5, "eco": -2}}, {"text": "Ignore.", "mods": {}}, {"text": "Recruit more.", "mods": {"cure": 2}}] },
    "cure_23": { "text": "RESEARCH: HERBALIST\nClaims local tea works.", "choices": [{"text": "Test it.", "mods": {"cure": 2, "eco": -1}}, {"text": "Debunk it.", "mods": {"trust": 2}}, {"text": "Tax sales.", "mods": {"eco": 2}}] },
    "cure_24": { "text": "RESEARCH: OCEAN VENT\nDeep sea bacteria might help.", "choices": [{"text": "Launch expedition.", "mods": {"cure": 8, "eco": -5}}, {"text": "Focus on land.", "mods": {}}, {"text": "Automated drones.", "mods": {"cure": 4}}] },
    "cure_25": { "text": "RESEARCH: RADIATION\nLow level radiation kills the virus surface.", "choices": [{"text": "Irradiate supplies.", "mods": {"inf": -5, "pop": -1}}, {"text": "Unsafe.", "mods": {"trust": 2}}, {"text": "Test on animals.", "mods": {"cure": 2}}] },
    "cure_26": { "text": "RESEARCH: NANOBOTS\nExperimental tech available.", "choices": [{"text": "Deploy prototype.", "mods": {"cure": 15, "eco": -15}}, {"text": "Wait for v2.", "mods": {"cure": 2}}, {"text": "Cancel project.", "mods": {"eco": 5}}] },
    "cure_27": { "text": "RESEARCH: HIVE MIND\nPattern matching suggests insect behavior.", "choices": [{"text": "Entomologist team.", "mods": {"cure": 6, "eco": -2}}, {"text": "Nonsense.", "mods": {}}, {"text": "Publish theory.", "mods": {"trust": -2}}] },
    "cure_28": { "text": "RESEARCH: SLEEP CYCLE\nVirus replicates during REM sleep.", "choices": [{"text": "Wakefulness pills.", "mods": {"inf": -5, "pop": -2}}, {"text": "Ignore.", "mods": {}}, {"text": "Study dreams.", "mods": {"cure": 2}}] },
    "cure_29": { "text": "RESEARCH: OXYGEN HYPER-DOSE\nPure oxygen kills it.", "choices": [{"text": "Build O2 bars.", "mods": {"inf": -2, "eco": -5}}, {"text": "Impractical.", "mods": {}}, {"text": "Ventilator upgrades.", "mods": {"cure": 2}}] },
    "cure_30": { "text": "RESEARCH: THE FINAL KEY\nWe are 90% there. Just need one push.", "choices": [{"text": "All resources.", "mods": {"cure": 10, "eco": -20, "trust": -10}}, {"text": "Stay steady.", "mods": {"cure": 2}}, {"text": "Crowdsource.", "mods": {"cure": 5, "trust": 5}}] },

    # ---------------------------------------------------------
    # 2. INFRASTRUCTURE & DISASTERS (15 Events)
    # ---------------------------------------------------------
    "infra_1": { "text": "SITUATION: OXYGEN LEAK\nHospital supply ruptured.", "choices": [{"text": "Industrial divert.", "mods": {"eco": -5}}, {"text": "Ration (Triage).", "mods": {"pop": -5, "trust": -10}}, {"text": "Import.", "mods": {"eco": -15, "trust": 5}}] },
    "infra_2": { "text": "SITUATION: WATER CONTAMINATION\nFiltration failure.", "choices": [{"text": "Fix immediately.", "mods": {"eco": -8}}, {"text": "Ration.", "mods": {"trust": -10}}, {"text": "Cover up.", "mods": {"pop": -5, "trust": -20}}] },
    "infra_3": { "text": "SITUATION: INTERNET BLACKOUT\nCyber-attack.", "choices": [{"text": "Restore civilian.", "mods": {"eco": -5}}, {"text": "Restore military.", "mods": {"trust": -10}}, {"text": "Blame enemies.", "mods": {"trust": 5, "eco": -2}}] },
    "infra_4": { "text": "SITUATION: WILDFIRES\nSuburbs burning.", "choices": [{"text": "Evacuate.", "mods": {"inf": 5}}, {"text": "Stay put.", "mods": {"pop": -2}}, {"text": "Cloud seed.", "mods": {"eco": -5}}] },
    "infra_5": { "text": "SITUATION: OIL SPILL\nTanker grounded.", "choices": [{"text": "Clean up.", "mods": {"eco": -5}}, {"text": "Ignore.", "mods": {"trust": -5}}, {"text": "Burn slick.", "mods": {"pop": -1}}] },
    "infra_6": { "text": "SITUATION: SATELLITE DEBRIS\nCrashed in city.", "choices": [{"text": "Salvage.", "mods": {"eco": 5}}, {"text": "Warn public.", "mods": {"trust": 2}}, {"text": "Secret recovery.", "mods": {"trust": -2}}] },
    "infra_7": { "text": "SITUATION: NUCLEAR LEAK\nCoolant failure.", "choices": [{"text": "Shutdown.", "mods": {"eco": -15}}, {"text": "Vent radiation.", "mods": {"pop": -2, "trust": -10}}, {"text": "Cover up.", "mods": {"pop": -5, "trust": -20}}] },
    "infra_8": { "text": "SITUATION: DAM CRACK\nHeavy rains.", "choices": [{"text": "Evacuate valley.", "mods": {"eco": -5, "inf": 2}}, {"text": "Repairs.", "mods": {"eco": -10}}, {"text": "Pray.", "mods": {"pop": -5}}] },
    "infra_9": { "text": "SITUATION: BRIDGE COLLAPSE\nMain route severed.", "choices": [{"text": "Rebuild.", "mods": {"eco": -10}}, {"text": "Ferries.", "mods": {"inf": 5}}, {"text": "Ignore.", "mods": {"eco": -5, "trust": -5}}] },
    "infra_10": { "text": "SITUATION: GPS FAILURE\nNav systems down.", "choices": [{"text": "Ground flights.", "mods": {"eco": -5}}, {"text": "Manual nav.", "mods": {"pop": -1}}, {"text": "Wait.", "mods": {"trust": -2}}] },
    "infra_11": { "text": "SITUATION: SEWAGE BACKUP\nTreatment plant unmanned.", "choices": [{"text": "Deploy army.", "mods": {"trust": 5, "eco": -2}}, {"text": "Ignore.", "mods": {"inf": 5, "pop": -1}}, {"text": "Bleach dump.", "mods": {"eco": -5}}] },
    "infra_12": { "text": "SITUATION: AIR TRAFFIC\nControllers sick.", "choices": [{"text": "Close airspace.", "mods": {"eco": -10}}, {"text": "Auto-pilot.", "mods": {"pop": -1}}, {"text": "Train reserves.", "mods": {"eco": -2}}] },
    "infra_13": { "text": "SITUATION: GARBAGE STRIKE\nRats swarming.", "choices": [{"text": "Burn it.", "mods": {"pop": -1, "inf": -1}}, {"text": "Pay demands.", "mods": {"eco": -5}}, {"text": "Deploy inmates.", "mods": {"trust": -5}}] },
    "infra_14": { "text": "SITUATION: GRID OVERLOAD\nEveryone staying home using AC.", "choices": [{"text": "Rolling blackouts.", "mods": {"trust": -5}}, {"text": "Buy power.", "mods": {"eco": -10}}, {"text": "Ignore.", "mods": {"pop": -1}}] },
    "infra_15": { "text": "SITUATION: SUBWAY FLOOD\nPumps failed.", "choices": [{"text": "Seal stations.", "mods": {"trust": -2}}, {"text": "Pump it out.", "mods": {"eco": -5}}, {"text": "Abandon lines.", "mods": {"eco": -2}}] },

    # ---------------------------------------------------------
    # 3. SOCIAL UNREST & CRIME (20 Events)
    # ---------------------------------------------------------
    "soc_1": { "text": "SITUATION: PRISON OUTBREAK\nGuards fleeing.", "choices": [{"text": "Release non-violent.", "mods": {"trust": -5, "inf": 2}}, {"text": "Lockdown.", "mods": {"trust": -5}}, {"text": "Ignore.", "mods": {"inf": 5, "trust": -10}}] },
    "soc_2": { "text": "SITUATION: LOOTING WAVE\nRiots downtown.", "choices": [{"text": "Shoot on sight.", "mods": {"pop": -5, "trust": -20}}, {"text": "Curfew.", "mods": {"eco": -5, "inf": -2}}, {"text": "Let it burn.", "mods": {"eco": -10}}] },
    "soc_3": { "text": "SITUATION: BLACK MARKET\nStolen meds.", "choices": [{"text": "Raids.", "mods": {"trust": -5}}, {"text": "Buy stock.", "mods": {"eco": -10}}, {"text": "Legalize.", "mods": {"eco": 5, "trust": -10}}] },
    "soc_4": { "text": "SITUATION: RELIGIOUS CULT\nMass gatherings.", "choices": [{"text": "Raid.", "mods": {"trust": -10, "pop": -1}}, {"text": "Ignore.", "mods": {"inf": 5}}, {"text": "Negotiate.", "mods": {"trust": 2, "inf": 2}}] },
    "soc_5": { "text": "SITUATION: SUICIDE PACT\nDoomsday cult.", "choices": [{"text": "Intervene.", "mods": {"trust": 5}}, {"text": "Ignore.", "mods": {"pop": -1}}, {"text": "Censor news.", "mods": {"trust": -5}}] },
    "soc_6": { "text": "SITUATION: TIKTOK CHALLENGE\nLicking doorknobs.", "choices": [{"text": "Ban app.", "mods": {"trust": -5}}, {"text": "PSA.", "mods": {"eco": -2}}, {"text": "Arrest kids.", "mods": {"trust": -2}}] },
    "soc_7": { "text": "SITUATION: DIGITAL CULT\n'Virus is a sim'.", "choices": [{"text": "Shut down servers.", "mods": {"trust": -5}}, {"text": "Ignore.", "mods": {"inf": 5}}, {"text": "Infiltrate.", "mods": {"trust": 2}}] },
    "soc_8": { "text": "SITUATION: VIGILANTES\nArresting 'infected'.", "choices": [{"text": "Stop them.", "mods": {"trust": -5}}, {"text": "Deputize them.", "mods": {"trust": -15, "inf": -2}}, {"text": "Ignore.", "mods": {"pop": -1}}] },
    "soc_9": { "text": "SITUATION: FOOD RIOTS\nEmpty shelves.", "choices": [{"text": "Ration cards.", "mods": {"trust": -5}}, {"text": "Army food drops.", "mods": {"trust": 5, "eco": -5}}, {"text": "Free market.", "mods": {"pop": -2}}] },
    "soc_10": { "text": "SITUATION: SQUATTERS\nOccupying hotels.", "choices": [{"text": "Evict force.", "mods": {"trust": -5}}, {"text": "Allow it.", "mods": {"trust": 5, "eco": -5}}, {"text": "Tax them.", "mods": {"eco": 2}}] },
    "soc_11": { "text": "SITUATION: CURFEW BREAKERS\nSpring break party.", "choices": [{"text": "Mass arrest.", "mods": {"trust": -5, "inf": -2}}, {"text": "Water cannons.", "mods": {"trust": -10}}, {"text": "Ignore.", "mods": {"inf": 5}}] },
    "soc_12": { "text": "SITUATION: MENTAL HEALTH\nSuicide rates up.", "choices": [{"text": "Hotlines.", "mods": {"eco": -2}}, {"text": "Free meds.", "mods": {"eco": -5, "trust": 5}}, {"text": "Ignore.", "mods": {"pop": -1}}] },
    "soc_13": { "text": "SITUATION: FAKE CURES\nBleach injections.", "choices": [{"text": "Arrest sellers.", "mods": {"trust": 5}}, {"text": "Education.", "mods": {"eco": -2}}, {"text": "Natural selection.", "mods": {"pop": -1}}] },
    "soc_14": { "text": "SITUATION: CARTEL WAR\nFighting for turf.", "choices": [{"text": "Send army.", "mods": {"pop": -1, "trust": 5}}, {"text": "Let them fight.", "mods": {"pop": -2}}, {"text": "Negotiate.", "mods": {"trust": -10}}] },
    "soc_15": { "text": "SITUATION: ZOMBIE RUMOR\nPanic over reanimation.", "choices": [{"text": "Show bodies.", "mods": {"trust": -5}}, {"text": "Deny.", "mods": {"trust": 2}}, {"text": "Suppress internet.", "mods": {"trust": -5}}] },
    "soc_16": { "text": "SITUATION: STOLEN BODIES\nSold for parts.", "choices": [{"text": "Cremation mandate.", "mods": {"trust": -10}}, {"text": "Guard morgues.", "mods": {"eco": -2}}, {"text": "Ignore.", "mods": {"trust": -5}}] },
    "soc_17": { "text": "SITUATION: ORPHAN CRISIS\nParents dead.", "choices": [{"text": "State homes.", "mods": {"eco": -5}}, {"text": "Foster program.", "mods": {"trust": 5}}, {"text": "Street kids.", "mods": {"trust": -5}}] },
    "soc_18": { "text": "SITUATION: VIP BUNKERS\nRich buying vents.", "choices": [{"text": "Seize vents.", "mods": {"trust": 10, "eco": -5}}, {"text": "Allow it.", "mods": {"trust": -10}}, {"text": "Tax heavy.", "mods": {"eco": 5}}] },
    "soc_19": { "text": "SITUATION: HATE CRIMES\nBlaming foreigners.", "choices": [{"text": "Strict policing.", "mods": {"trust": -5}}, {"text": "Unity speech.", "mods": {"trust": 2}}, {"text": "Ignore.", "mods": {"inf": 2}}] },
    "soc_20": { "text": "SITUATION: DOCTOR STRIKE\nWant hazard pay.", "choices": [{"text": "Pay them.", "mods": {"eco": -5}}, {"text": "Draft them.", "mods": {"trust": -10}}, {"text": "Replace them.", "mods": {"pop": -2}}] },

    # ---------------------------------------------------------
    # 4. POLITICS & ECONOMY (20 Events)
    # ---------------------------------------------------------
    "pol_1": { "text": "SITUATION: BANK RUN\nCash shortage.", "choices": [{"text": "Freeze banks.", "mods": {"trust": -15}}, {"text": "Print money.", "mods": {"eco": -15}}, {"text": "Bailout.", "mods": {"eco": -10, "trust": -5}}] },
    "pol_2": { "text": "SITUATION: PRICE GOUGING\nMeds expensive.", "choices": [{"text": "Seize stock.", "mods": {"trust": 5, "eco": -2}}, {"text": "Free market.", "mods": {"trust": -10}}, {"text": "Subsidize.", "mods": {"eco": -5}}] },
    "pol_3": { "text": "SITUATION: SENATOR SCANDAL\nParty during lockdown.", "choices": [{"text": "Resign.", "mods": {"trust": 5}}, {"text": "Cover up.", "mods": {"trust": -15}}, {"text": "Blame media.", "mods": {"trust": -5}}] },
    "pol_4": { "text": "SITUATION: CRYPTO CRASH\nAssets wiped.", "choices": [{"text": "Bailout.", "mods": {"eco": -5}}, {"text": "Ignore.", "mods": {"trust": -5}}, {"text": "Investigate.", "mods": {"eco": -2}}] },
    "pol_5": { "text": "SITUATION: GOLD RESERVES\nCurrency drop.", "choices": [{"text": "Sell gold.", "mods": {"eco": 10, "trust": -5}}, {"text": "Hold.", "mods": {"trust": 2}}, {"text": "Buy.", "mods": {"eco": -10}}] },
    "pol_6": { "text": "SITUATION: ELECTION YEAR\nOpponent campaigning.", "choices": [{"text": "Delay election.", "mods": {"trust": -20}}, {"text": "Reopen economy.", "mods": {"inf": 10, "eco": 10}}, {"text": "Smear campaign.", "mods": {"trust": -5}}] },
    "pol_7": { "text": "SITUATION: TRADE WAR\nTariffs on meds.", "choices": [{"text": "Pay tariffs.", "mods": {"eco": -10}}, {"text": "Retaliate.", "mods": {"eco": -5, "trust": 5}}, {"text": "Smuggle.", "mods": {"trust": -5}}] },
    "pol_8": { "text": "SITUATION: PENSION FUND\nCollapsed.", "choices": [{"text": "Bailout.", "mods": {"eco": -10}}, {"text": "Cut payouts.", "mods": {"trust": -15}}, {"text": "Ignore.", "mods": {"trust": -10}}] },
    "pol_9": { "text": "SITUATION: UNION STRIKE\nGeneral stoppage.", "choices": [{"text": "Meet demands.", "mods": {"eco": -10}}, {"text": "Break strike.", "mods": {"trust": -10}}, {"text": "Negotiate.", "mods": {"eco": -2}}] },
    "pol_10": { "text": "SITUATION: BILLIONAIRE BUNKER\nTax flight.", "choices": [{"text": "Exit tax.", "mods": {"eco": 10, "trust": -5}}, {"text": "Seize assets.", "mods": {"trust": 5, "eco": 5}}, {"text": "Let go.", "mods": {"eco": -5}}] },
    "pol_11": { "text": "SITUATION: DATA LEAK\nTrue death toll.", "choices": [{"text": "Deny.", "mods": {"trust": -10}}, {"text": "Apologize.", "mods": {"trust": 5}}, {"text": "Distract.", "mods": {"eco": -5}}] },
    "pol_12": { "text": "SITUATION: ARMY DESERTION\nSoldiers leaving.", "choices": [{"text": "Court martial.", "mods": {"trust": -10}}, {"text": "Bonuses.", "mods": {"eco": -5}}, {"text": "Ignore.", "mods": {"trust": -5}}] },
    "pol_13": { "text": "SITUATION: UN SANCTIONS\nHuman rights violation.", "choices": [{"text": "Comply.", "mods": {"trust": -5, "eco": -5}}, {"text": "Ignore.", "mods": {"eco": -10}}, {"text": "Quit UN.", "mods": {"trust": -5}}] },
    "pol_14": { "text": "SITUATION: NEIGHBOR WAR\nBorder skirmish.", "choices": [{"text": "Defend.", "mods": {"eco": -10, "pop": -2}}, {"text": "Cede land.", "mods": {"trust": -15}}, {"text": "Peace talks.", "mods": {"trust": 2}}] },
    "pol_15": { "text": "SITUATION: STOCK MARKET\nFree fall.", "choices": [{"text": "Close market.", "mods": {"trust": -5}}, {"text": "Inject cash.", "mods": {"eco": -10}}, {"text": "Watch.", "mods": {"trust": -2}}] },
    "pol_16": { "text": "SITUATION: HOUSING CRASH\nMass evictions.", "choices": [{"text": "Freeze rent.", "mods": {"eco": -5, "trust": 5}}, {"text": "Allow evictions.", "mods": {"trust": -10}}, {"text": "State housing.", "mods": {"eco": -8}}] },
    "pol_17": { "text": "SITUATION: OIL PRICE\nNegative value.", "choices": [{"text": "Buy reserves.", "mods": {"eco": -5}}, {"text": "Subsidy.", "mods": {"eco": -2}}, {"text": "Ignore.", "mods": {}}] },
    "pol_18": { "text": "SITUATION: TECH MONOPOLY\nOffering tracking app.", "choices": [{"text": "Mandate it.", "mods": {"inf": -5, "trust": -10}}, {"text": "Refuse.", "mods": {"inf": 2}}, {"text": "Tax them.", "mods": {"eco": 5}}] },
    "pol_19": { "text": "SITUATION: FARMER SUBSIDY\nDemanding cash.", "choices": [{"text": "Pay.", "mods": {"eco": -5}}, {"text": "Refuse.", "mods": {"trust": -5}}, {"text": "Import food.", "mods": {"eco": -8}}] },
    "pol_20": { "text": "SITUATION: STATE MEDIA\nJournalists asking questions.", "choices": [{"text": "Censor.", "mods": {"trust": -5}}, {"text": "Answer.", "mods": {"trust": 5, "eco": -2}}, {"text": "Arrest them.", "mods": {"trust": -10}}] },

    # ---------------------------------------------------------
    # 5. MISC & WILD CARDS (15 Events)
    # ---------------------------------------------------------
    "wild_1": { "text": "SITUATION: CELEBRITY HOAX\nPop star claims fake.", "choices": [{"text": "Arrest.", "mods": {"trust": -5}}, {"text": "Ignore.", "mods": {"inf": 5}}, {"text": "Counter.", "mods": {"eco": -2}}] },
    "wild_2": { "text": "SITUATION: FOREIGN SPIES\nStealing data.", "choices": [{"text": "Execute.", "mods": {"trust": 5, "eco": -5}}, {"text": "Trade.", "mods": {"trust": -10, "eco": 5}}, {"text": "Turn.", "mods": {"inf": 2}}] },
    "wild_3": { "text": "SITUATION: ZOO ANIMALS\nStarving.", "choices": [{"text": "Feed.", "mods": {"eco": -2}}, {"text": "Kill.", "mods": {"trust": -5}}, {"text": "Release.", "mods": {"trust": -2}}] },
    "wild_4": { "text": "SITUATION: CRUISE SHIP\nInfected.", "choices": [{"text": "Dock.", "mods": {"inf": 5}}, {"text": "Refuse.", "mods": {"trust": -5}}, {"text": "Quarantine.", "mods": {"eco": -5}}] },
    "wild_5": { "text": "SITUATION: ROGUE SCIENTIST\nUnethical tests.", "choices": [{"text": "Use data.", "mods": {"cure": 10, "trust": -10}}, {"text": "Arrest.", "mods": {"trust": 5}}, {"text": "Fund.", "mods": {"eco": -5, "cure": 5}}] },
    "wild_6": { "text": "SITUATION: HERBAL REMEDY\nFake news.", "choices": [{"text": "Ban.", "mods": {"trust": -5}}, {"text": "PSA.", "mods": {"eco": -1}}, {"text": "Tax.", "mods": {"eco": 2}}] },
    "wild_7": { "text": "SITUATION: GHOST TOWNS\n0% survival.", "choices": [{"text": "Burn.", "mods": {"trust": -5}}, {"text": "Seal.", "mods": {"trust": -2}}, {"text": "Loot.", "mods": {"eco": 5, "trust": -10}}] },
    "wild_8": { "text": "SITUATION: AI PREDICTION\nPredicts doom.", "choices": [{"text": "Trust AI (Cull).", "mods": {"eco": 5, "trust": -25, "pop": -5}}, {"text": "Trust Humans.", "mods": {"trust": 5}}, {"text": "Off switch.", "mods": {"eco": -5}}] },
    "wild_9": { "text": "SITUATION: ANCIENT RUINS\nArtifact found.", "choices": [{"text": "Sell.", "mods": {"eco": 10}}, {"text": "Museum.", "mods": {"trust": 2}}, {"text": "Cursed?", "mods": {"trust": -2}}] },
    "wild_10": { "text": "SITUATION: METEOR SHOWER\nSpectacle.", "choices": [{"text": "View.", "mods": {"trust": 5, "inf": 2}}, {"text": "Inside.", "mods": {"trust": -2}}, {"text": "Ignore.", "mods": {}}] },
    "wild_11": { "text": "SITUATION: SOLAR FLARE\nComms glitch.", "choices": [{"text": "Fix.", "mods": {"eco": -2}}, {"text": "Wait.", "mods": {}}, {"text": "Blame virus.", "mods": {"trust": -2}}] },
    "wild_12": { "text": "SITUATION: VOLCANO\nAsh cloud.", "choices": [{"text": "Masks.", "mods": {"eco": -2}}, {"text": "Evacuate.", "mods": {"eco": -5, "inf": 2}}, {"text": "Ignore.", "mods": {"pop": -1}}] },
    "wild_13": { "text": "SITUATION: LOCUSTS\nEating crops.", "choices": [{"text": "Pesticide.", "mods": {"eco": -5}}, {"text": "Burn fields.", "mods": {"eco": -10}}, {"text": "Eat them.", "mods": {"pop": -1}}] },
    "wild_14": { "text": "SITUATION: UFO?\nStrange lights.", "choices": [{"text": "Investigate.", "mods": {"eco": -2}}, {"text": "Ignore.", "mods": {}}, {"text": "Attack.", "mods": {"trust": -5}}] },
    "wild_15": { "text": "SITUATION: SERIAL KILLER\nTargeting doctors.", "choices": [{"text": "Manhunt.", "mods": {"eco": -5}}, {"text": "Bodyguards.", "mods": {"eco": -2}}, {"text": "Bait trap.", "mods": {"pop": -1}}] }
}

# --- PROCEDURAL GENERATION (Smart & Varied, 3 Choices) ---
sectors = ["North", "South", "East", "West", "Central", "Industrial", "Slum", "Tech", "Port", "Rural"]
issues = ["Food Riots", "Power Failure", "Medical Shortage", "Militia Uprising", "Infection Spike", "Water Crisis", "Fire Outbreak", "Supply Raid"]
flavor_text = ["Command awaits orders.", "Situation critical.", "Locals are panicking.", "Casualties rising.", "Local government non-responsive."]

# Option Pools (Mix & Match for variety)
# Choice 1: Proactive / Expensive
opt_1_pool = [
    ("Send Military Aid.", {"trust": 2, "eco": -3}),
    ("Dispatch Emergency Crews.", {"trust": 3, "eco": -2}),
    ("Authorize Relief Funds.", {"trust": 5, "eco": -5}),
    ("Deploy National Guard.", {"trust": 1, "inf": -1, "eco": -4}),
    ("Send Medical Drones.", {"cure": 1, "eco": -2})
]

# Choice 2: Harsh / Effective
opt_2_pool = [
    ("Enforce Quarantine.", {"inf": -2, "pop": -1, "trust": -2}),
    ("Declare Martial Law.", {"trust": -10, "inf": -5}),
    ("Seal the District.", {"pop": -2, "trust": -5}),
    ("Arrest Agitators.", {"trust": -3, "pop": -1}),
    ("Use Tear Gas.", {"trust": -5, "inf": -1})
]

# Choice 3: Passive / Negligent
opt_3_pool = [
    ("Do Nothing.", {"trust": -5, "pop": -2}),
    ("Focus on Virus (Ignore).", {"cure": 1, "trust": -5, "pop": -1}),
    ("Let local police handle it.", {"trust": -2}),
    ("Suppress media coverage.", {"trust": -5, "eco": 1}),
    ("Wait for reports.", {"pop": -1, "inf": 1})
]

# Generate 105 unique procedural events (ID: proc_100 to proc_204)
# Using a fixed range ensures IDs are unique and filterable
for i in range(100, 205):
    sec = random.choice(sectors)
    iss = random.choice(issues)
    flav = random.choice(flavor_text)
    
    c1 = random.choice(opt_1_pool)
    c2 = random.choice(opt_2_pool)
    c3 = random.choice(opt_3_pool)

    eid = f"proc_{i}"
    RANDOM_POOL[eid] = {
        "text": f"REPORT: {sec} Sector\nAlert: {iss} reported.\n{flav}",
        "choices": [
            {"text": c1[0], "mods": c1[1]},
            {"text": c2[0], "mods": c2[1]},
            {"text": c3[0], "mods": c3[1]}
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
    # 1. CHECK FOR GAME OVER CONDITIONS
    if stats['inf'] >= 99: return "ending_extinction", {"text": "ENDING: TOTAL INFECTION\nThe virus has consumed the population. Society has collapsed.", "choices": []}
    if stats['pop'] < 10: return "ending_extinction", {"text": "ENDING: SILENT EARTH\nPopulation collapsed below critical levels.", "choices": []}
    if stats['trust'] <= 10: return "ending_revolution", {"text": "ENDING: THE GUILLOTINE\nThe military has seized control. You are under arrest.", "choices": []}
    if stats['eco'] <= 5: return "ending_collapse", {"text": "ENDING: DARK AGES\nEconomy destroyed. Electricity and food distribution failed.", "choices": []}
    if stats.get('cure', 0) >= 95: return "ending_victory", {"text": "ENDING: VICTORY\nThe virus has been eradicated. Humanity survives. YOU helped us win.", "choices": []}

    # 2. HANDLE FORCED EVENTS (e.g., Arc Start -> Strategy)
    if forced_next and forced_next in MUTATION_ARC:
        if "strategy" in forced_next: stats['mutated_strain_active'] = True
        return forced_next, MUTATION_ARC[forced_next]

    # 3. HANDLE MUTATION ARC LOGIC
    if stats.get('mutated_strain_active'):
        # Get all mutation keys (mut_p1 to mut_p20)
        mut_keys = [k for k in MUTATION_ARC.keys() if k.startswith("mut_p")]
        
        # Count how many we have played THIS RUN
        played_in_arc = [k for k in used_events if k in mut_keys]
        
        # ARC LENGTH CHECK: Trigger Finale after 8 events
        if len(played_in_arc) >= 8:
            stats['mutated_strain_active'] = False
            return "mut_finale_win", MUTATION_ARC["mut_finale_win"]
        
        # Pick a random mutation event that hasn't been played yet
        available_muts = [k for k in mut_keys if k not in used_events]
        
        if available_muts:
            eid = random.choice(available_muts)
            return eid, MUTATION_ARC[eid]
        else:
            # Fallback if we somehow run out of mutation events
            return "mut_finale_win", MUTATION_ARC["mut_finale_win"]

    # 4. TRIGGER MUTATION ARC START
    # Can only happen after Day 15, if not played yet, 30% chance per turn
    if stats['day'] > 15 and "mut_start" not in used_events and random.random() < 0.3:
        return "mut_start", MUTATION_ARC["mut_start"]

    # 5. MAIN STORY EVENTS (Fixed Days)
    day = stats.get('day', 1)
    if day in STORY_ARCS: return f"day_{day}", STORY_ARCS[day]

    # 6. RANDOM POOL LOGIC (Strict No Repetition)
    # Get all events that have NOT been used yet
    all_available = [k for k in RANDOM_POOL.keys() if k not in used_events]
    
    # FILTER: If Day <= 18, BLOCK procedural events (ids starting with 'proc_')
    if day <= 18:
        filtered_available = [k for k in all_available if not k.startswith("proc_")]
    else:
        filtered_available = all_available

    # SELECTION
    if filtered_available: 
        eid = random.choice(filtered_available)
        return eid, RANDOM_POOL[eid]
    
    # Fallback: If ran out of hand-written pre-18, allow procedural early
    if all_available:
        eid = random.choice(all_available)
        return eid, RANDOM_POOL[eid]

    # Ultimate Fallback (Should never happen with 150+ events)
    return "quiet_day", {"text": "STATUS: QUIET DAY\nNo major incidents reported.", "choices": [{"text": "Rest.", "mods": {"trust": 1}}]}
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
