"use client";
import { useState, useEffect, useRef, memo } from 'react';

// --- HELPER: GENERATE UNIQUE ID ---
// Fixed to use 'let'/'const' to satisfy Linter
const generateUUID = () => {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
};

const INTRO_PART_1 = "Welcome to the command group.\n\nOur nation has just noted a novel infection.\n\nYou are recruited to guide the decision makers.\n\n";
const INTRO_PART_2 = "Stay prepared to lead from the shadows.";

// --- COMPONENT: TERMINAL ENTRY ---
const TerminalEntry = memo(({ entry, isLast, onScroll }) => {
    const [displayedText, setDisplayedText] = useState(entry.type === 'typewriter' && isLast ? "" : entry.text);
    const hasRun = useRef(false);

    useEffect(() => {
        if (entry.type === 'instant' || (entry.type === 'typewriter' && !isLast)) {
            setDisplayedText(entry.text);
            return;
        }

        if (hasRun.current) return;
        hasRun.current = true;

        const sfx = document.getElementById('sfx-typewriter');
        if (sfx) { sfx.currentTime = 0; sfx.loop = true; sfx.play().catch(() => {}); }

        let i = 0;
        const interval = setInterval(() => {
            setDisplayedText(entry.text.substring(0, i+1));
            onScroll(); 
            i++;
            
            if (i === entry.text.length) {
                clearInterval(interval);
                if (sfx) sfx.pause();
            }
        }, 15);

        return () => { clearInterval(interval); if (sfx) sfx.pause(); };
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


// --- MAIN COMPONENT ---
export default function Home() {
  const [booted, setBooted] = useState(false);
  const [loginStep, setLoginStep] = useState(true);
  const [commanderId, setCommanderId] = useState(null);
  const [introStep, setIntroStep] = useState(0);
  const [gameStarted, setGameStarted] = useState(false);
  const [gameEnded, setGameEnded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [playerName, setPlayerName] = useState("");
  const [leaderboard, setLeaderboard] = useState([]);

  const [stats, setStats] = useState({ day: 1, pop: 100, trust: 70, eco: 80, inf: 5, cure: 0 });
  const [terminalLogs, setTerminalLogs] = useState([]); 
  const [currentEventId, setCurrentEventId] = useState(null);
  const [usedEvents, setUsedEvents] = useState([]); 
  const [activeChoices, setActiveChoices] = useState([]); 
  const [input, setInput] = useState("");

  const terminalRef = useRef(null);
  const audioRef = useRef({ bgm: null });

  useEffect(() => {
    audioRef.current.bgm = document.getElementById('bgm');
    
    let storedId = localStorage.getItem('commander_id');
    if (!storedId) {
        storedId = generateUUID();
        localStorage.setItem('commander_id', storedId);
    }
    setCommanderId(storedId);
  }, []);

  const handleScroll = () => {
    if (terminalRef.current) {
        terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  };

  // Fixed: Removed unused 'mode' parameter to satisfy Linter
  const handleLogin = () => {
    setLoginStep(false);
  };

  const bootSystem = () => {
    setBooted(true);
    startIntroTyping();
  };

  const [introTextDisplay, setIntroTextDisplay] = useState("");
  const startIntroTyping = () => {
    let fullText = INTRO_PART_1 + INTRO_PART_2;
    let i = 0;
    const sfx = document.getElementById('sfx-typewriter');
    if (sfx) { sfx.currentTime = 0; sfx.loop = true; sfx.play().catch(() => {}); }

    const interval = setInterval(() => {
      setIntroTextDisplay(fullText.substring(0, i+1));
      i++;
      if (i === fullText.length) { 
          clearInterval(interval); 
          setIntroStep(1); 
          if (sfx) sfx.pause();
      }
    }, 40);
  };

  const startGame = () => {
    setGameStarted(true);
    if (audioRef.current.bgm) { audioRef.current.bgm.volume = 0.4; audioRef.current.bgm.play().catch(() => {}); }
    processTurn(null, true);
  };

  const processTurn = async (choiceIndex = null, isInit = false) => {
    if (loading) return;
    setLoading(true);

    if (choiceIndex !== null) {
        setTerminalLogs(prev => [...prev, { text: `>> OPTION ${choiceIndex + 1} SELECTED`, type: 'instant' }]);
        
        if (typeof window !== 'undefined' && window.gtag) {
            window.gtag('event', 'player_choice', {
                event_category: 'gameplay',
                event_label: `Day ${stats.day} - Option ${choiceIndex + 1}`,
                value: choiceIndex
            });
        }
        
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

      if (data.event_id && data.event_id.startsWith("ending_")) {
          setGameEnded(true);
          setStats(data.stats);
          setCurrentEventId(data.event_id);
      } else {
          setStats(data.stats);
          setCurrentEventId(data.event_id);
          setUsedEvents(data.used_events);
          setActiveChoices(data.choices);
      }
      
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

  const submitScore = async () => {
    if (!playerName.trim()) return;
    setLoading(true);
    
    try {
        await fetch('/api/simulate', {
            method: 'POST',
            body: JSON.stringify({ 
                action: 'submit_score', 
                user_id: commanderId, 
                name: playerName, 
                stats: stats, 
                ending: currentEventId 
            })
        });
        
        setTerminalLogs(prev => [...prev, { text: `>> COMMANDER REGISTERED: ${playerName}`, type: 'instant' }]);

        const res = await fetch('/api/simulate', {
            method: 'POST',
            body: JSON.stringify({ action: 'get_leaderboard' })
        });
        const data = await res.json();
        setLeaderboard(data.leaderboard);
        
    } catch (e) {
        setTerminalLogs(prev => [...prev, { text: "ERROR: COULD NOT REACH ARCHIVES.", type: 'instant' }]);
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
      
      {loginStep && !booted && (
         <div style={{
             position: 'fixed', top:0, left:0, width:'100%', height:'100%', 
             background:'#000', zIndex:6000, display:'flex', flexDirection:'column', 
             alignItems:'center', justifyContent:'center'
         }}>
            <h1 style={{color:'#4af626', marginBottom:'40px', letterSpacing:'4px', fontSize: '3rem'}}>ZERO HOUR</h1>
            
            <button onClick={() => handleLogin()} className="glow-btn" style={{
                marginBottom:'20px', padding:'15px 40px', background:'#4285F4', 
                color:'#fff', border:'none', fontSize:'1.2rem', cursor:'pointer', minWidth: '300px'
            }}>
                LOGIN WITH GOOGLE ID
            </button>
            
            <button onClick={() => handleLogin()} style={{
                padding:'15px 40px', background:'transparent', border:'2px solid #4af626', 
                color:'#4af626', fontSize:'1.2rem', cursor:'pointer', minWidth: '300px'
            }}>
                PLAY AS GUEST
            </button>
            
            <div style={{marginTop: '20px', color: '#666', fontFamily: 'monospace'}}>
                SECURE ID: {commanderId ? commanderId.substring(0,8) : '...'}
            </div>
         </div>
      )}

      {!loginStep && !gameStarted && (
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
                <div className="crt-turn-on"> 
                    <div className="intro-container">
                        {introTextDisplay.includes(INTRO_PART_2) ? (
                            <>
                                {INTRO_PART_1}
                                <span className="intro-highlight cursor">{INTRO_PART_2}</span>
                            </>
                        ) : <span className="cursor">{introTextDisplay}</span>}
                    </div>
                    <button onClick={startGame} style={{
                        opacity: introStep === 1 ? 1 : 0, 
                        pointerEvents: introStep === 1 ? 'auto' : 'none',
                        marginTop: '40px', background: '#4af626', color: '#000', 
                        padding: '15px 50px', fontSize: '1.2rem', fontWeight: 'bold', 
                        border: 'none', cursor: 'pointer', transition: 'opacity 1s', 
                        boxShadow: '0 0 20px #4af626'
                    }}>
                        INITIALIZE PROTOCOLS
                    </button>
                </div>
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
        
        {gameEnded && leaderboard.length > 0 && (
            <div style={{marginTop: '30px', borderTop: '2px solid #4af626', padding: '20px'}}>
                <h3 style={{color: '#4af626', textAlign: 'center', marginBottom: '20px'}}>TOP COMMANDERS</h3>
                <table style={{width: '100%', textAlign: 'left', color: '#fff', borderCollapse: 'collapse'}}>
                    <thead>
                        <tr style={{borderBottom: '1px solid #333'}}>
                            <th style={{padding: '10px'}}>RANK</th>
                            <th style={{padding: '10px'}}>NAME</th>
                            <th style={{padding: '10px'}}>DAYS</th>
                            <th style={{padding: '10px'}}>SCORE</th>
                        </tr>
                    </thead>
                    <tbody>
                        {leaderboard.map((entry, i) => (
                            <tr key={i} style={{
                                color: entry.user_id === commanderId ? '#ffff00' : '#ccc',
                                background: entry.user_id === commanderId ? 'rgba(255, 255, 0, 0.1)' : 'transparent'
                            }}>
                                <td style={{padding: '10px'}}>{i+1}</td>
                                <td style={{padding: '10px'}}>{entry.name}</td>
                                <td style={{padding: '10px'}}>{entry.days}</td>
                                <td style={{padding: '10px', fontWeight: 'bold'}}>{entry.score}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        )}
        
        {loading && <div className="cursor">PROCESSING...</div>}
      </div>

      <div className="input-row">
        {gameEnded && leaderboard.length === 0 ? (
            <>
                <input 
                    type="text" 
                    placeholder=">> ENTER COMMANDER NAME" 
                    value={playerName} 
                    onChange={(e) => setPlayerName(e.target.value)} 
                    onKeyDown={(e) => e.key === 'Enter' && submitScore()}
                    disabled={loading}
                    autoFocus 
                />
                <button onClick={submitScore} disabled={loading}>SUBMIT</button>
            </>
        ) : (
            <>
                <input 
                    type="number" 
                    placeholder={activeChoices.length > 0 ? ">> ENTER OPTION ID" : ">> PROCESSING..."} 
                    value={input} 
                    onChange={(e) => setInput(e.target.value)} 
                    onKeyDown={(e) => e.key === 'Enter' && handleInput()} 
                    disabled={loading || activeChoices.length === 0 || gameEnded} 
                    autoFocus 
                />
                <button onClick={handleInput} disabled={loading || activeChoices.length === 0 || gameEnded}>
                    EXECUTE
                </button>
            </>
        )}
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
