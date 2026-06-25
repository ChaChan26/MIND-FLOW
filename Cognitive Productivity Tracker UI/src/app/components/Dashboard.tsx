import { useState, useEffect, useMemo } from "react";
import {
  MonitorCheck, Check, RefreshCw, Brain, Zap, Battery, Clock,
  ChevronDown, Sparkles, Plus, Trash2, ListChecks, Heart, Wind,
} from "lucide-react";
import { LineChart, Line, ResponsiveContainer, Tooltip } from "recharts";
import { toast } from "sonner";
import { AppMode, AppClass, BASE_WORK, BASE_REST } from "../hooks/useStaminaEngine";
import { VitalityTracker } from "./VitalityTracker";
import { useReflections } from "../hooks/useReflections";
import { useLocalStorage } from "../hooks/useLocalStorage";
import type { Mood } from "../hooks/useReflections";

// ─── Constants ────────────────────────────────────────────────────────────────
const WISDOM = [
  "Energy, not time, is the fundamental currency of high performance.",
  "Almost everything will work again if you unplug it for a few minutes — including you.",
  "The secret of getting ahead is getting started.",
  "Protect your enthusiasm from the negativity and fear of others.",
  "Decide and stick with it, particularly during times of need for strong leadership.",
];

const SEGMENTS = 5;

const MOODS: Mood[] = ["Calm", "Focused", "Neutral", "Anxious", "Overwhelmed", "Frustrated", "Exhausted"];
const MOOD_COLORS: Record<Mood, string> = {
  Calm: "#8FA08D", Focused: "#7A9BAA", Neutral: "#B5B0A8",
  Anxious: "#C5A882", Overwhelmed: "#C17B6B", Frustrated: "#B87565", Exhausted: "#A08D8D",
};

const MODE_META: Record<AppMode, { label: string; color: string; dimColor: string; bg: string; heroBg: string; timerLabel: string }> = {
  work:     { label: "Deep Work",  color: "#8FA08D", dimColor: "rgba(143,160,141,0.2)", bg: "#E4EDE3", heroBg: "linear-gradient(135deg, rgba(143,160,141,0.12) 0%, rgba(143,160,141,0.04) 100%)", timerLabel: "DEEP WORK" },
  recharge: { label: "Recharge",   color: "#7A9BAA", dimColor: "rgba(122,155,170,0.2)", bg: "#E0EBF0", heroBg: "linear-gradient(135deg, rgba(122,155,170,0.12) 0%, rgba(122,155,170,0.04) 100%)", timerLabel: "RECHARGE" },
  rest:     { label: "Rest Lock",  color: "#C5A882", dimColor: "rgba(197,168,130,0.2)", bg: "#F5EFE5", heroBg: "linear-gradient(135deg, rgba(197,168,130,0.14) 0%, rgba(197,168,130,0.04) 100%)", timerLabel: "REST LOCK" },
};

const CLASS_META: Record<AppClass, { label: string; color: string; bg: string }> = {
  work:     { label: "Work",     color: "#8FA08D", bg: "#E4EDE3" },
  recharge: { label: "Recharge", color: "#7A9BAA", bg: "#E0EBF0" },
  neutral:  { label: "Neutral",  color: "#B5B0A8", bg: "#EDE8DF" },
};

interface Props {
  battery: number; mode: AppMode; timerSeconds: number; timerMax: number;
  activeApp: string; classifiedApp: AppClass; autopilot: boolean;
  energy: number; friction: number; sleep: number; hydration: number;
  fatigue: number; adaptedWorkSecs: number; adaptedRestSecs: number;
  onSetMode: (m: AppMode) => void; onSetEnergy: (v: number) => void;
  onSetFriction: (v: number) => void; onSetSleep: (v: number) => void;
  onSetHydration: (v: number) => void; onOverrideClassify: (cls: AppClass) => void;
}

// ─── Forecast tooltip ─────────────────────────────────────────────────────────
function ForecastTip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const v = payload[0]?.value;
  const color = v > 55 ? "#8FA08D" : v > 30 ? "#C5A882" : "#C17B6B";
  return (
    <div style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 10, padding: "7px 11px" }}>
      <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.6rem", color: "var(--muted-foreground)", marginBottom: 2 }}>{label}</div>
      <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.8rem", color }}>{v}%</div>
    </div>
  );
}

// ─── Task Planner ─────────────────────────────────────────────────────────────
const SEED_TASKS = [
  { id: "t1", text: "Implement collision physics", done: false },
  { id: "t2", text: "Write daily standup notes",   done: true  },
  { id: "t3", text: "Review PR for shader system", done: false },
];

function TaskPlanner() {
  const [tasks, setTasks] = useLocalStorage("mindflow_tasks", SEED_TASKS);
  const [input, setInput] = useState("");
  const done = tasks.filter(t => t.done).length;

  const addTask = () => {
    if (!input.trim()) return;
    setTasks(prev => [...prev, { id: `t${Date.now()}`, text: input.trim(), done: false }]);
    setInput("");
  };

  const toggleTask = (id: string) => {
    setTasks(prev => prev.map(t => {
      if (t.id !== id) return t;
      if (!t.done) toast.success("Task complete", { description: t.text });
      return { ...t, done: !t.done };
    }));
  };

  return (
    <div style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 20, overflow: "hidden", boxShadow: "0 2px 16px rgba(0,0,0,0.04)" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 20px", borderBottom: "1px solid var(--border)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <ListChecks size={13} style={{ color: "var(--primary)" }} />
          <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.68rem", letterSpacing: "0.1em", color: "var(--muted-foreground)", textTransform: "uppercase" }}>Task Planner</span>
        </div>
        <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.65rem", color: "var(--primary)" }}>{done}/{tasks.length}</span>
      </div>

      {/* Progress bar */}
      <div style={{ height: 2, background: "var(--muted)" }}>
        <div style={{ height: "100%", width: `${tasks.length ? (done / tasks.length) * 100 : 0}%`, background: "var(--primary)", transition: "width 0.4s ease" }} />
      </div>

      <div style={{ padding: "12px 20px", display: "flex", flexDirection: "column", gap: 4 }}>
        {tasks.length === 0 && (
          <div style={{ textAlign: "center", padding: "16px 0", fontFamily: "'DM Sans', sans-serif", fontSize: "0.78rem", color: "var(--muted-foreground)", fontStyle: "italic" }}>
            No tasks yet — add your first micro-milestone below.
          </div>
        )}
        {tasks.map(task => (
          <div key={task.id} className="group" style={{ display: "flex", alignItems: "center", gap: 10, padding: "6px 0" }}>
            <button onClick={() => toggleTask(task.id)}
              style={{
                width: 18, height: 18, borderRadius: 5, flexShrink: 0, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", transition: "all 0.15s",
                border: `2px solid ${task.done ? "var(--primary)" : "var(--border)"}`,
                background: task.done ? "var(--primary)" : "transparent",
              }}>
              {task.done && <Check size={10} style={{ color: "var(--primary-foreground)" }} />}
            </button>
            <span style={{
              flex: 1, fontFamily: "'DM Sans', sans-serif", fontSize: "0.83rem",
              color: task.done ? "var(--muted-foreground)" : "var(--foreground)",
              textDecoration: task.done ? "line-through" : "none", transition: "all 0.2s",
            }}>{task.text}</span>
            <button onClick={() => setTasks(p => p.filter(t => t.id !== task.id))}
              style={{ background: "none", border: "none", cursor: "pointer", padding: 2, opacity: 0, transition: "opacity 0.15s", display: "flex" }}
              className="group-hover:opacity-60">
              <Trash2 size={11} style={{ color: "var(--muted-foreground)" }} />
            </button>
          </div>
        ))}
      </div>

      <div style={{ padding: "0 20px 16px", display: "flex", gap: 8 }}>
        <input value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === "Enter" && addTask()}
          placeholder="Add a micro-task…"
          style={{ flex: 1, padding: "8px 12px", borderRadius: 10, border: "1px solid var(--border)", outline: "none", fontFamily: "'DM Sans', sans-serif", fontSize: "0.79rem", background: "var(--muted)", color: "var(--foreground)" }}
        />
        <button onClick={addTask}
          style={{ width: 34, height: 34, borderRadius: 10, border: "none", cursor: "pointer", background: "var(--primary)", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Plus size={14} style={{ color: "var(--primary-foreground)" }} />
        </button>
      </div>
    </div>
  );
}

// ─── Check-In + Gratitude ────────────────────────────────────────────────────
function CheckInGratitude() {
  const { addReflection } = useReflections();
  const [energy, setEnergy]     = useState(3);
  const [mood, setMood]         = useState<Mood>("Focused");
  const [wins, setWins]         = useState("");
  const [gratitude, setGratitude] = useLocalStorage("mindflow_gratitude", ["", "", ""]);
  const [submitted, setSubmitted] = useState(false);
  const [gratSaved, setGratSaved] = useState(false);

  const handleCheckin = () => {
    addReflection({ energy, friction: 3, mood, sleepHours: 7, wins, roadblocks: "" });
    setSubmitted(true); setWins("");
    toast.success("Check-in logged", { description: `Energy ${energy}/5 · feeling ${mood}` });
    setTimeout(() => setSubmitted(false), 2500);
  };

  const handleGratitude = () => {
    const filled = gratitude.filter(g => g.trim()).length;
    if (filled === 0) { toast.error("Add at least one thing you're grateful for"); return; }
    setGratSaved(true);
    toast.success("Gratitude committed", { description: `${filled} ${filled === 1 ? "entry" : "entries"} saved to your journal`, icon: "💛" });
    setTimeout(() => setGratSaved(false), 2000);
  };

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
      {/* Check-In */}
      <div style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 20, padding: "20px 22px", boxShadow: "0 2px 16px rgba(0,0,0,0.04)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
          <Zap size={13} style={{ color: "var(--primary)" }} />
          <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.68rem", letterSpacing: "0.1em", color: "var(--muted-foreground)", textTransform: "uppercase", flex: 1 }}>Quick Check-In</span>
          {submitted && <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.6rem", color: "var(--primary)" }}>✓ Logged</span>}
        </div>

        <div style={{ marginBottom: 14 }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
            <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.76rem", color: "var(--foreground)" }}>Energy</span>
            <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.72rem", color: "var(--primary)" }}>{energy}/5</span>
          </div>
          <div style={{ display: "flex", gap: 5 }}>
            {[1, 2, 3, 4, 5].map(n => (
              <button key={n} onClick={() => setEnergy(n)} style={{
                flex: 1, height: 26, borderRadius: 6, border: "none", cursor: "pointer",
                background: n <= energy ? "var(--primary)" : "var(--muted)", opacity: n <= energy ? 1 : 0.35, transition: "all 0.15s",
              }} />
            ))}
          </div>
        </div>

        <div style={{ marginBottom: 14 }}>
          <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.65rem", letterSpacing: "0.08em", color: "var(--muted-foreground)", textTransform: "uppercase", marginBottom: 7 }}>Mood</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
            {MOODS.map(m => (
              <button key={m} onClick={() => setMood(m)} style={{
                padding: "3px 8px", borderRadius: 20, border: "none", cursor: "pointer",
                fontFamily: "'DM Sans', sans-serif", fontSize: "0.7rem",
                background: mood === m ? MOOD_COLORS[m] : "var(--muted)",
                color: mood === m ? "#FDFCF9" : "var(--muted-foreground)", transition: "all 0.15s",
              }}>{m}</button>
            ))}
          </div>
        </div>

        <textarea value={wins} onChange={e => setWins(e.target.value)} placeholder="Today's win or highlight…" rows={2}
          style={{ width: "100%", resize: "none", border: "1px solid var(--border)", borderRadius: 10, padding: "8px 11px", fontFamily: "'DM Sans', sans-serif", fontSize: "0.78rem", color: "var(--foreground)", background: "var(--muted)", outline: "none", lineHeight: 1.55, boxSizing: "border-box", marginBottom: 12 }}
        />
        <button onClick={handleCheckin}
          style={{ width: "100%", padding: "9px 0", borderRadius: 10, border: "none", background: "var(--primary)", color: "var(--primary-foreground)", fontFamily: "'DM Sans', sans-serif", fontSize: "0.82rem", cursor: "pointer" }}>
          Log Check-In
        </button>
      </div>

      {/* Gratitude */}
      <div style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 20, padding: "20px 22px", boxShadow: "0 2px 16px rgba(0,0,0,0.04)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
          <Heart size={13} style={{ color: "#C5A882" }} />
          <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.68rem", letterSpacing: "0.1em", color: "var(--muted-foreground)", textTransform: "uppercase", flex: 1 }}>Gratitude Board</span>
          {gratSaved && <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.6rem", color: "#C5A882" }}>✓ Saved</span>}
        </div>
        <p style={{ fontFamily: "'Lora', serif", fontSize: "0.77rem", color: "var(--muted-foreground)", lineHeight: 1.6, fontStyle: "italic", marginBottom: 14 }}>
          Name three things you appreciate today.
        </p>
        <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 14 }}>
          {gratitude.map((val, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{
                width: 20, height: 20, borderRadius: "50%", flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center",
                background: val.trim() ? "#C5A882" : "var(--muted)",
                fontFamily: "'DM Mono', monospace", fontSize: "0.62rem",
                color: val.trim() ? "#FDFCF9" : "var(--muted-foreground)", transition: "all 0.2s",
              }}>{i + 1}</span>
              <input value={val} onChange={e => setGratitude(prev => prev.map((g, j) => j === i ? e.target.value : g))}
                placeholder={["I'm grateful for…", "One person I appreciate…", "Something I overlook…"][i]}
                style={{ flex: 1, padding: "7px 11px", borderRadius: 9, border: "1px solid var(--border)", outline: "none", fontFamily: "'DM Sans', sans-serif", fontSize: "0.78rem", background: "var(--muted)", color: "var(--foreground)" }}
              />
            </div>
          ))}
        </div>
        <button onClick={handleGratitude}
          style={{ width: "100%", padding: "9px 0", borderRadius: 10, background: "rgba(197,168,130,0.12)", color: "#C5A882", border: "1px solid rgba(197,168,130,0.3)", fontFamily: "'DM Sans', sans-serif", fontSize: "0.82rem", cursor: "pointer" }}>
          <Sparkles size={11} style={{ display: "inline", marginRight: 6, verticalAlign: "middle" }} />
          Commit Gratitude
        </button>
      </div>
    </div>
  );
}

// ─── Main Dashboard ────────────────────────────────────────────────────────────
export function Dashboard({
  battery, mode, timerSeconds, timerMax, activeApp, classifiedApp,
  autopilot, energy, friction, sleep, hydration, fatigue,
  adaptedWorkSecs, adaptedRestSecs,
  onSetMode, onSetEnergy, onSetFriction, onSetSleep, onSetHydration, onOverrideClassify,
}: Props) {
  const [intention, setIntention]     = useLocalStorage("mindflow_intention", "");
  const [intentionSaved, setIntentionSaved] = useState(false);
  const [autopilotOpen, setAutopilotOpen]   = useState(false);
  const [prevApp, setPrevApp]         = useState<AppClass>(classifiedApp);
  const [classFlash, setClassFlash]   = useState(false);
  const [wisdomIdx, setWisdomIdx]     = useState(0);
  const [wisdomVisible, setWisdomVisible] = useState(true);

  useEffect(() => {
    const id = setInterval(() => {
      setWisdomVisible(false);
      setTimeout(() => { setWisdomIdx(i => (i + 1) % WISDOM.length); setWisdomVisible(true); }, 350);
    }, 10000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (classifiedApp !== prevApp) {
      setClassFlash(true);
      setTimeout(() => setClassFlash(false), 1200);
      setPrevApp(classifiedApp);
    }
  }, [classifiedApp, prevApp]);

  // Dynamic forecast
  const FORECAST = useMemo(() => {
    let b = battery;
    const workMins = adaptedWorkSecs / 60;
    const restMins = adaptedRestSecs / 60;
    let inWork = mode === "work";
    let blockLeft = timerSeconds / 60;
    return [0, 30, 60, 90, 120, 150, 180].map((mins, idx) => {
      if (idx === 0) return { t: "Now", v: Math.round(b) };
      let rem = 30;
      while (rem > 0) {
        const consume = Math.min(rem, blockLeft);
        b = Math.min(100, Math.max(0, b + (inWork ? -(0.5 + fatigue * 0.01) : 0.8) * consume));
        blockLeft -= consume; rem -= consume;
        if (blockLeft <= 0) { inWork = !inWork; blockLeft = inWork ? workMins : restMins; }
      }
      return { t: `+${mins}m`, v: Math.round(b) };
    });
  }, [battery, mode, fatigue, adaptedWorkSecs, adaptedRestSecs, timerSeconds]);

  const fmt = (s: number) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
  const timerPct   = timerMax > 0 ? timerSeconds / timerMax : 0;
  const ringR      = 68;
  const ringCirc   = 2 * Math.PI * ringR;
  const filledSegs = Math.round((battery / 100) * SEGMENTS);
  const meta       = MODE_META[mode];
  const clsMeta    = CLASS_META[classifiedApp];
  const fatigueColor = fatigue < 30 ? "var(--primary)" : fatigue < 60 ? "#C5A882" : "#C17B6B";
  const fatigueLabel = fatigue < 30 ? "Low" : fatigue < 60 ? "Moderate" : fatigue < 80 ? "High" : "Critical";
  const workReduction = Math.round((BASE_WORK - adaptedWorkSecs) / 60);
  const restExtension = Math.round((adaptedRestSecs - BASE_REST) / 60);
  const forecastEnd   = FORECAST[FORECAST.length - 1]?.v ?? battery;
  const forecastColor = forecastEnd > 55 ? "#8FA08D" : forecastEnd > 30 ? "#C5A882" : "#C17B6B";

  const saveIntention = async () => {
    if (!intention.trim()) return;
    try {
      const qs = window.location.search;
      await fetch(`/api/goal${qs}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ goal: intention })
      });
    } catch (e) {}
    setIntentionSaved(true);
    toast.success("Intention set for this block", { description: intention });
    setTimeout(() => setIntentionSaved(false), 2000);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16, padding: "28px 28px", height: "100%", overflowY: "auto", scrollbarWidth: "none", background: "var(--background)", boxSizing: "border-box" }}>

      {/* ══ HERO CARD ══════════════════════════════════════════════════════════ */}
      <div style={{
        borderRadius: 24, border: "1px solid var(--border)", overflow: "hidden",
        background: meta.heroBg, backdropFilter: "blur(12px)",
        boxShadow: `0 4px 32px ${meta.color}18`,
      }}>
        <div style={{ display: "grid", gridTemplateColumns: "auto 1fr auto", gap: 0, alignItems: "center" }}>

          {/* Timer ring */}
          <div style={{ padding: "28px 24px 28px 32px", display: "flex", flexDirection: "column", alignItems: "center", gap: 10 }}>
            <div style={{ position: "relative", width: ringR * 2 + 12, height: ringR * 2 + 12 }}>
              <svg width={ringR * 2 + 12} height={ringR * 2 + 12} style={{ transform: "rotate(-90deg)" }}>
                <circle cx={ringR + 6} cy={ringR + 6} r={ringR} fill="none" stroke={`${meta.color}22`} strokeWidth={7} />
                <circle cx={ringR + 6} cy={ringR + 6} r={ringR} fill="none" stroke={meta.color} strokeWidth={7}
                  strokeLinecap="round" strokeDasharray={ringCirc}
                  strokeDashoffset={ringCirc * (1 - timerPct)}
                  style={{ transition: "stroke-dashoffset 1s linear", filter: `drop-shadow(0 0 8px ${meta.color}88)` }}
                />
              </svg>
              {/* Center content */}
              <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
                <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "1.65rem", color: "var(--foreground)", letterSpacing: "-0.02em", lineHeight: 1 }}>
                  {fmt(timerSeconds)}
                </div>
                <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.52rem", color: meta.color, letterSpacing: "0.14em", textTransform: "uppercase", marginTop: 4 }}>
                  {meta.timerLabel}
                </div>
              </div>
            </div>

            {/* Mode pills */}
            <div style={{ display: "flex", gap: 5 }}>
              {(["work", "recharge", "rest"] as AppMode[]).map(m => {
                const mm = MODE_META[m];
                return (
                  <button key={m} onClick={() => onSetMode(m)}
                    style={{
                      padding: "4px 10px", borderRadius: 20, border: "none", cursor: "pointer",
                      fontFamily: "'DM Mono', monospace", fontSize: "0.58rem", letterSpacing: "0.06em", textTransform: "uppercase",
                      background: mode === m ? mm.color : "transparent",
                      color: mode === m ? "#FDFCF9" : "var(--muted-foreground)",
                      boxShadow: mode === m ? `0 2px 10px ${mm.color}44` : "none",
                      transition: "all 0.2s",
                    }}>
                    {mm.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Center: Intention + Wisdom */}
          <div style={{ padding: "28px 16px", borderLeft: `1px solid ${meta.color}22`, borderRight: `1px solid ${meta.color}22`, display: "flex", flexDirection: "column", gap: 16, minWidth: 0 }}>
            {/* Intention */}
            <div>
              <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.6rem", letterSpacing: "0.12em", color: meta.color, textTransform: "uppercase", marginBottom: 6 }}>
                Session Intention
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <input value={intention} onChange={e => { setIntention(e.target.value); setIntentionSaved(false); }}
                  onKeyDown={e => e.key === "Enter" && saveIntention()}
                  placeholder="What are you building this block?"
                  style={{
                    flex: 1, outline: "none", background: "transparent", border: "none",
                    fontFamily: "'Lora', serif", fontSize: "1.05rem", color: "var(--foreground)",
                    borderBottom: `1px solid ${meta.color}44`, paddingBottom: 4,
                  }}
                />
                <button onClick={saveIntention}
                  style={{ width: 28, height: 28, borderRadius: 8, border: "none", cursor: "pointer", flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center", transition: "all 0.25s", background: intentionSaved ? meta.color : `${meta.color}22`, color: intentionSaved ? "#FDFCF9" : meta.color }}>
                  <Check size={13} />
                </button>
              </div>
            </div>

            {/* Wisdom */}
            <div style={{ padding: "12px 16px", borderRadius: 12, background: `${meta.color}10`, border: `1px solid ${meta.color}20` }}>
              <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.58rem", letterSpacing: "0.1em", color: meta.color, textTransform: "uppercase", marginBottom: 5 }}>
                Focus Wisdom
              </div>
              <p style={{ fontFamily: "'Lora', serif", fontSize: "0.82rem", color: "var(--foreground)", lineHeight: 1.6, fontStyle: "italic", margin: 0, opacity: wisdomVisible ? 1 : 0, transition: "opacity 0.35s ease" }}>
                "{WISDOM[wisdomIdx]}"
              </p>
            </div>
          </div>

          {/* Right: Battery + Mini stats */}
          <div style={{ padding: "28px 28px 28px 20px", display: "flex", flexDirection: "column", gap: 16, minWidth: 160 }}>
            {/* Battery large % */}
            <div style={{ textAlign: "center" }}>
              <div style={{ fontFamily: "'Lora', serif", fontSize: "2.8rem", color: "var(--foreground)", lineHeight: 1, letterSpacing: "-0.03em" }}>
                {Math.round(battery)}<span style={{ fontSize: "1.2rem", color: "var(--muted-foreground)" }}>%</span>
              </div>
              <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.58rem", color: "var(--muted-foreground)", letterSpacing: "0.08em", textTransform: "uppercase", marginTop: 4 }}>
                Mental Battery
              </div>
              {/* Segments */}
              <div style={{ display: "flex", gap: 4, marginTop: 10, justifyContent: "center" }}>
                {Array.from({ length: SEGMENTS }).map((_, i) => (
                  <div key={`b-${i}`} style={{
                    width: 18, height: 6, borderRadius: 3, transition: "all 0.5s",
                    background: i < filledSegs
                      ? battery > 40 ? "#8FA08D" : "#C17B6B"
                      : "var(--muted)",
                    boxShadow: i < filledSegs ? `0 0 6px ${battery > 40 ? "#8FA08D" : "#C17B6B"}66` : "none",
                  }} />
                ))}
              </div>
            </div>
            {/* Quick stat row */}
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {[
                { label: "Fatigue",   value: `${fatigue}%`,                               color: fatigueColor },
                { label: "Work Block",value: `${Math.floor(adaptedWorkSecs / 60)}m`,       color: "var(--primary)" },
                { label: "Forecast",  value: `${forecastEnd}% @ +3h`,                     color: forecastColor },
              ].map(({ label, value, color }) => (
                <div key={label} style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.68rem", color: "var(--muted-foreground)" }}>{label}</span>
                  <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.68rem", color }}>{value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* ══ ROW: Forecast + Classifier ════════════════════════════════════════ */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        {/* Forecast sparkline */}
        <div style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 20, padding: "20px 22px", boxShadow: "0 2px 16px rgba(0,0,0,0.04)" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
            <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.68rem", letterSpacing: "0.1em", color: "var(--muted-foreground)", textTransform: "uppercase" }}>
              Stamina Forecast (3h)
            </span>
            <span style={{ padding: "2px 8px", borderRadius: 20, fontFamily: "'DM Mono', monospace", fontSize: "0.6rem", background: `${forecastColor}18`, color: forecastColor, border: `1px solid ${forecastColor}30` }}>
              {forecastEnd}% at +3h
            </span>
          </div>
          <ResponsiveContainer width="100%" height={64}>
            <LineChart data={FORECAST} margin={{ top: 4, right: 4, bottom: 0, left: -28 }}>
              <Tooltip content={<ForecastTip />} />
              <Line type="monotone" dataKey="v" stroke={forecastColor} strokeWidth={2.5} dot={false}
                activeDot={{ r: 4, fill: forecastColor, stroke: "var(--card)", strokeWidth: 2 }}
                style={{ filter: `drop-shadow(0 0 5px ${forecastColor}99)` }}
              />
            </LineChart>
          </ResponsiveContainer>
          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4 }}>
            {FORECAST.map(d => (
              <span key={d.t} style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.54rem", color: "var(--muted-foreground)" }}>{d.t}</span>
            ))}
          </div>
        </div>

        {/* Active window classifier */}
        <div style={{
          background: "var(--card)", border: "1px solid var(--border)", borderRadius: 20, padding: "20px 22px",
          boxShadow: "0 2px 16px rgba(0,0,0,0.04)",
          outline: classFlash ? `2px solid ${clsMeta.color}55` : "2px solid transparent", transition: "outline 0.3s ease",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
            <div style={{ width: 32, height: 32, borderRadius: 10, background: clsMeta.bg, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
              <MonitorCheck size={15} style={{ color: clsMeta.color, transition: "color 0.5s ease" }} />
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
                <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.65rem", letterSpacing: "0.08em", color: "var(--muted-foreground)", textTransform: "uppercase" }}>Active Window</span>
                <span style={{ padding: "2px 8px", borderRadius: 20, fontFamily: "'DM Mono', monospace", fontSize: "0.58rem", background: clsMeta.bg, color: clsMeta.color }}>
                  {clsMeta.label.toUpperCase()}
                </span>
              </div>
              <div style={{ fontFamily: "'Lora', serif", fontSize: "0.9rem", color: "var(--foreground)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                {activeApp}
              </div>
            </div>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            {(["work", "recharge"] as AppClass[]).map(cls => {
              const cm = CLASS_META[cls];
              return (
                <button key={cls} onClick={() => onOverrideClassify(cls)}
                  style={{
                    flex: 1, padding: "8px 0", borderRadius: 12, cursor: "pointer", fontFamily: "'DM Sans', sans-serif", fontSize: "0.78rem",
                    background: classifiedApp === cls ? cm.bg : "transparent",
                    color: classifiedApp === cls ? cm.color : "var(--muted-foreground)",
                    border: `1px solid ${classifiedApp === cls ? cm.color + "55" : "var(--border)"}`,
                    transition: "all 0.2s",
                  }}>
                  {cm.label}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* ══ COGNITIVE AUTOPILOT ═══════════════════════════════════════════════ */}
      <div style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 20, overflow: "hidden", boxShadow: "0 2px 16px rgba(0,0,0,0.04)" }}>
        <button onClick={() => setAutopilotOpen(o => !o)}
          style={{ width: "100%", display: "flex", alignItems: "center", padding: "16px 22px", background: "transparent", border: "none", cursor: "pointer", gap: 10 }}>
          <Brain size={14} style={{ color: autopilot ? "var(--primary)" : "var(--muted-foreground)", flexShrink: 0 }} />
          <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.68rem", letterSpacing: "0.1em", color: "var(--muted-foreground)", textTransform: "uppercase" }}>
            Cognitive Autopilot
          </span>
          <span style={{
            padding: "2px 8px", borderRadius: 20, fontFamily: "'DM Mono', monospace", fontSize: "0.58rem",
            background: autopilot ? "rgba(143,160,141,0.12)" : "var(--muted)", color: autopilot ? "var(--primary)" : "var(--muted-foreground)",
          }}>{autopilot ? "ACTIVE" : "PAUSED"}</span>

          {!autopilotOpen && (
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginLeft: "auto", marginRight: 8 }}>
              <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.62rem", color: fatigueColor }}>⚡ {fatigue}% {fatigueLabel}</span>
              <span style={{ width: 1, height: 12, background: "var(--border)" }} />
              <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.62rem", color: "var(--primary)" }}>{Math.floor(adaptedWorkSecs / 60)}m block</span>
            </div>
          )}

          <div style={{ marginLeft: autopilotOpen ? "auto" : 0, transform: autopilotOpen ? "rotate(180deg)" : "rotate(0deg)", transition: "transform 0.25s ease" }}>
            <ChevronDown size={15} style={{ color: "var(--muted-foreground)" }} />
          </div>
        </button>

        <div style={{ maxHeight: autopilotOpen ? 400 : 0, overflow: "hidden", transition: "max-height 0.35s cubic-bezier(0.4,0,0.2,1)" }}>
          <div style={{ padding: "0 22px 20px", borderTop: "1px solid var(--border)", display: "flex", flexDirection: "column", gap: 16 }}>
            {/* Stat tiles */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 10, paddingTop: 16 }}>
              {[
                { Icon: Zap,     label: "Fatigue",      value: fatigueLabel,                                   sub: `${fatigue}/100`,                                              color: fatigueColor },
                { Icon: Clock,   label: "Work Block",   value: `${Math.floor(adaptedWorkSecs / 60)}m`,          sub: workReduction > 0 ? `−${workReduction}m scaled` : "At baseline", color: "var(--primary)" },
                { Icon: Clock,   label: "Rest Block",   value: `${Math.floor(adaptedRestSecs / 60)}m`,          sub: restExtension > 0 ? `+${restExtension}m scaled` : "At baseline", color: "#7A9BAA" },
                { Icon: Battery, label: "Battery Rate", value: mode === "work" ? `−${(0.5 + fatigue * 0.01).toFixed(1)}%/m` : `+${mode === "rest" ? "1.2" : "0.4"}%/m`, sub: mode === "work" ? "Depleting" : "Replenishing", color: mode === "work" ? "#C17B6B" : "var(--primary)" },
              ].map(({ Icon, label, value, sub, color }) => (
                <div key={label} style={{ padding: "12px 14px", borderRadius: 14, background: "var(--muted)", border: "1px solid var(--border)" }}>
                  <Icon size={12} style={{ color, marginBottom: 7 }} />
                  <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.88rem", color: "var(--foreground)" }}>{value}</div>
                  <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.64rem", color: "var(--muted-foreground)", marginTop: 2 }}>{label}</div>
                  <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.58rem", color, marginTop: 3 }}>{sub}</div>
                </div>
              ))}
            </div>
            {/* Sliders */}
            {[
              { label: "Energy Level",    value: energy,   set: onSetEnergy,   color: "#8FA08D" },
              { label: "Mental Friction", value: friction, set: onSetFriction, color: "#C5A882" },
            ].map(({ label, value, set, color }) => (
              <div key={label}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 7 }}>
                  <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.75rem", color: "var(--muted-foreground)" }}>{label}</span>
                  <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.72rem", color }}>{value}%</span>
                </div>
                <input type="range" min={0} max={100} value={value} onChange={e => set(Number(e.target.value))}
                  className="w-full h-1.5 rounded-full appearance-none outline-none cursor-pointer"
                  style={{ accentColor: color, background: `linear-gradient(to right, ${color} ${value}%, var(--muted) ${value}%)` }}
                />
              </div>
            ))}
            {fatigue >= 65 && (
              <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "10px 14px", borderRadius: 12, background: "rgba(193,123,107,0.06)", border: "1px solid rgba(193,123,107,0.18)" }}>
                <Wind size={13} style={{ color: "#C17B6B", flexShrink: 0 }} />
                <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.75rem", color: "#C17B6B" }}>
                  High fatigue — autopilot has shortened work blocks and extended rest windows.
                </span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ══ CHECK-IN + GRATITUDE ══════════════════════════════════════════════ */}
      <CheckInGratitude />

      {/* ══ TASK PLANNER ═════════════════════════════════════════════════════ */}
      <TaskPlanner />

      {/* ══ VITALITY ═════════════════════════════════════════════════════════ */}
      <VitalityTracker sleep={sleep} hydration={hydration} onSetSleep={onSetSleep} onSetHydration={onSetHydration} />
    </div>
  );
}
