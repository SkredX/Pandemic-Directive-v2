from http.server import BaseHTTPRequestHandler
import json
import random
import numpy as np
import os
import sys

# ==========================================
# 0. DIAGNOSTIC CONFIG
# ==========================================
# We wrap imports to catch "Missing Package" errors immediately
DB_STATUS = "Checking..."
try:
    from pymongo import MongoClient
    import dns.resolver # Check for dnspython
    DB_STATUS = "Drivers Installed"
except ImportError as e:
    DB_STATUS = f"MISSING DRIVER: {str(e)}"

# ==========================================
# 1. CORE LOGIC (Simplified for Stability)
# ==========================================
def calculate_score(stats, ending_type):
    score = (stats['day'] * 100) + (stats['pop'] * 50) + (stats['trust'] * 20)
    return int(score)

# ==========================================
# 2. HANDLER (CRASH-PROOF MODE)
# ==========================================
class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            # 1. READ DATA
            l = int(self.headers.get('Content-Length', 0))
            if l == 0: raise ValueError("Empty request body")
            data = json.loads(self.rfile.read(l))
            
            # 2. TEST DATABASE CONNECTION (Explicit Test)
            client = None
            db_error = None
            
            if 'MONGODB_URI' not in os.environ:
                db_error = "Env Var MONGODB_URI is missing from Vercel."
            elif "MISSING" in DB_STATUS:
                db_error = DB_STATUS
            else:
                try:
                    # Low timeout to prevent hanging
                    client = MongoClient(os.environ['MONGODB_URI'], serverSelectionTimeoutMS=2000)
                    # Force a "ping" to verify connection actually works
                    client.admin.command('ping')
                    db = client['zero_hour_game']
                    # Verify collections exist/can be touched
                    count = db.leaderboard.count_documents({})
                except Exception as e:
                    db_error = f"Connection Refused: {str(e)}"

            # 3. ROUTE HANDLING
            action = data.get('action')
            
            # --- LEADERBOARD ---
            if action == 'get_leaderboard':
                if db_error:
                    # Return error as a "fake" leaderboard entry so user sees it
                    self.send_json({"leaderboard": [{"name": "SYSTEM ERROR", "score": 0, "days": 0, "user_id": "err"}]})
                else:
                    scores = list(db.leaderboard.find({}, {'_id': 0}).sort("score", -1).limit(10))
                    self.send_json({"leaderboard": scores})
                return

            # --- SUBMIT SCORE ---
            if action == 'submit_score':
                if db_error:
                    self.send_json({"status": "error", "message": db_error})
                else:
                    uid = data.get('user_id'); name = data.get('name')
                    s = data.get('stats'); ending = data.get('ending')
                    score = calculate_score(s, ending)
                    db.leaderboard.update_one(
                        {"user_id": uid}, 
                        {"$set": {"name": name, "score": score, "days": s['day'], "ending": ending}}, 
                        upsert=True
                    )
                    self.send_json({"status": "saved", "score": score})
                return

            # --- GAME TURN (The part that was crashing) ---
            stats = data.get('stats', {})
            choice_idx = data.get('choice_index')
            is_init = data.get('is_init', False)

            narrative = ""
            
            # APPEND DB ERROR TO TEXT (So you can see it!)
            if db_error:
                narrative += f"[WARNING: DATABASE OFFLINE - {db_error}]\n\n"

            # Logic Placeholder (Keep it simple to verify connection first)
            new_stats = stats.copy()
            if is_init:
                new_stats = {"day": 1, "pop": 100, "trust": 70, "eco": 80, "inf": 5, "cure": 0}
                narrative += "DAY 1: PATIENT ZERO\nSurveillance satellites detected a bio-anomaly."
                choices = [{"text": "Blockade Sector 4.", "mods": {"trust": -5}}, {"text": "Send Medical Team.", "mods": {"eco": -2}}]
            else:
                new_stats['day'] += 1
                narrative += f"DAY {new_stats['day']}: SITUATION CRITICAL\nReports are coming in."
                choices = [{"text": "Continue Operations.", "mods": {}}, {"text": "Emergency Meeting.", "mods": {}}]

            self.send_json({
                "stats": new_stats, 
                "narrative": narrative, 
                "choices": choices, 
                "event_id": "debug_mode", 
                "used_events": []
            })

        except Exception as e:
            # --- THE SAFETY NET ---
            # If ANYTHING crashes, we return a 200 OK with the error message
            # so the Frontend displays it instead of "Disconnected".
            error_response = {
                "stats": {"day": 0, "pop": 0, "trust": 0, "eco": 0, "inf": 0},
                "narrative": f"CRITICAL SYSTEM FAILURE:\n{str(e)}\n\n(Please copy this error message)",
                "choices": [{"text": "RETRY CONNECTION", "mods": {}}],
                "event_id": "error",
                "used_events": []
            }
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(error_response).encode())

    def send_json(self, d):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(d).encode())
