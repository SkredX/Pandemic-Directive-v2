"use client";
import { useState, useEffect, useRef } from 'react';

// --- VISUAL & AUDIO CONSTANTS ---
const INTRO_TEXT = "Welcome to the command group.\n\nOur nation has just noted a novel infection.\n\nYou are recruited to guide the decision makers.\n\nStay prepared to lead from the shadows.";

export default function Home() {
  // --- STATE MANAGEMENT ---
  const [gameStarted, setGameStarted] = useState(false);
  const [introDone, setIntroDone] = useState(false);
  const [loading, setLoading] = useState(false);
  
  // Game Data
  const [stats, setStats] = useState({ pop: 100, trust: 70, eco: 80, inf: 5, load: 10 });
  const [terminalLogs, setTerminalLogs] = useState([]); 
  const [currentChoices, setCurrentChoices] = useState([]);
  const [currentEventId, setCurrentEventId] = useState(null); // NEW: Track Event ID
  const [input, setInput] = useState("");

  const terminalRef = useRef(null);
  const audioRef = useRef({ bgm: null, type: null });

  // --- AUDIO SETUP ---
  useEffect(() => {
    audioRef.current.bgm = document.getElementById('bgm');
    audioRef.current.type = document.getElementById('sfx-typewriter');
  }, []);

  const playTypeSound = () => {
    if (audioRef.current.type) {
      audioRef.current.type.currentTime = 0;
      audioRef.current.type.play().catch(() => {});
    }
  };

  // --- TYPEWRITER EFFECT ---
  const TypewriterLog = ({ text, onComplete }) => {
    const [display, setDisplay] = useState("");
    useEffect(() => {
      let i = 0;
      playTypeSound();
      const interval = setInterval(() => {
        setDisplay(text.substring(0, i + 1));
        i++;
        if (i === text.length) {
          clearInterval(interval);
          if (onComplete) onComplete();
        }
        if (terminalRef.current) terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
      }, 10); // Faster typing for better UX
      return () => clearInterval(interval);
    }, [text]);
    return <div style={{marginBottom: '15px', whiteSpace: 'pre-wrap'}}>{display}</div>;
  };

  // --- INTRO SEQUENCE ---
  useEffect(() => {
    let i = 0;
    const interval = setInterval(() => {
        const el = document.getElementById('intro-text');
        if (el) {
            el.innerText = INTRO_TEXT.substring(0, i);
            i++;
            if (i > INTRO_TEXT.length) {
                clearInterval(interval);
                setIntroDone(true);
            }
        }
    }, 30);
    return () => clearInterval(interval);
  }, []);

  const initializeGame = () => {
    if (audioRef.current.bgm) {
        audioRef.current.bgm.volume = 0.5;
        audioRef.current.bgm.play().catch(e => console.log("Audio blocked"));
    }
    setGameStarted(true);
    processTurn(null, true); 
  };

  // --- GAME LOGIC BRIDGE ---
  const processTurn = async (choiceIndex = null, isInit = false) => {
    if (loading) return;
    setLoading(true);

    if (choiceIndex !== null) {
        const choiceText = currentChoices[choiceIndex]?.text || "UNKNOWN COMMAND";
        setTerminalLogs(prev => [...prev, { text: `>> ACTION: ${choiceText}`, type: 'instant' }]);
    }

    try {
      const payload = {
        stats: stats,
        choice_index: choiceIndex, // Which button they clicked (0, 1, 2...)
        last_event_id: currentEventId, // NEW: Tell server what we just played
        is_init: isInit
      };

      const res = await fetch('/api/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) throw new Error("UPLINK FAILED");
      const data = await res.json();

      setStats(data.stats);
      setCurrentChoices(data.choices);
      setCurrentEventId(data.event_id); // NEW: Store the new event ID
      
      setTerminalLogs(prev => [...prev, { text: data.narrative, type: 'typewriter' }]);

    } catch (error) {
      setTerminalLogs(prev => [...prev, { text: "ERROR: CONNECTION TO MAINFRAME LOST.", type: 'instant' }]);
    }
    setLoading(false);
  };

  // --- INPUT HANDLING ---
  const handleInput = () => {
    const val = parseInt(input);
    if (!isNaN(val) && val > 0 && val <= currentChoices.length) {
        processTurn(val - 1);
        setInput("");
    } else {
        setTerminalLogs(prev => [...prev, { text: ">> INVALID PARAMETER", type: 'instant' }]);
        setInput("");
    }
  };

  return (
    <main className={`container ${stats.inf > 70 ? 'critical' : ''}`}>
      {!gameStarted && (
        <div id="loading-overlay" style={{
            position: 'fixed', top: 0, left: 0, width: '100%', height: '100%',
            background: '#000', zIndex: 5000, display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center'
        }}>
            <div id="intro-text" style={{maxWidth: '600px', whiteSpace: 'pre-wrap', color: '#ccc', marginBottom: '30px', minHeight: '150px'}}></div>
            <button 
                id="enter-btn"
                onClick={initializeGame}
                style={{
                    opacity: introDone ? 1 : 0, 
                    pointerEvents: introDone ? 'auto' : 'none',
                    background: 'transparent', color: '#4af626', border: '2px solid #4af626',
                    padding: '20px 60px', fontSize: '1.5rem', cursor: 'pointer', transition: 'opacity 1s'
                }}
            >
                INITIALIZE PROTOCOLS
            </button>
        </div>
      )}

      <div className="system-header">
        <span>SYS.OP.2025</span>
        <span className="blink">ONLINE</span>
      </div>

      <div className="terminal" ref={terminalRef}>
        {terminalLogs.map((log, i) => (
            log.type === 'typewriter' && i === terminalLogs.length - 1 
            ? <TypewriterLog key={i} text={log.text} />
            : <div key={i} style={{marginBottom: '15px', whiteSpace: 'pre-wrap'}}>{log.text}</div>
        ))}
        {loading && <div className="blink">CALCULATING PROJECTIONS...</div>}
        
        {/* Dynamic Choice List (Handles 2, 3, or 4 options) */}
        {!loading && currentChoices.length > 0 && (
            <div style={{marginTop: '20px', borderTop: '1px dashed #333', paddingTop: '10px'}}>
                {currentChoices.map((c, i) => (
                    <div key={i} style={{marginBottom: '5px'}}>[{i+1}] {c.text}</div>
                ))}
            </div>
        )}
      </div>

      <div className="input-row">
        <input 
          type="number" 
          placeholder=">> AWAITING INTEGER INPUT" 
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleInput()}
          disabled={loading || currentChoices.length === 0}
        />
        <button onClick={handleInput} disabled={loading || currentChoices.length === 0}>
          EXECUTE
        </button>
      </div>

      <footer>
        <p>POP: {stats.pop}% | TRUST: {stats.trust}% | INF: {stats.inf}% | ECO: {stats.eco}% | CURE: {stats.cure || 0}%</p>
      </footer>
      
      <audio id="bgm" loop><source src="/Audio/bgm.mp3" type="audio/mpeg" /></audio>
      <audio id="sfx-typewriter"><source src="/Audio/typewriter.mp3" type="audio/mpeg" /></audio>
    </main>
  );
}
