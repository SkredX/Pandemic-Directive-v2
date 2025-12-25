"use client";
import { useState, useEffect, useRef, memo } from 'react';

const INTRO_PART_1 = "Welcome to the command group.\n\nOur nation has just noted a novel infection.\n\nYou are recruited to guide the decision makers.\n\n";
const INTRO_PART_2 = "Stay prepared to lead from the shadows.";

// --- 1. EXTERNAL COMPONENT (STABLE) ---
const TerminalEntry = memo(({ entry, isLast, onScroll }) => {
    const [displayedText, setDisplayedText] = useState(entry.type === 'typewriter' && isLast ? "" : entry.text);
    const hasRun = useRef(false);

    useEffect(() => {
        // Instant render for old logs or 'instant' type logs
        if (entry.type === 'instant' || (entry.type === 'typewriter' && !isLast)) {
            setDisplayedText(entry.text);
            return;
        }

        if (hasRun.current) return;
        hasRun.current = true;

        // --- AUDIO START ---
        const sfx = document.getElementById('sfx-typewriter');
        if (sfx) {
            sfx.currentTime = 0;
            sfx.loop = true; // Loop the sound smoothly
            sfx.play().catch(() => {});
        }

        let i = 0;
        const interval = setInterval(() => {
            setDisplayedText(entry.text.substring(0, i+1));
            onScroll(); 
            i++;
            
            // --- AUDIO STOP (When Finished) ---
            if (i === entry.text.length) {
                clearInterval(interval);
                if (sfx) sfx.pause();
            }
        }, 15); // Speed of typing

        // Cleanup if component unmounts mid-type
        return () => {
            clearInterval(interval);
            if (sfx) sfx.pause();
        };
    }, [entry, isLast, onScroll]);

    const showChoices = entry.choices && (entry.type !== 'typewriter' || displayedText.length === entry.text.length);

    return (
        <div style={{marginBottom: '25px', borderBottom: '1px dashed #333', paddingBottom: '15px'}}>
            <div style={{whiteSpace: 'pre-wrap', marginBottom: '15px'}}>{displayedText}</div>
            
            {showChoices && (
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
});

TerminalEntry.displayName = "TerminalEntry";


// --- 2. MAIN GAME COMPONENT ---
export default function Home() {
  const [booted, setBooted] = useState(false);
  const [introStep, setIntroStep] = useState(0);
  const [gameStarted, setGameStarted] = useState(false);
  const [loading, setLoading] = useState(false);
  
  // Game State
  const [stats, setStats] = useState({ day: 1, pop: 100, trust: 70, eco: 80, inf: 5, cure: 0 });
  const [terminalLogs, setTerminalLogs] = useState([]); 
  const [currentEventId, setCurrentEventId] = useState(null);
  const [usedEvents, setUsedEvents] = useState([]); 
  const [activeChoices, setActiveChoices] = useState([]); 
  
  const [input, setInput] = useState("");
  const terminalRef = useRef(null);
  const audioRef = useRef({ bgm: null });

  const handleScroll = () => {
    if (terminalRef.current) {
        terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  };

  useEffect(() => {
    audioRef.current.bgm = document.getElementById('bgm');
  }, []);

  const bootSystem = () => {
    setBooted(true);
    startIntroTyping();
  };

  const [introTextDisplay, setIntroTextDisplay] = useState("");
  
  const startIntroTyping = () => {
    let fullText = INTRO_PART_1 + INTRO_PART_2;
    let i = 0;
    
    // --- INTRO AUDIO START ---
    const sfx = document.getElementById('sfx-typewriter');
    if (sfx) { sfx.currentTime = 0; sfx.loop = true; sfx.play().catch(() => {}); }

    const interval = setInterval(() => {
      setIntroTextDisplay(fullText.substring(0, i+1));
      i++;
      
      if (i === fullText.length) { 
          clearInterval(interval); 
          setIntroStep(1); 
          // --- INTRO AUDIO STOP ---
          if (sfx) sfx.pause();
      }
    }, 40);
  };

  const startGame = () => {
    setGameStarted(true);
    if (audioRef.current.bgm) { audioRef.current.bgm.volume = 0.4; audioRef.current.bgm.play().catch(() => {}); }
    processTurn(null, true);
  };

  // --- ENGINE ---
  const processTurn = async (choiceIndex = null, isInit = false) => {
    if (loading) return;
    setLoading(true);

    if (choiceIndex !== null) {
        setTerminalLogs(prev => [...prev, { text: `>> OPTION ${choiceIndex + 1} SELECTED`, type: 'instant' }]);
        setActiveChoices([]); 
    }

    try {
      const res = await fetch('/api/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            stats,
            choice_index: choiceIndex,
            last_event_id: currentEventId,
            used_events: usedEvents,
            is_init: isInit
        }),
      });

      if (!res.ok) throw new Error("Connection Failed");
      const data = await res.json();

      setStats(data.stats);
      setCurrentEventId(data.event_id);
      setUsedEvents(data.used_events);
      setActiveChoices(data.choices);
      
      setTerminalLogs(prev => [
        ...prev, 
        { 
            text: data.narrative, 
            choices: data.choices, 
            type: 'typewriter' 
        }
      ]);

    } catch (error) {
      setTerminalLogs(prev => [...prev, { text: "ERROR: MAINFRAME DISCONNECTED.", type: 'instant' }]);
    }
    setLoading(false);
  };

  const handleInput = () => {
    if (activeChoices.length === 0) return;

    const val = parseInt(input);
    if (!isNaN(val) && val > 0 && val <= activeChoices.length) {
        processTurn(val - 1);
        setInput("");
    } else {
        setInput("ERR");
        setTimeout(() => setInput(""), 500);
    }
  };

  return (
    <main className={`container ${
      stats.inf > 70 || stats.pop < 40 || stats.trust < 20 ? 'critical' : ''
  }`}>
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
                        {introTextDisplay.includes(INTRO_PART_2) ? (
                            <>
                                {INTRO_PART_1}
                                <span className="intro-highlight cursor">{INTRO_PART_2}</span>
                            </>
                        ) : <span className="cursor">{introTextDisplay}</span>}
                    </div>
                    <button onClick={startGame} style={{
                        opacity: introStep === 1 ? 1 : 0, pointerEvents: introStep === 1 ? 'auto' : 'none',
                        marginTop: '40px', background: '#4af626', color: '#000', padding: '15px 50px',
                        fontSize: '1.2rem', fontWeight: 'bold', border: 'none', cursor: 'pointer',
                        transition: 'opacity 1s', boxShadow: '0 0 20px #4af626'
                    }}>INITIALIZE PROTOCOLS</button>
                </>
            )}
        </div>
      )}

      <div className="system-header">
        <span>SYS.OP.2025</span>
        <span style={{animation: 'blink 2s infinite'}}>CONNECTED // DAY {stats.day}</span>
      </div>

      <div className="terminal" ref={terminalRef}>
        {terminalLogs.map((log, i) => (
            <TerminalEntry 
                key={i} 
                entry={log} 
                isLast={i === terminalLogs.length - 1} 
                onScroll={handleScroll}
            />
        ))}
        {loading && <div className="cursor">CALCULATING...</div>}
      </div>

      <div className="input-row">
        <input 
          type="number" placeholder={activeChoices.length > 0 ? ">> ENTER OPTION ID" : ">> PROCESSING..."}
          value={input} onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleInput()}
          disabled={loading || activeChoices.length === 0}
          autoFocus
        />
        <button onClick={handleInput} disabled={loading || activeChoices.length === 0}>EXECUTE</button>
      </div>

      <footer>
        <div className="stat-box">POP:<span className="stat-val">{stats.pop}%</span></div>
        <div className="stat-box">TRUST:<span className="stat-val">{stats.trust}%</span></div>
        <div className="stat-box">INF:<span className="stat-val" style={{color: stats.inf > 50 ? 'red' : '#fff'}}>{stats.inf}%</span></div>
        <div className="stat-box">ECO:<span className="stat-val">{stats.eco}%</span></div>
        <div className="stat-box">CURE:<span className="stat-val">{stats.cure || 0}%</span></div>
      </footer>
      
      <audio id="bgm" loop><source src="/Audio/bgm.mp3" type="audio/mpeg" /></audio>
      <audio id="sfx-typewriter"><source src="/Audio/typewriter.mp3" type="audio/mpeg" /></audio>
    </main>
  );
}
