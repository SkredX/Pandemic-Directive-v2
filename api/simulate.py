from http.server import BaseHTTPRequestHandler
import json
import numpy as np

# --- 1. THE GAME LOGIC (Previously JS, now Python) ---
def run_simulation(state):
    # Extract variables for easier reading
    infection = state.get('inf', 0)
    trust = state.get('trust', 0)
    economy = state.get('eco', 0)
    load = state.get('load', 0)
    
    # --- LOGISTIC GROWTH MODEL ---
    # Python allows us to use numpy for more complex curves if we want later
    spread_rate = 0.15
    
    # Apply Modifiers
    if trust < 40: spread_rate += 0.06
    if load > 90: spread_rate += 0.05
    
    # Calculate Growth: Rate * Inf * (1 - Inf)
    growth = spread_rate * infection * (1.0 - infection)
    noise = np.random.normal(0, 0.01) # Gaussian noise (bell curve)
    
    new_infection = infection + growth + noise
    
    # Snap to limits (0 to 100 range)
    new_infection = max(0, min(100, new_infection))
    
    # --- HEALTHCARE LAG MODEL ---
    # Healthcare load rubber-bands towards Infection * 1.3
    target_load = new_infection * 1.3
    new_load = load + (target_load - load) * 0.25
    
    # --- ECONOMY DECAY ---
    eco_decay = 0.5
    if new_infection > 30: eco_decay += 2.0
    new_economy = economy - eco_decay
    
    # --- TRUST FALL ---
    new_trust = trust
    if new_economy < 30: new_trust -= 2
    if new_infection > 50: new_trust -= 3

    return {
        "inf": round(new_infection, 1),
        "eco": round(new_economy, 1),
        "trust": round(new_trust, 1),
        "load": round(new_load, 1),
        "message": generate_narrative(new_infection, new_trust)
    }

def generate_narrative(inf, trust):
    # Simple logic-based narrative for now
    if inf > 80: return "CRITICAL: HOSPITALS COLLAPSING."
    if trust < 20: return "WARNING: CIVIL UNREST IMMINENT."
    if inf < 10: return "STATUS: CONTAINMENT STABLE."
    return "STATUS: AWAITING FURTHER ORDERS."

# --- 2. THE VERCEL HANDLER ---
class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # Read the incoming JSON body
        content_len = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_len)
        
        try:
            current_state = json.loads(body)
            # Run the Python Brain
            next_state = run_simulation(current_state)
            
            # Send response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(next_state).encode('utf-8'))
            
        except Exception as e:
            self.send_response(500)
            self.wfile.write(str(e).encode('utf-8'))
