"use client";
import { useState, useEffect, useRef } from 'react';

export default function Home() {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  
  // Game State (Now managed by React, updated by Python)
  const [stats, setStats] = useState({ 
    pop: 100, trust: 70, eco: 80, inf: 5, load: 10 
  });
  
  const [terminalLogs, setTerminalLogs] = useState([
    "SYS.OP.2025 INITIALIZED...", 
    "CONNECTION TO PENTAGON SERVER: ESTABLISHED",
    "AWAITING INPUT..."
  ]);
  
  const terminalRef = useRef(null);

  // Auto-scroll terminal
  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [terminalLogs]);

  // --- THE BRIDGE TO PYTHON ---
  const processTurn = async () => {
    if (loading) return;
    setLoading(true);

    // 1. Add user command to log
    const command = input || "SKIP DAY";
    setTerminalLogs(prev => [...prev, `>> ${command}`, "PROCESSING SIMULATION..."]);
    setInput("");

    try {
      // 2. Send current stats to Python Backend
      const res = await fetch('/api/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(stats),
      });

      if (!res.ok) throw new Error("SERVER CONNECTION LOST");

      const newStats = await res.json();

      // 3. Update UI with Python's calculation
      setStats(prev => ({
        ...prev,
        inf: newStats.inf,
        eco: newStats.eco,
        trust: newStats.trust,
        load: newStats.load
      }));

      setTerminalLogs(prev => [...prev, newStats.message]);

    } catch (error) {
      setTerminalLogs(prev => [...prev, "ERROR: UPLINK FAILED."]);
    }
    
    setLoading(false);
  };

  return (
    <main className={`container ${stats.inf > 70 ? 'critical' : ''}`}>
      <div className="system-header">
        <span>SYS.OP.2025</span>
        <span className="blink">ONLINE</span>
      </div>

      <div className="terminal" ref={terminalRef}>
        {terminalLogs.map((line, i) => (
          <div key={i} style={{marginBottom: '10px', whiteSpace: 'pre-wrap'}}>{line}</div>
        ))}
        {loading && <div className="blink">CALCULATING PROJECTIONS...</div>}
      </div>

      <div className="input-row">
        <input 
          type="text" 
          placeholder=">> ENTER COMMAND" 
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && processTurn()}
          disabled={loading}
        />
        <button onClick={processTurn} disabled={loading}>
          {loading ? "..." : "EXECUTE"}
        </button>
      </div>

      <footer>
        <p>POP: {stats.pop}% | TRUST: {stats.trust}% | INF: {stats.inf}% | ECO: {stats.eco}%</p>
        <p>Decisions are final. History is watching.</p>
      </footer>
      
      <audio id="bgm" loop><source src="/Audio/bgm.mp3" type="audio/mpeg" /></audio>
    </main>
  );
}
