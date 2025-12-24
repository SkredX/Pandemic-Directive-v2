"use client";
import { useState, useEffect, useRef } from 'react';

// --- TEXT CONTENT ---
const INTRO_PART_1 = "Welcome to the command group.\n\nOur nation has just noted a novel infection.\n\nYou are recruited to guide the decision makers.\n\n";
const INTRO_PART_2 = "Stay prepared to lead from the shadows.";

export default function Home() {
  // --- STATES ---
  const [booted, setBooted] = useState(false);       // Has user clicked "BOOT SYSTEM"?
  const [introStep, setIntroStep] = useState(0);     // 0=Typing, 1=Done
  const [gameStarted, setGameStarted] = useState(false);
  const [loading, setLoading] = useState(false);
  
  // Game Data
  const [stats, setStats] = useState({ pop: 100, trust: 70, eco: 80, inf: 5, cure: 0 });
  const [terminalLogs, setTerminalLogs] = useState([]); 
  const [currentEventId, setCurrentEventId] = useState(null);
  const [input, setInput] = useState("");

  // Refs
  const terminalRef = useRef(null);
  const audioRef = useRef({ bgm: null, type: null });

  // --- AUDIO SETUP ---
  useEffect(() => {
    // Grab audio elements
    audioRef.current.bgm = document.getElementById('bgm');
    audioRef.current.type = document.getElementById('sfx-typewriter');
  }, []);

  const playTypeSound = () => {
    const sfx = audioRef.current.type;
    if (sfx) {
       // Reset and play to handle rapid typing
       sfx.currentTime = 0;
       sfx.play().catch(() => {}); 
    }
  };

  // --- BOOT SEQUENCE (Required for Audio Policy) ---
  const bootSystem = () => {
    setBooted(true);
    // Start Intro Typing
    startIntroTyping();
  };

  // --- INTRO TYPING LOGIC ---
  const [introTextDisplay, setIntroTextDisplay] = useState("");
  
  const startIntroTyping = () => {
    let fullText = INTRO_PART_1 + INTRO_PART_2;
    let i = 0;
    
    const interval = setInterval(() => {
      setIntroTextDisplay(fullText.substring(0, i+1));
      playTypeSound(); // Play sound per character
      i++;
      
      if (i === fullText.length) {
        clearInterval(interval);
        setIntroStep(1); // Show Initialize Button
      }
    }, 40); // Typing speed
  };

  const startGame = () => {
    setGameStarted(true);
    // Start BGM
    if (audioRef.current.bgm) {
        audioRef.current.bgm.volume = 0.4;
        audioRef.current.bgm.play().catch(() => {});
    }
    // Fetch Day 1
    processTurn(null, true);
  };

  // --- GAMEPLAY ENGINE ---
  const processTurn = async (choiceIndex = null, isInit = false) => {
    if (loading) return;
    setLoading(true);

    // 1. Log User Selection (Stable visual)
    if (choiceIndex !== null) {
      // Find the text of the choice they made from the previous log
      // (This logic assumes the last log entry contained the choices)
      // Since we clear choices, we just log the action generic or use state if stored
      setTerminalLogs(prev => [...prev, { text: `>> COMMAND CONFIRMED: OPTION ${choiceIndex + 1}`, type: 'instant' }]);
    }

    try {
      // 2. API Call
      const res = await fetch('/api/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            stats,
            choice_index: choiceIndex,
            last_event_id: currentEventId,
            is_init: isInit
        }),
      });

      if (!res.ok) throw new Error("Connection Failed");
      const data = await res.json();

      // 3. Update State
      setStats(data.stats);
      setCurrentEventId(data.event_id);
      
      // 4. Update Logs with new Narrative AND Choices
      // We bundle narrative + choices into one log object to keep them stable
      setTerminalLogs(prev => [
        ...prev, 
        { 
            text: data.narrative, 
            choices: data.choices, // Store choices inside the log entry
            type: 'typewriter' 
        }
      ]);

    } catch (error) {
      setTerminalLogs(prev => [...prev, { text: "ERROR: MAINFRAME DISCONNECTED.", type: 'instant' }]);
    }
    setLoading(false);
  };

  const handleInput = () => {
    // Get the active choices from the *last* log entry
    const lastLog = terminalLogs[terminalLogs.length - 1];
    if (!lastLog || !lastLog.choices) return;

    const val = parseInt(input);
    if (!isNaN(val) && val > 0 && val <= lastLog.choices.length) {
        processTurn(val - 1); // 0-based index
        setInput("");
    } else {
        // Invalid input visual feedback
        setInput("ERR");
        setTimeout(() => setInput(""), 500);
    }
  };

  // --- RENDER HELPERS ---
  
  // Custom Component to handle Typing Effect inside Terminal
  const TerminalEntry = ({ entry, isLast }) => {
    const [displayedText, setDisplayedText] = useState(entry.type === 'typewriter' && isLast ? "" : entry.text);
    const hasRun = useRef(false);

    useEffect(() => {
        if (entry.type === 'instant' || (entry.type === 'typewriter' && !isLast)) {
            setDisplayedText(entry.text);
            return;
        }
        if (hasRun.current) return;
        hasRun.current = true;

        let i = 0;
        const interval = setInterval(() => {
            setDisplayedText(entry.text.substring(0, i+1));
            playTypeSound();
            terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
            i++;
            if (i === entry.text.length) clearInterval(interval);
        }, 15);
        return () => clearInterval(interval);
    }, [entry, isLast]);

    return (
        <div style={{marginBottom: '25px', borderBottom: '1px dashed #333', paddingBottom: '15px'}}>
            <div style={{whiteSpace: 'pre-wrap', marginBottom: '15px'}}>{displayedText}</div>
            
            {/* Stable Choice List: Only show if this is the latest log */}
            {entry.choices && (
                <div style={{color: '#fff'}}>
                   {entry.choices.map((c, idx) => (
                       <div key={idx} style={{marginBottom: '8px'}}>
                           <span style={{color: '#4af626'}}>[{idx+1}]</span> {c.text}
                       </div>
                   ))} 
                </div>
            )}
        </div>
    );
  };

  // --- RENDER MAIN ---
  return (
    <main className="container">
      
      {/* 1. BOOT & INTRO SCREEN */}
      {!gameStarted && (
        <div style={{
            position: 'fixed', top: 0, left: 0, width: '100%', height: '100%',
            background: '#000', zIndex: 5000, display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center'
        }}>
            {!booted ? (
               <button onClick={bootSystem} className="glow-btn" style={{
                   background: 'transparent', border: '2px solid #4af626', color: '#4af626',
                   padding: '20px 40px', fontSize: '1.5rem', cursor: 'pointer', letterSpacing: '2px'
               }}>
                   BOOT SYSTEM_
               </button>
            ) : (
                <>
                    <div className="intro-container">
                        {/* Logic to highlight the second part */}
                        {introTextDisplay.includes(INTRO_PART_2) ? (
                            <>
                                {INTRO_PART_1}
                                <span className="intro-highlight cursor">{INTRO_PART_2}</span>
                            </>
                        ) : (
                             <span className="cursor">{introTextDisplay}</span>
                        )}
                    </div>

                    <button 
                        onClick={startGame}
                        style={{
                            opacity: introStep === 1 ? 1 : 0, 
                            pointerEvents: introStep === 1 ? 'auto' : 'none',
                            marginTop: '40px', background: '#4af626', color: '#000',
                            padding: '15px 50px', fontSize: '1.2rem', fontWeight: 'bold',
                            border: 'none', cursor: 'pointer', transition: 'opacity 1s',
                            boxShadow: '0 0 20px #4af626'
                        }}
                    >
                        INITIALIZE PROTOCOLS
                    </button>
                </>
            )}
        </div>
      )}

      {/* 2. GAME HUD */}
      <div className="system-header">
        <span>SYS.OP.2025</span>
        <span style={{animation: 'blink 2s infinite'}}>CONNECTED</span>
      </div>

      {/* 3. TERMINAL LOGS */}
      <div className="terminal" ref={terminalRef}>
        {terminalLogs.map((log, i) => (
            <TerminalEntry key={i} entry={log} isLast={i === terminalLogs.length - 1} />
        ))}
        {loading && <div className="cursor">CALCULATING PROJECTIONS...</div>}
      </div>

      {/* 4. INPUT */}
      <div className="input-row">
        <input 
          type="number" 
          placeholder=">> ENTER OPTION ID" 
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleInput()}
          disabled={loading || !gameStarted}
          autoFocus
        />
        <button onClick={handleInput} disabled={loading || !gameStarted}>
          EXECUTE
        </button>
      </div>

      {/* 5. STATS (GLOWING) */}
      <footer>
        <div className="stat-box">POP:<span className="stat-val">{stats.pop}%</span></div>
        <div className="stat-box">TRUST:<span className="stat-val">{stats.trust}%</span></div>
        <div className="stat-box">INF:<span className="stat-val" style={{color: stats.inf > 50 ? 'red' : '#fff'}}>{stats.inf}%</span></div>
        <div className="stat-box">ECO:<span className="stat-val">{stats.eco}%</span></div>
        <div className="stat-box">CURE:<span className="stat-val">{stats.cure || 0}%</span></div>
      </footer>
      
      {/* AUDIO ELEMENTS */}
      <audio id="bgm" loop><source src="/Audio/bgm.mp3" type="audio/mpeg" /></audio>
      <audio id="sfx-typewriter"><source src="/Audio/typewriter.mp3" type="audio/mpeg" /></audio>
    </main>
  );
}
