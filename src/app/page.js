"use client";
import { useState, useEffect, useRef } from 'react';

export default function Home() {
  const [input, setInput] = useState("");
  const [terminalLogs, setTerminalLogs] = useState([
    "SYS.OP.2025 INITIALIZED...", 
    "ESTABLISHING SECURE CONNECTION...",
    "AWAITING INPUT..."
  ]);
  
  const stats = { pop: 100, trust: 70, eco: 80, inf: 5, load: 10 };
  const terminalRef = useRef(null);

  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [terminalLogs]);

  const handleCommand = () => {
    if (!input) return;
    setTerminalLogs(prev => [...prev, `>> ${input}`, "COMMAND NOT RECOGNIZED (SYSTEM OFFLINE)"]);
    setInput("");
  };

  return (
    <main className="container">
      <div className="system-header">
        <span>SYS.OP.2025</span>
        <span className="blink">ONLINE</span>
      </div>

      <div className="terminal" ref={terminalRef}>
        {terminalLogs.map((line, i) => (
          <div key={i} style={{marginBottom: '10px', whiteSpace: 'pre-wrap'}}>{line}</div>
        ))}
      </div>

      <div className="input-row">
        <input 
          type="text" 
          placeholder=">> AWAITING COMMAND" 
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleCommand()}
        />
        <button onClick={handleCommand}>EXECUTE</button>
      </div>

      <footer>
        <p>POP: {stats.pop}% | TRUST: {stats.trust}% | INF: {stats.inf}%</p>
        <p>Decisions are final. History is watching.</p>
      </footer>
      
      {/* Audio Elements will check for file existence */}
      <audio id="bgm" loop>
         <source src="/Audio/bgm.mp3" type="audio/mpeg" />
      </audio>
    </main>
  );
}
