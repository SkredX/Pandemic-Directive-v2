# Pandemic Directive: Zero Hour

> Status: Active  
> Version: 2.0 (Redux)  
> Stack: Next.js + Python (Serverless) + MongoDB

Pandemic Directive: Zero Hour is a high-fidelity strategic simulation game that places players in the role of a crisis commander during a global biological emergency. Unlike standard choose-your-own-adventure games, this project uses a probabilistic simulation engine combined with an adaptive AI decision matrix to generate dynamic outcomes.

---

## Project Architecture

The project follows a hybrid serverless architecture. The frontend is built with Next.js, while the backend simulation logic is implemented in Python using Vercel serverless functions. MongoDB is used for persistence and analytics.

```text
.
├── api/
│   └── simulate.py         # Game logic, probability math, and MongoDB integration
├── src/
│   ├── app/
│   │   ├── globals.css     # CRT styling, scanlines, and animations
│   │   ├── layout.js       # Root layout and analytics integration
│   │   └── page.js         # React frontend with terminal UI
├── public/
│   └── Audio/
│       ├── bgm.mp3         # Ambient background audio
│       └── typewriter.mp3  # Terminal sound effects
├── requirements.txt        # Python dependencies
├── next.config.js          # Next.js configuration
└── package.json            # Node.js dependencies
```

---

## The Mathematics of Chaos (Version 2.0)

Version 1.0 relied on static conditional logic. Version 2.0 introduces a stochastic simulation model in which the game state evolves continuously based on interacting variables rather than fixed narrative paths.

---

### Infection Growth Model (R_eff)

Virus transmission is calculated using a modified epidemiological formula based on the effective reproduction number:

R_eff = R_0 × (0.5 + 0.5 × Eco) × (1 − α × Compliance)

Where:
- R_0 is the base viral reproduction rate (initially 1.5, increasing up to 2.8 during mutation events)
- Eco represents economic activity (higher values imply greater mobility and spread)
- Compliance is derived from public trust (Trust / 100)
- α is the mitigation effectiveness coefficient

---

### Probabilistic Mortality Model

Mortality is computed as a probability influenced by infection load and healthcare system capacity:

Mortality = Base Rate + Overload Penalty

If:

Infection × 1.2 > (40 + Eco × 0.2)

the healthcare system collapses, triggering a 2.0 percent daily population loss.

---

### Virus Brain (Adaptive AI Logic)

Every five in-game days, the system evaluates an AI decision matrix defined in `virus_brain.json` or a fallback rule set.

- If Cure exceeds 30 percent, the virus may mutate, increasing R_0
- If Trust exceeds 80 percent, the virus may enter dormancy, reducing short-term pressure before resurging later

This creates a rubber-band effect, increasing difficulty as the player approaches success.

---

## Version Comparison

| Feature | Version 1.0 | Version 2.0 |
|------|-------------|-------------|
| Core Logic | Static JSON tree | Python-based stochastic simulation |
| Event System | 12 linear scenarios | 35+ randomized events with mutation arcs |
| Persistence | None | MongoDB cloud saves |
| Social Features | Single player | Global leaderboards and statistics |
| Visuals | Basic HTML | CRT shaders and glitch effects |

---

## How to Play

1. Boot the system by clicking the terminal interface
2. Review the daily intelligence briefing
3. Execute commands by entering the protocol number and confirming
4. Monitor critical metrics:
   - Population: Below 10 percent results in societal collapse
   - Trust: Below 10 percent triggers a military coup
   - Infection: 100 percent results in human extinction
   - Economy: Required to fund research and infrastructure
   - Cure: Reach 95 percent to achieve victory
5. Submit your record to the Global Commander Leaderboard at the end of a run to save your stats and view the top players

---

The Python backend builds automatically using Vercel's serverless runtime.

---

"The death of one man is a tragedy.
The death of millions is a statistic."
