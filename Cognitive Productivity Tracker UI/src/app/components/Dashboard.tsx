/**
 * MIND-FLOW Primary Dashboard component orchestrating telemetry, mode cards, intentions, and widgets.
 *
 * Author: ChaChan26 <minhharry2006@gmail.com>
 * Copyright (c) 2026 ChaChan26. All rights reserved.
 */

import { useState, useEffect, useMemo, useRef } from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  MonitorCheck, Check, RefreshCw, Brain, Zap, Battery, Clock,
  ChevronDown, Sparkles, Plus, Trash2, ListChecks, Heart, Wind,
  AlertTriangle, Bell, Droplets, Coffee, X, ArrowRight, ShieldAlert,
  Activity,
} from "lucide-react";
import { LineChart, Line, ResponsiveContainer, Tooltip } from "recharts";
import { toast } from "sonner";
import { AppMode, AppClass, BASE_WORK, BASE_REST, getAuthHeaders } from "../hooks/useStaminaEngine";
import { VitalityTracker } from "./VitalityTracker";
import { FocusTimer } from "./FocusTimer";
import { MorningBriefing } from "./MorningBriefing";
import { DailyDigest } from "./DailyDigest";
import { useReflections } from "../hooks/useReflections";
import { useLocalStorage } from "../hooks/useLocalStorage";
import type { Mood } from "../hooks/useReflections";
import type { RechartsTooltipProps } from "../types/recharts";

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
  Calm: "var(--accent-4, #82C1B8)", Focused: "var(--accent-2, #7583CA)", Neutral: "var(--muted-foreground)",
  Anxious: "var(--accent-3, #F0B68E)", Overwhelmed: "var(--accent-1, #FF84A2)", Frustrated: "var(--primary-variant, #2A2A3A)", Exhausted: "var(--secondary-foreground, #1A1A24)",
};

const MODE_META: Record<string, { label: string; color: string; dimColor: string; bg: string; heroBg: string; timerLabel: string }> = {
  work:     { label: "Deep Work",  color: "var(--primary)", dimColor: "var(--border)", bg: "var(--muted)", heroBg: "linear-gradient(135deg, var(--muted) 0%, transparent 100%)", timerLabel: "DEEP WORK" },
  recharge: { label: "Recharge",   color: "var(--secondary)", dimColor: "var(--border)", bg: "var(--muted)", heroBg: "linear-gradient(135deg, var(--muted) 0%, transparent 100%)", timerLabel: "RECHARGE" },
  rest:     { label: "Rest Cycle", color: "var(--accent-4, #82C1B8)", dimColor: "var(--border)", bg: "var(--muted)", heroBg: "linear-gradient(135deg, var(--muted) 0%, transparent 100%)", timerLabel: "RESTING" },
  neutral:  { label: "Neutral",    color: "var(--muted-foreground)", dimColor: "var(--border)", bg: "var(--muted)", heroBg: "linear-gradient(135deg, var(--muted) 0%, transparent 100%)", timerLabel: "READY" }
};

const CLASS_META: Record<string, { label: string; color: string; bg: string }> = {
  work:     { label: "Work",     color: "var(--primary)", bg: "var(--muted)" },
  recharge: { label: "Recharge", color: "var(--secondary)", bg: "var(--muted)" },
  neutral:  { label: "Neutral",  color: "var(--muted-foreground)", bg: "var(--border)" },
};

import { useStaminaStore } from "../hooks/useStaminaEngine";

// ─── Forecast tooltip ─────────────────────────────────────────────────────────
function ForecastTip({ active, payload, label }: RechartsTooltipProps) {
  if (!active || !payload?.length) return null;
  const v = payload[0]?.value ?? 0;
  const color = v > 55 ? "var(--primary)" : v > 30 ? "var(--secondary)" : "var(--accent)";
  return (
    <div style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: "var(--radii-lg)", padding: "7px 11px" }}>
      <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.6rem", color: "var(--muted-foreground)", marginBottom: 2 }}>{label}</div>
      <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.8rem", color }}>{v}%</div>
    </div>
  );
}

// ─── Task Planner ─────────────────────────────────────────────────────────────
type Priority = "high" | "normal" | "low";
type TaskItem = { id: string; text: string; done: boolean; priority?: Priority };

const SEED_TASKS: TaskItem[] = [
  { id: "t1", text: "Implement collision physics", done: false, priority: "high" },
  { id: "t2", text: "Write daily standup notes",   done: true,  priority: "normal"  },
  { id: "t3", text: "Review PR for shader system", done: false, priority: "normal" },
];

function TaskPlanner() {
  const [tasks, setTasks] = useLocalStorage<TaskItem[]>("mindflow_tasks", SEED_TASKS);
  const [input, setInput] = useState("");
  const [priority, setPriority] = useState<Priority>("normal");
  const [filter, setFilter] = useState<"all" | "active" | "completed">("all");

  const doneCount = tasks.filter(t => t.done).length;

  const addTask = () => {
    if (!input.trim()) return;
    setTasks(prev => [...prev, { id: `t${Date.now()}`, text: input.trim(), done: false, priority }]);
    setInput("");
  };

  const toggleTask = (id: string) => {
    setTasks(prev => prev.map(t => {
      if (t.id !== id) return t;
      if (!t.done) toast.success("Task complete", { description: t.text });
      return { ...t, done: !t.done };
    }));
  };

  const filteredTasks = tasks.filter(t => {
    if (filter === "active") return !t.done;
    if (filter === "completed") return t.done;
    return true;
  });

  const pColors: Record<Priority, { bg: string; color: string; label: string }> = {
    high:   { bg: "rgba(255, 132, 162, 0.15)", color: "var(--accent-1, #FF84A2)", label: "HIGH" },
    normal: { bg: "rgba(142, 151, 253, 0.15)", color: "var(--primary, #8E97FD)", label: "NORM" },
    low:    { bg: "rgba(130, 193, 184, 0.15)", color: "var(--accent-4, #82C1B8)", label: "LOW" },
  };

  return (
    <div style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: "var(--radii-xl)", overflow: "hidden", boxShadow: "var(--shadow-lg)" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 20px", borderBottom: "1px solid var(--border)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <ListChecks size={13} style={{ color: "var(--primary)" }} />
          <span style={{ fontFamily: "'Nunito', sans-serif", fontSize: "0.68rem", letterSpacing: "0.1em", color: "var(--muted-foreground)", textTransform: "uppercase" }}>Task Planner</span>
        </div>
        
        {/* Status Filters */}
        <div style={{ display: "flex", alignItems: "center", gap: 4, background: "var(--muted)", padding: "2px 4px", borderRadius: "var(--radii-sm)" }}>
          {(["all", "active", "completed"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              style={{
                background: filter === f ? "var(--card)" : "transparent",
                color: filter === f ? "var(--primary)" : "var(--muted-foreground)",
                border: "none",
                borderRadius: "var(--radii-sm)",
                padding: "2px 6px",
                fontSize: "0.6rem",
                fontFamily: "'DM Mono', monospace",
                cursor: "pointer",
                textTransform: "capitalize",
              }}
            >
              {f}
            </button>
          ))}
        </div>
        <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.65rem", color: "var(--primary)" }}>{doneCount}/{tasks.length}</span>
      </div>

      {/* Progress bar */}
      <div style={{ height: 2, background: "var(--muted)" }}>
        <div style={{ height: "100%", width: `${tasks.length ? (doneCount / tasks.length) * 100 : 0}%`, background: "var(--primary)", transition: "width 0.4s ease" }} />
      </div>

      <div style={{ padding: "12px 20px", display: "flex", flexDirection: "column", gap: 4 }}>
        {filteredTasks.length === 0 && (
          <div style={{ textAlign: "center", padding: "16px 0", fontFamily: "'Nunito', sans-serif", fontSize: "0.78rem", color: "var(--muted-foreground)", fontStyle: "italic" }}>
            {filter === "all" ? "No tasks yet — add your first micro-milestone below." : `No ${filter} tasks.`}
          </div>
        )}
        {filteredTasks.map(task => {
          const pConf = pColors[task.priority || "normal"];
          return (
            <div key={task.id} className="group" style={{ display: "flex", alignItems: "center", gap: 10, padding: "6px 0" }}>
              <button onClick={() => toggleTask(task.id)}
                style={{
                  width: 18, height: 18, borderRadius: "var(--radii-sm)", flexShrink: 0, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", transition: "all 0.15s",
                  border: `2px solid ${task.done ? "var(--primary)" : "var(--border)"}`,
                  background: task.done ? "var(--primary)" : "transparent",
                }}>
                {task.done && <Check size={10} style={{ color: "var(--primary-foreground)" }} />}
              </button>
              <span style={{
                flex: 1, fontFamily: "'Nunito', sans-serif", fontSize: "0.83rem",
                color: task.done ? "var(--muted-foreground)" : "var(--foreground)",
                textDecoration: task.done ? "line-through" : "none", transition: "all 0.2s",
              }}>{task.text}</span>

              {/* Priority tag */}
              <span style={{
                fontSize: "0.55rem",
                fontFamily: "'DM Mono', monospace",
                padding: "2px 6px",
                borderRadius: "var(--radii-sm)",
                background: pConf.bg,
                color: pConf.color,
                fontWeight: 600,
              }}>
                {pConf.label}
              </span>

              <button onClick={() => setTasks(p => p.filter(t => t.id !== task.id))}
                style={{ background: "none", border: "none", cursor: "pointer", padding: 2, opacity: 0, transition: "opacity 0.15s", display: "flex" }}
                className="group-hover:opacity-60">
                <Trash2 size={11} style={{ color: "var(--muted-foreground)" }} />
              </button>
            </div>
          );
        })}
      </div>

      <div style={{ padding: "0 20px 16px", display: "flex", gap: 8 }}>
        <input value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === "Enter" && addTask()}
          placeholder="Add a micro-task…"
          style={{ flex: 1, padding: "8px 12px", borderRadius: "var(--radii-lg)", border: "1px solid var(--border)", outline: "none", fontFamily: "'Nunito', sans-serif", fontSize: "0.79rem", background: "var(--muted)", color: "var(--foreground)" }}
        />
        
        {/* Priority select toggle */}
        <select
          value={priority}
          onChange={(e) => setPriority(e.target.value as Priority)}
          style={{
            padding: "0 8px",
            borderRadius: "var(--radii-lg)",
            border: "1px solid var(--border)",
            background: "var(--muted)",
            color: "var(--foreground)",
            fontSize: "0.72rem",
            fontFamily: "'DM Mono', monospace",
            cursor: "pointer",
            outline: "none",
          }}
        >
          <option value="normal">Normal</option>
          <option value="high">High</option>
          <option value="low">Low</option>
        </select>

        <button onClick={addTask}
          style={{ width: 34, height: 34, borderRadius: "var(--radii-lg)", border: "none", cursor: "pointer", background: "var(--primary)", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Plus size={14} style={{ color: "var(--primary-foreground)" }} />
        </button>
      </div>
    </div>
  );
}

// ─── Check-In + Gratitude ────────────────────────────────────────────────────
function CheckInGratitude({ currentFriction, sleepTarget }: { currentFriction: number; sleepTarget: number }) {
  const { addReflection } = useReflections();
  const [energy, setEnergy]     = useState(3);
  const [mood, setMood]         = useState<Mood>("Focused");
  const [wins, setWins]         = useState("");
  const [gratitude, setGratitude] = useLocalStorage("mindflow_gratitude", ["", "", ""]);
  const [submitted, setSubmitted] = useState(false);
  const [gratSaved, setGratSaved] = useState(false);

  const handleCheckin = () => {
    addReflection({ energy, friction: currentFriction, mood, sleepHours: sleepTarget, wins, roadblocks: "" });
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
      <div style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: "var(--radii-xl)", padding: "20px 22px", boxShadow: "var(--shadow-lg)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
          <Zap size={13} style={{ color: "var(--primary)" }} />
          <span style={{ fontFamily: "'Nunito', sans-serif", fontSize: "0.68rem", letterSpacing: "0.1em", color: "var(--muted-foreground)", textTransform: "uppercase", flex: 1 }}>Quick Check-In</span>
          {submitted && <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.6rem", color: "var(--primary)" }}>✓ Logged</span>}
        </div>

        <div style={{ marginBottom: 14 }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
            <span style={{ fontFamily: "'Nunito', sans-serif", fontSize: "0.76rem", color: "var(--foreground)" }}>Energy</span>
            <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.72rem", color: "var(--primary)" }}>{energy}/5</span>
          </div>
          <div style={{ display: "flex", gap: 5 }}>
            {[1, 2, 3, 4, 5].map(n => (
              <button key={n} onClick={() => setEnergy(n)} aria-label={`Set energy level to ${n}`} style={{
                flex: 1, height: 26, borderRadius: "var(--radii-sm)", border: "none", cursor: "pointer",
                background: n <= energy ? "var(--primary)" : "var(--muted)", opacity: n <= energy ? 1 : 0.35, transition: "all 0.15s",
              }} />
            ))}
          </div>
        </div>

        <div style={{ marginBottom: 14 }}>
          <div style={{ fontFamily: "'Nunito', sans-serif", fontSize: "0.65rem", letterSpacing: "0.08em", color: "var(--muted-foreground)", textTransform: "uppercase", marginBottom: 7 }}>Mood</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
            {MOODS.map(m => (
              <button key={m} onClick={() => setMood(m)} style={{
                padding: "3px 8px", borderRadius: "var(--radii-xl)", border: "none", cursor: "pointer",
                fontFamily: "'Nunito', sans-serif", fontSize: "0.7rem",
                background: mood === m ? MOOD_COLORS[m] : "var(--muted)",
                color: mood === m ? "var(--primary-foreground)" : "var(--muted-foreground)", transition: "all 0.15s",
              }}>{m}</button>
            ))}
          </div>
        </div>

        <textarea value={wins} onChange={e => setWins(e.target.value)} placeholder="Today's win or highlight…" rows={2}
          style={{ width: "100%", resize: "none", border: "1px solid var(--border)", borderRadius: "var(--radii-lg)", padding: "8px 11px", fontFamily: "'Nunito', sans-serif", fontSize: "0.78rem", color: "var(--foreground)", background: "var(--muted)", outline: "none", lineHeight: 1.55, boxSizing: "border-box", marginBottom: 12 }}
        />
        <button onClick={handleCheckin}
          style={{ width: "100%", padding: "9px 0", borderRadius: "var(--radii-lg)", border: "none", background: "var(--primary)", color: "var(--primary-foreground)", fontFamily: "'Nunito', sans-serif", fontSize: "0.82rem", cursor: "pointer" }}>
          Log Check-In
        </button>
      </div>

      {/* Gratitude */}
      <div style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: "var(--radii-xl)", padding: "20px 22px", boxShadow: "var(--shadow-lg)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
          <Heart size={13} style={{ color: "var(--secondary)" }} />
          <span style={{ fontFamily: "'Nunito', sans-serif", fontSize: "0.68rem", letterSpacing: "0.1em", color: "var(--muted-foreground)", textTransform: "uppercase", flex: 1 }}>Gratitude Board</span>
          {gratSaved && <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.6rem", color: "var(--secondary)" }}>✓ Saved</span>}
        </div>
        <p style={{ fontFamily: "var(--font-sans)", fontSize: "0.77rem", color: "var(--muted-foreground)", lineHeight: 1.6, fontStyle: "italic", marginBottom: 14 }}>
          Name three things you appreciate today.
        </p>
        <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 14 }}>
          {gratitude.map((val, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{
                width: 20, height: 20, borderRadius: "50%", flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center",
                background: val.trim() ? "var(--secondary)" : "var(--muted)",
                fontFamily: "'DM Mono', monospace", fontSize: "0.62rem",
                color: val.trim() ? "var(--primary-foreground)" : "var(--muted-foreground)", transition: "all 0.2s",
              }}>{i + 1}</span>
              <input value={val} onChange={e => setGratitude(prev => prev.map((g, j) => j === i ? e.target.value : g))}
                placeholder={["I'm grateful for…", "One person I appreciate…", "Something I overlook…"][i]}
                style={{ flex: 1, padding: "7px 11px", borderRadius: "var(--radii-md)", border: "1px solid var(--border)", outline: "none", fontFamily: "'Nunito', sans-serif", fontSize: "0.78rem", background: "var(--muted)", color: "var(--foreground)" }}
              />
            </div>
          ))}
        </div>
        <button onClick={handleGratitude}
          style={{ width: "100%", padding: "9px 0", borderRadius: "var(--radii-lg)", background: "var(--muted)", color: "var(--secondary)", border: "1px solid var(--border)", fontFamily: "'Nunito', sans-serif", fontSize: "0.82rem", cursor: "pointer" }}>
          <Sparkles size={11} style={{ display: "inline", marginRight: 6, verticalAlign: "middle" }} />
          Commit Gratitude
        </button>
      </div>
    </div>
  );
}

// ─── Main Dashboard ────────────────────────────────────────────────────────────
export function Dashboard() {
  const battery = useStaminaStore(s => s.battery);
  const mode = useStaminaStore(s => s.mode);
  const timerSeconds = useStaminaStore(s => s.timerSeconds);
  const timerMax = useStaminaStore(s => s.timerMax);
  const activeApp = useStaminaStore(s => s.activeApp);
  const activeProcess = useStaminaStore(s => s.activeProcess);
  const classifiedApp = useStaminaStore(s => s.classifiedApp);
  const autopilot = useStaminaStore(s => s.autopilot);
  const energy = useStaminaStore(s => s.energy);
  const friction = useStaminaStore(s => s.friction);
  const sleep = useStaminaStore(s => s.sleep);
  const hydration = useStaminaStore(s => s.hydration);
  const fatigue = useStaminaStore(s => s.fatigue);
  const adaptedWorkSecs = useStaminaStore(s => s.adaptedWorkSecs);
  const adaptedRestSecs = useStaminaStore(s => s.adaptedRestSecs);
  const settings = useStaminaStore(s => s.settings);
  const todayWork = useStaminaStore(s => s.todayWork || 0);
  const todayRecharge = useStaminaStore(s => s.todayRecharge || 0);
  const activeNudge = useStaminaStore(s => s.activeNudge);
  const companionMessage = useStaminaStore(s => s.companionMessage);
  const handleNudgeAction = useStaminaStore(s => s.handleNudgeAction);
  const dismissNudge = useStaminaStore(s => s.dismissNudge);
  const onSetMode = useStaminaStore(s => s.setMode);
  const onSetEnergy = useStaminaStore(s => s.setEnergy);
  const onSetFriction = useStaminaStore(s => s.setFriction);
  const onSetSleep = useStaminaStore(s => s.setSleep);
  const onSetHydration = useStaminaStore(s => s.setHydration);
  const onOverrideClassify = useStaminaStore(s => s.overrideClassify);
  const extendFocus = useStaminaStore(s => s.extendFocus);
  const takeBreak = useStaminaStore(s => s.takeBreak);
  const startFocus = useStaminaStore(s => s.startFocus);
  const resetTimer = useStaminaStore(s => s.resetTimer);
  const focusScore = useStaminaStore(s => s.focusScore ?? 85);
  const streakDays = useStaminaStore(s => s.streakDays ?? 1);
  const [intention, setIntention]     = useLocalStorage("mindflow_intention", "");
  const [intentionSaved, setIntentionSaved] = useState(false);
  const [autopilotOpen, setAutopilotOpen]   = useState(false);
  const [digestOpen, setDigestOpen]         = useState(false);
  const [prevApp, setPrevApp]         = useState<AppClass>(classifiedApp);
  const [classFlash, setClassFlash]   = useState(false);
  const [wisdomIdx, setWisdomIdx]     = useState(0);
  const [wisdomVisible, setWisdomVisible] = useState(true);
  const wisdomTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const flashTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const id = setInterval(() => {
      setWisdomVisible(false);
      wisdomTimeoutRef.current = setTimeout(() => {
        setWisdomIdx(i => (i + 1) % WISDOM.length);
        setWisdomVisible(true);
      }, 350);
    }, 10000);
    return () => {
      clearInterval(id);
      if (wisdomTimeoutRef.current) clearTimeout(wisdomTimeoutRef.current);
    };
  }, []);

  useEffect(() => {
    if (classifiedApp !== prevApp) {
      setClassFlash(true);
      if (flashTimeoutRef.current) clearTimeout(flashTimeoutRef.current);
      flashTimeoutRef.current = setTimeout(() => setClassFlash(false), 1200);
      setPrevApp(classifiedApp);
    }
    return () => {
      if (flashTimeoutRef.current) clearTimeout(flashTimeoutRef.current);
    };
  }, [classifiedApp, prevApp]);

  // Dynamic forecast
  const timerSecsRounded = Math.round(timerSeconds / 30) * 30;
  const FORECAST = useMemo(() => {
    let b = battery;
    const workMins = Math.max(1, (adaptedWorkSecs || BASE_WORK) / 60);
    const restMins = Math.max(1, (adaptedRestSecs || BASE_REST) / 60);
    let inWork = mode === "work";
    let blockLeft = Math.max(0.1, timerSecsRounded / 60);
    return [0, 30, 60, 90, 120, 150, 180].map((mins, idx) => {
      if (idx === 0) return { t: "Now", v: Math.round(b) };
      let rem = 30;
      while (rem > 0) {
        const consume = Math.min(rem, blockLeft);
        if (consume <= 0) break;
        b = Math.min(100, Math.max(0, b + (inWork ? -(0.5 + fatigue * 0.01) : 0.8) * consume));
        blockLeft -= consume; rem -= consume;
        if (blockLeft <= 0) { inWork = !inWork; blockLeft = Math.max(1, inWork ? workMins : restMins); }
      }
      return { t: `+${mins}m`, v: Math.round(b) };
    });
  }, [battery, mode, fatigue, adaptedWorkSecs, adaptedRestSecs, timerSecsRounded]);

  const fmt = (s: number) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
  const timerPct   = timerMax > 0 ? timerSeconds / timerMax : 0;
  const ringR      = 68;
  const ringCirc   = 2 * Math.PI * ringR;
  const filledSegs = Math.round((battery / 100) * SEGMENTS);
  const meta       = (mode && MODE_META[mode]) ? MODE_META[mode] : MODE_META.neutral;
  const clsMeta    = (classifiedApp && CLASS_META[classifiedApp]) ? CLASS_META[classifiedApp] : CLASS_META.neutral;
  const fatigueColor = fatigue < 30 ? "var(--primary)" : fatigue < 60 ? "var(--secondary)" : "var(--accent)";
  const fatigueLabel = fatigue < 30 ? "Low" : fatigue < 60 ? "Moderate" : fatigue < 80 ? "High" : "Critical";
  const workReduction = Math.round((BASE_WORK - adaptedWorkSecs) / 60);
  const restExtension = Math.round((adaptedRestSecs - BASE_REST) / 60);
  const forecastEnd   = FORECAST[FORECAST.length - 1]?.v ?? battery;
  const forecastColor = forecastEnd > 55 ? "var(--primary)" : forecastEnd > 30 ? "var(--secondary)" : "var(--accent)";

  const saveIntention = async () => {
    if (!intention.trim()) return;
    try {
      const qs = window.location.search;
      const res = await fetch(`/api/goal${qs}`, {
        method: "POST",
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ goal: intention })
      });
      if (res.ok) {
        setIntentionSaved(true);
        toast.success("Intention set for this block", { description: intention });
        setTimeout(() => setIntentionSaved(false), 2000);
      } else {
        toast.error("Failed to save intention");
      }
    } catch (e) {
      toast.error("Network error saving intention");
    }
  };

  return (
    <div className="custom-scrollbar" style={{ display: "flex", flexDirection: "column", gap: 24, padding: "24px 32px", height: "100%", overflowY: "auto", scrollbarWidth: "none", background: "var(--background)", boxSizing: "border-box" }}>

      {/* ══ DAILY MORNING BRIEFING CARD ══ */}
      <MorningBriefing
        recoveryScore={Math.round(battery || 85)}
        suggestedWorkMinutes={Math.round((adaptedWorkSecs || BASE_WORK) / 60)}
        circadianForecastMessage={companionMessage}
        streakDays={streakDays}
        hydrationCups={hydration || 0}
        hydrationTarget={settings?.hydration_target ?? 8}
        onStartSprint={() => onSetMode("work")}
      />

      {/* ══ HEADER & COMPANION COMMAND BAR ══ */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 20, flexWrap: "wrap" }}>
        <div>
          <div style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "4px 12px", borderRadius: "var(--radii-full, 9999px)", background: "var(--primary-alpha-8)", border: "1px solid var(--primary-alpha-20)", marginBottom: 8 }}>
            <span style={{ width: 7, height: 7, borderRadius: "50%", background: "var(--primary)", boxShadow: "0 0 8px var(--primary)" }} />
            <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.65rem", color: "var(--primary)", letterSpacing: "0.08em", textTransform: "uppercase", fontWeight: 700 }}>Cognitive Shield Active</span>
          </div>
          <h1 style={{ fontFamily: "var(--font-sans)", fontSize: "2rem", fontWeight: 800, color: "var(--foreground)", margin: 0, letterSpacing: "-0.02em", lineHeight: 1.1 }}>
            {(() => {
              const h = new Date().getHours();
              return h < 12 ? "Good Morning" : h < 18 ? "Good Afternoon" : "Good Evening";
            })()}, User
          </h1>
          <p style={{ fontFamily: "var(--font-sans)", fontSize: "0.92rem", color: "var(--muted-foreground)", marginTop: 4, fontWeight: 500 }}>
            Cognitive stamina is at <strong style={{ color: "var(--primary)" }}>{Math.round(battery)}%</strong> · <span style={{ color: fatigueColor, fontWeight: 600 }}>{fatigueLabel} Fatigue</span>
          </p>
        </div>

        {/* Dynamic Wisdom & Live Companion Snippet */}
        <div style={{ flex: 1, minWidth: 280, maxWidth: 440, background: "var(--card)", border: "1px solid var(--border)", borderRadius: "var(--radii-lg)", padding: "14px 18px", boxShadow: "var(--shadow-sm)", display: "flex", flexDirection: "column", gap: 6 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--primary)" }}>
              <Sparkles size={13} />
              <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.6rem", letterSpacing: "0.08em", textTransform: "uppercase", fontWeight: 700 }}>Cognitive Companion</span>
            </div>
            <button
              onClick={() => setDigestOpen(true)}
              style={{ background: "transparent", border: "none", color: "var(--primary)", fontFamily: "var(--font-mono)", fontSize: "0.62rem", fontWeight: 700, cursor: "pointer", display: "flex", alignItems: "center", gap: 3, padding: 0 }}
            >
              Digest <ArrowRight size={11} />
            </button>
          </div>
          <p style={{ fontFamily: "var(--font-sans)", fontStyle: "italic", fontSize: "0.82rem", color: "var(--foreground)", margin: 0, lineHeight: 1.4 }}>
            {companionMessage || `"${WISDOM[wisdomIdx]}"`}
          </p>
        </div>
      </div>

      {/* ══ PROACTIVE INTERVENTION HERO BANNER ═══════════════════════════════ */}
      <AnimatePresence>
        {activeNudge && (
          <motion.div
            initial={{ opacity: 0, y: -12, scale: 0.99 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -10, scale: 0.99 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            style={{
              borderRadius: "var(--radii-lg)",
              padding: "16px 20px",
              background: activeNudge.type === "critical"
                ? "linear-gradient(135deg, rgba(255, 132, 162, 0.15) 0%, var(--card) 100%)"
                : activeNudge.type === "warning"
                ? "linear-gradient(135deg, rgba(255, 201, 126, 0.15) 0%, var(--card) 100%)"
                : "linear-gradient(135deg, rgba(142, 151, 253, 0.15) 0%, var(--card) 100%)",
              border: `1.5px solid ${activeNudge.type === "critical" ? "var(--accent-1, #FF84A2)" : activeNudge.type === "warning" ? "var(--secondary, #FFC97E)" : "var(--primary, #8E97FD)"}`,
              boxShadow: `0 6px 24px ${activeNudge.type === "critical" ? "rgba(255, 132, 162, 0.18)" : "rgba(142, 151, 253, 0.12)"}`,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 16,
              flexWrap: "wrap",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 12, flex: 1, minWidth: 240 }}>
              <div
                style={{
                  width: 38,
                  height: 38,
                  borderRadius: 10,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  background: activeNudge.type === "critical" ? "rgba(255, 132, 162, 0.2)" : activeNudge.type === "warning" ? "rgba(255, 201, 126, 0.2)" : "rgba(142, 151, 253, 0.2)",
                  color: activeNudge.type === "critical" ? "var(--accent-1, #FF84A2)" : activeNudge.type === "warning" ? "#E5A93C" : "var(--primary, #8E97FD)",
                  flexShrink: 0
                }}
              >
                {activeNudge.type === "critical" ? <AlertTriangle size={20} /> : activeNudge.type === "warning" ? <Bell size={20} /> : <Zap size={20} />}
              </div>
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontFamily: "'Nunito', sans-serif", fontSize: "0.9rem", fontWeight: 800, color: "var(--foreground)" }}>
                    {activeNudge.title}
                  </span>
                  <span
                    style={{
                      fontFamily: "'DM Mono', monospace",
                      fontSize: "0.58rem",
                      textTransform: "uppercase",
                      padding: "2px 6px",
                      borderRadius: 4,
                      background: activeNudge.type === "critical" ? "var(--accent-1)" : "var(--primary)",
                      color: "#FFFFFF",
                      fontWeight: 700
                    }}
                  >
                    Action Needed
                  </span>
                </div>
                <div style={{ fontFamily: "'Nunito', sans-serif", fontSize: "0.8rem", color: "var(--muted-foreground)", marginTop: 2 }}>
                  {activeNudge.message}
                </div>
              </div>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
              {activeNudge.actions.map((act) => {
                const isPrimary = act.variant === "primary" || act.action === "take_break" || act.action === "drink_water";
                return (
                  <button
                    key={act.action}
                    onClick={async () => {
                      toast.info(`Executing: ${act.label}`);
                      await handleNudgeAction(act.action, activeNudge.id);
                    }}
                    style={{
                      padding: "7px 14px",
                      borderRadius: "var(--radii-lg)",
                      border: isPrimary ? "none" : "1px solid var(--border)",
                      background: isPrimary ? (activeNudge.type === "critical" ? "var(--accent-1, #FF84A2)" : "var(--primary)") : "var(--muted)",
                      color: isPrimary ? "#FFFFFF" : "var(--foreground)",
                      fontFamily: "'Nunito', sans-serif",
                      fontSize: "0.8rem",
                      fontWeight: 700,
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: 5,
                      boxShadow: isPrimary ? "0 4px 12px rgba(0,0,0,0.12)" : "none",
                      transition: "all 0.15s ease"
                    }}
                  >
                    {act.label}
                  </button>
                );
              })}
              <button
                onClick={() => dismissNudge()}
                title="Dismiss"
                aria-label="Dismiss proactive nudge"
                style={{
                  width: 28,
                  height: 28,
                  borderRadius: "50%",
                  border: "1px solid var(--border)",
                  background: "transparent",
                  color: "var(--muted-foreground)",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  transition: "all 0.15s"
                }}
              >
                <X size={13} />
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ══ COMMAND CENTER 2-COLUMN BALANCED BENTO GRID ═════════════════════ */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(12, 1fr)",
        gap: "24px",
        alignItems: "start"
      }}>

        {/* ── LEFT COLUMN: FOCUS & EXECUTION (SPAN 7) ──────────────────────── */}
        <div style={{ gridColumn: "span 7", display: "flex", flexDirection: "column", gap: "24px" }}>

          {/* 1. UNIFIED FOCUS HERO (Orb Timer + Mode Switcher + Intention) */}
          <motion.div 
            className="card-interactive"
            whileHover={{ y: -3, boxShadow: "var(--shadow-lg)" }}
            style={{
              borderRadius: "var(--radii-lg)", border: "1px solid var(--border)",
              background: "var(--card)", backdropFilter: "blur(16px)",
              padding: "26px 28px", display: "flex", flexDirection: "column", gap: 20
            }}
          >
            {/* Top Row: Focus Header & Active Mode */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <Zap size={14} style={{ color: "var(--primary)" }} />
                <span style={{ fontFamily: "'Nunito', sans-serif", fontSize: "0.72rem", letterSpacing: "0.12em", color: "var(--muted-foreground)", textTransform: "uppercase", fontWeight: 800 }}>
                  Focus Cycle
                </span>
              </div>
              <span style={{ padding: "3px 10px", borderRadius: "var(--radii-full, 9999px)", fontFamily: "'DM Mono', monospace", fontSize: "0.65rem", fontWeight: 700, background: meta.bg, color: meta.color }}>
                {meta.label.toUpperCase()}
              </span>
            </div>

            {/* Middle Row: Glowing Orb Timer + Mode Selector */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 24 }}>
              {/* Glowing Orb */}
              <div style={{ position: "relative", width: 170, height: 170, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                <motion.div
                  animate={{ scale: [1, 1.06, 1], opacity: [0.5, 0.85, 0.5] }}
                  transition={{ repeat: Infinity, duration: 4, ease: "easeInOut" }}
                  style={{
                    position: "absolute", inset: 0, borderRadius: "50%",
                    background: `radial-gradient(circle at 30% 30%, ${meta.color}, color-mix(in srgb, ${meta.color} 30%, transparent))`,
                    boxShadow: `0 0 35px ${meta.color}`,
                    willChange: "transform, opacity",
                    filter: "blur(5px)"
                  }}
                />
                <div style={{ position: "relative", zIndex: 10, textAlign: "center", color: "var(--primary-foreground)", textShadow: "0 2px 10px rgba(0,0,0,0.35)", display: "flex", flexDirection: "column", alignItems: "center", width: "100%", padding: "0 6px" }}>
                  <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "2.3rem", fontWeight: 700, letterSpacing: "-0.04em", lineHeight: 1 }}>
                    {fmt(timerSeconds)}
                  </div>
                  <div style={{ fontFamily: "'Nunito', sans-serif", fontSize: "0.62rem", letterSpacing: "0.14em", textTransform: "uppercase", marginTop: 3, opacity: 0.9, fontWeight: 700 }}>
                    {meta.timerLabel}
                  </div>

                  {/* Active Window Badge */}
                  <div
                    style={{
                      marginTop: 6,
                      padding: "3px 8px",
                      borderRadius: 12,
                      background: "rgba(0, 0, 0, 0.4)",
                      backdropFilter: "blur(6px)",
                      border: `1px solid ${classifiedApp === "work" ? "rgba(142,151,253,0.4)" : classifiedApp === "recharge" ? "rgba(255,201,126,0.4)" : "rgba(255,255,255,0.2)"}`,
                      display: "flex",
                      alignItems: "center",
                      gap: 4,
                      maxWidth: 150,
                      boxSizing: "border-box"
                    }}
                    title={`Active: ${activeApp} (${clsMeta.label})`}
                  >
                    <span style={{ fontSize: "0.68rem", flexShrink: 0 }}>
                      {classifiedApp === "work" ? "💻" : classifiedApp === "recharge" ? "🎮" : "☕"}
                    </span>
                    <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.6rem", color: "#FFFFFF", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: 110 }}>
                      {activeApp || "Detecting..."}
                    </span>
                  </div>
                </div>
              </div>

              {/* Mode Switcher Buttons + Quick Controls */}
              <div style={{ display: "flex", flexDirection: "column", gap: 10, flex: 1 }}>
                {(["work", "recharge"] as AppMode[]).map(m => {
                  const mm = MODE_META[m];
                  const isCur = mode === m;
                  return (
                    <button
                      key={m}
                      onClick={() => onSetMode(m)}
                      style={{
                        padding: "12px 20px",
                        borderRadius: "var(--radii-lg)",
                        border: `1px solid ${isCur ? mm.color : "var(--border)"}`,
                        cursor: "pointer",
                        fontFamily: "var(--font-sans)",
                        fontSize: "0.82rem",
                        fontWeight: 700,
                        letterSpacing: "0.04em",
                        background: isCur ? mm.color : "var(--muted)",
                        color: isCur ? "var(--primary-foreground)" : "var(--foreground)",
                        boxShadow: isCur ? `0 4px 16px color-mix(in srgb, ${mm.color} 35%, transparent)` : "none",
                        transition: "all 0.2s ease",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between"
                      }}
                    >
                      <span>{m === "work" ? "💻 Deep Work" : "🧘 Recharge"}</span>
                      {isCur && <Check size={14} />}
                    </button>
                  );
                })}

                {/* Quick Focus Cycle Actions */}
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 2 }}>
                  {mode === "work" ? (
                    <>
                      <button
                        onClick={() => extendFocus(300)}
                        style={{
                          flex: 1,
                          padding: "6px 10px",
                          borderRadius: "var(--radii-md)",
                          border: "1px solid var(--border)",
                          background: "var(--card)",
                          color: "var(--foreground)",
                          fontSize: "0.68rem",
                          fontFamily: "'DM Mono', monospace",
                          fontWeight: 600,
                          cursor: "pointer",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          gap: 4
                        }}
                        title="Extend current focus sprint by +5 minutes"
                      >
                        <Plus size={11} /> +5m Focus
                      </button>
                      <button
                        onClick={() => takeBreak()}
                        style={{
                          flex: 1,
                          padding: "6px 10px",
                          borderRadius: "var(--radii-md)",
                          border: "1px solid var(--border)",
                          background: "var(--muted)",
                          color: "var(--muted-foreground)",
                          fontSize: "0.68rem",
                          fontFamily: "var(--font-sans)",
                          fontWeight: 600,
                          cursor: "pointer",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          gap: 4
                        }}
                        title="Transition to recharge break"
                      >
                        <Coffee size={11} /> Take Break
                      </button>
                      <button
                        onClick={() => resetTimer()}
                        style={{
                          padding: "6px 8px",
                          borderRadius: "var(--radii-md)",
                          border: "1px solid var(--border)",
                          background: "transparent",
                          color: "var(--muted-foreground)",
                          cursor: "pointer"
                        }}
                        title="Reset current block timer"
                      >
                        <RefreshCw size={11} />
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        onClick={() => startFocus()}
                        style={{
                          flex: 1,
                          padding: "6px 10px",
                          borderRadius: "var(--radii-md)",
                          border: "1px solid var(--primary)",
                          background: "var(--primary)",
                          color: "var(--primary-foreground)",
                          fontSize: "0.68rem",
                          fontFamily: "var(--font-sans)",
                          fontWeight: 700,
                          cursor: "pointer",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          gap: 4
                        }}
                        title="Start a new Deep Work sprint"
                      >
                        <Zap size={11} /> Start Focus
                      </button>
                      <button
                        onClick={() => extendFocus(120)}
                        style={{
                          flex: 1,
                          padding: "6px 10px",
                          borderRadius: "var(--radii-md)",
                          border: "1px solid var(--border)",
                          background: "var(--card)",
                          color: "var(--foreground)",
                          fontSize: "0.68rem",
                          fontFamily: "'DM Mono', monospace",
                          fontWeight: 600,
                          cursor: "pointer",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          gap: 4
                        }}
                        title="Extend recharge break by +2 minutes"
                      >
                        <Plus size={11} /> +2m Rest
                      </button>
                    </>
                  )}
                </div>
              </div>
            </div>

            {/* Bottom Row: Direct Session Intention Input */}
            <div style={{ borderTop: "1px solid var(--border)", paddingTop: 16 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                <span style={{ fontFamily: "var(--font-sans)", fontSize: "0.72rem", letterSpacing: "0.1em", color: "var(--primary)", textTransform: "uppercase", fontWeight: 800 }}>
                  Block Intention
                </span>
                {intentionSaved && (
                  <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.62rem", color: "var(--primary)", fontWeight: 600 }}>
                    ✓ Saved
                  </span>
                )}
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <input
                  value={intention}
                  onChange={e => { setIntention(e.target.value); setIntentionSaved(false); }}
                  onKeyDown={e => e.key === "Enter" && saveIntention()}
                  placeholder="What is your primary milestone for this block?"
                  style={{
                    flex: 1, outline: "none", background: "var(--muted)", border: "1px solid var(--border)",
                    borderRadius: "var(--radii-lg)", padding: "10px 14px", fontFamily: "var(--font-sans)",
                    fontSize: "0.88rem", color: "var(--foreground)", transition: "border-color 0.2s"
                  }}
                />
                <button
                  onClick={saveIntention}
                  title="Save Intention"
                  style={{
                    height: 40, padding: "0 16px", borderRadius: "var(--radii-lg)", border: "none",
                    cursor: "pointer", flexShrink: 0, display: "flex", alignItems: "center", gap: 6,
                    fontFamily: "var(--font-sans)", fontSize: "0.8rem", fontWeight: 700,
                    background: intentionSaved ? "var(--primary)" : "var(--primary-alpha-12)",
                    color: intentionSaved ? "var(--primary-foreground)" : "var(--primary)",
                    transition: "all 0.2s"
                  }}
                >
                  <Check size={15} />
                  <span>Set Goal</span>
                </button>
              </div>
            </div>
          </motion.div>

          {/* 2. STAMINA FORECAST & COGNITIVE AUTOPILOT */}
          <motion.div 
            className="card-interactive"
            whileHover={{ y: -3, boxShadow: "var(--shadow-lg)" }}
            style={{
              borderRadius: "var(--radii-lg)", border: "1px solid var(--border)",
              background: "var(--card)", backdropFilter: "blur(16px)",
              padding: "24px 28px", display: "flex", flexDirection: "column", gap: 18
            }}
          >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <Activity size={14} style={{ color: "var(--primary)" }} />
                <span style={{ fontFamily: "'Nunito', sans-serif", fontSize: "0.75rem", letterSpacing: "0.12em", color: "var(--muted-foreground)", textTransform: "uppercase", fontWeight: 800 }}>
                  Stamina Forecast (3h)
                </span>
              </div>
              <span style={{ padding: "4px 12px", borderRadius: "var(--radii-full, 9999px)", fontFamily: "'DM Mono', monospace", fontSize: "0.72rem", background: `color-mix(in srgb, ${forecastColor} 12%, transparent)`, color: forecastColor, fontWeight: 700 }}>
                {forecastEnd}% at +3h
              </span>
            </div>

            <ResponsiveContainer width="100%" height={110}>
              <LineChart data={FORECAST} margin={{ top: 8, right: 8, bottom: 0, left: -24 }}>
                <Tooltip content={<ForecastTip />} />
                <Line type="monotone" dataKey="v" stroke={forecastColor} strokeWidth={3.5} dot={false}
                  activeDot={{ r: 5, fill: forecastColor, stroke: "var(--card)", strokeWidth: 2 }}
                />
              </LineChart>
            </ResponsiveContainer>

            <div style={{ display: "flex", justifyContent: "space-between", paddingLeft: 8, paddingRight: 8 }}>
              {FORECAST.map(d => (
                <span key={d.t} style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.62rem", color: "var(--muted-foreground)", fontWeight: 600 }}>{d.t}</span>
              ))}
            </div>

            {/* Cognitive Autopilot Integrated Accordion */}
            <div style={{ borderTop: "1px solid var(--border)", paddingTop: 14 }}>
              <button
                onClick={() => setAutopilotOpen(o => !o)}
                style={{ width: "100%", display: "flex", alignItems: "center", background: "transparent", border: "none", cursor: "pointer", gap: 10, padding: 0 }}
              >
                <Brain size={16} style={{ color: autopilot ? "var(--primary)" : "var(--muted-foreground)", flexShrink: 0 }} />
                <span style={{ fontFamily: "'Nunito', sans-serif", fontSize: "0.78rem", letterSpacing: "0.1em", color: "var(--foreground)", textTransform: "uppercase", fontWeight: 800 }}>
                  Cognitive Autopilot
                </span>
                <span style={{
                  padding: "2px 8px", borderRadius: "var(--radii-sm)", fontFamily: "'DM Mono', monospace", fontSize: "0.6rem", fontWeight: 700,
                  background: autopilot ? "var(--primary-alpha-12)" : "var(--muted)", color: autopilot ? "var(--primary)" : "var(--muted-foreground)",
                }}>{autopilot ? "ACTIVE" : "PAUSED"}</span>

                {!autopilotOpen && (
                  <div style={{ display: "flex", alignItems: "center", gap: 10, marginLeft: "auto", marginRight: 8 }}>
                    <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.68rem", color: fatigueColor, fontWeight: 600 }}>⚡ {fatigue}% {fatigueLabel}</span>
                    <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.68rem", color: "var(--primary)", fontWeight: 600 }}>{Math.floor(adaptedWorkSecs / 60)}m block</span>
                  </div>
                )}

                <div style={{ marginLeft: autopilotOpen ? "auto" : 0, transform: autopilotOpen ? "rotate(180deg)" : "rotate(0deg)", transition: "transform 0.25s ease" }}>
                  <ChevronDown size={16} style={{ color: "var(--muted-foreground)" }} />
                </div>
              </button>

              {autopilotOpen && (
                <div style={{ display: "flex", flexDirection: "column", gap: 16, paddingTop: 16 }}>
                  {/* Autopilot stat tiles */}
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10 }}>
                    {[
                      { Icon: Zap,     label: "Fatigue",      value: fatigueLabel,                          sub: `${fatigue}/100`,                                   color: fatigueColor },
                      { Icon: Clock,   label: "Work Block",   value: `${Math.floor(adaptedWorkSecs / 60)}m`, sub: workReduction > 0 ? `−${workReduction}m` : "Baseline", color: "var(--primary)" },
                      { Icon: Clock,   label: "Rest Block",   value: `${Math.floor(adaptedRestSecs / 60)}m`, sub: restExtension > 0 ? `+${restExtension}m` : "Baseline", color: "var(--primary)" },
                      { Icon: Battery, label: "Rate",        value: mode === "work" ? `−${(0.5 + fatigue * 0.01).toFixed(1)}%/m` : `+${mode === "rest" ? "1.2" : "0.4"}%/m`, sub: mode === "work" ? "Drain" : "Charge", color: mode === "work" ? "var(--accent-1)" : "var(--primary)" },
                    ].map(({ Icon, label, value, sub, color }) => (
                      <div key={label} style={{ padding: "10px 12px", borderRadius: "var(--radii-md)", background: "var(--muted)", border: "1px solid var(--border)" }}>
                        <Icon size={13} style={{ color, marginBottom: 4 }} />
                        <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.88rem", color: "var(--foreground)", fontWeight: 600 }}>{value}</div>
                        <div style={{ fontFamily: "'Nunito', sans-serif", fontSize: "0.68rem", color: "var(--muted-foreground)", fontWeight: 700 }}>{label}</div>
                        <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.58rem", color }}>{sub}</div>
                      </div>
                    ))}
                  </div>

                  {/* Sliders */}
                  <div style={{ display: "flex", gap: 20 }}>
                    {[
                      { label: "Energy Level",    value: energy,   set: onSetEnergy,   color: "var(--primary)" },
                      { label: "Mental Friction", value: friction, set: onSetFriction, color: "var(--secondary)" },
                    ].map(({ label, value, set, color }) => (
                      <div key={label} style={{ flex: 1 }}>
                        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                          <span style={{ fontFamily: "'Nunito', sans-serif", fontSize: "0.74rem", color: "var(--muted-foreground)", fontWeight: 700 }}>{label}</span>
                          <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.74rem", color, fontWeight: 600 }}>{value}/5</span>
                        </div>
                        <input type="range" min={1} max={5} step={1} value={value} onChange={e => set(Number(e.target.value))}
                          className="w-full h-2 rounded-full appearance-none outline-none cursor-pointer"
                          style={{ accentColor: color, background: `linear-gradient(to right, ${color} ${((value - 1) / 4) * 100}%, var(--muted) ${((value - 1) / 4) * 100}%)` }}
                        />
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </motion.div>

          {/* 3. TASK PLANNER */}
          <TaskPlanner />
        </div>

        {/* ── RIGHT COLUMN: TELEMETRY & HABIT CENTER (SPAN 5) ──────────────── */}
        <div style={{ gridColumn: "span 5", display: "flex", flexDirection: "column", gap: "24px" }}>

          {/* 1. MENTAL BATTERY & FATIGUE STATUS */}
          <motion.div 
            className="card-interactive"
            whileHover={{ y: -3, boxShadow: "var(--shadow-lg)" }}
            style={{
              borderRadius: "var(--radii-lg)", border: "1px solid var(--border)",
              background: "var(--card)", backdropFilter: "blur(16px)",
              padding: "24px 26px", display: "flex", flexDirection: "column", gap: 16
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
              <div>
                <div style={{ fontFamily: "var(--font-sans)", fontSize: "3rem", fontWeight: 800, color: "var(--foreground)", lineHeight: 1, letterSpacing: "-0.03em" }}>
                  {Math.round(battery)}<span style={{ fontSize: "1.4rem", color: "var(--muted-foreground)" }}>%</span>
                </div>
                <div style={{ fontFamily: "var(--font-sans)", fontSize: "0.75rem", color: "var(--muted-foreground)", letterSpacing: "0.1em", textTransform: "uppercase", marginTop: 4, fontWeight: 700 }}>
                  Mental Battery Level
                </div>
              </div>
              <div style={{ width: 44, height: 44, borderRadius: "var(--radii-md)", background: "var(--primary-alpha-8)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                <Battery size={24} style={{ color: battery > 40 ? "var(--primary)" : "var(--accent-1)" }} />
              </div>
            </div>

            {/* Battery Segments */}
            <div style={{ display: "flex", gap: 6 }}>
              {Array.from({ length: SEGMENTS }).map((_, i) => (
                <div key={`b-${i}`} style={{
                  flex: 1, height: 8, borderRadius: 4, transition: "all 0.5s cubic-bezier(0.4,0,0.2,1)",
                  background: i < filledSegs ? (battery > 40 ? "var(--primary)" : "var(--accent-1)") : "var(--muted)",
                  boxShadow: i < filledSegs ? `0 0 10px color-mix(in srgb, ${battery > 40 ? "var(--primary)" : "var(--accent-1)"} 50%, transparent)` : "none",
                }} />
              ))}
            </div>

            {/* Fatigue sub-panel */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderTop: "1px solid var(--border)", paddingTop: 12 }}>
              <span style={{ fontFamily: "var(--font-sans)", fontSize: "0.78rem", color: "var(--muted-foreground)", fontWeight: 600 }}>Fatigue Load</span>
              <span style={{ padding: "4px 10px", borderRadius: "var(--radii-full, 9999px)", fontFamily: "var(--font-mono)", fontSize: "0.68rem", background: "var(--muted)", color: fatigueColor, fontWeight: 700, border: "1px solid var(--border)" }}>
                {fatigueLabel} ({fatigue}%)
              </span>
            </div>
          </motion.div>

          {/* 2. ACTIVE WINDOW & REAL-TIME CLASSIFIER */}
          <motion.div 
            className="card-interactive"
            whileHover={{ y: -3, boxShadow: "var(--shadow-lg)" }}
            style={{
              borderRadius: "var(--radii-lg)", border: "1px solid var(--border)",
              background: "var(--card)", backdropFilter: "blur(16px)",
              padding: "22px 24px", display: "flex", flexDirection: "column", gap: 14,
              outline: classFlash ? `2px solid color-mix(in srgb, ${clsMeta.color} 50%, transparent)` : "2px solid transparent",
              transition: "outline 0.3s ease"
            }}
          >
            <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
              <div style={{ width: 42, height: 42, borderRadius: "var(--radii-md)", background: clsMeta.bg, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                <MonitorCheck size={20} style={{ color: clsMeta.color, transition: "color 0.4s ease" }} />
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                  <span style={{ fontFamily: "var(--font-sans)", fontSize: "0.7rem", letterSpacing: "0.1em", color: "var(--muted-foreground)", textTransform: "uppercase", fontWeight: 800 }}>Active Window</span>
                  <span style={{ padding: "2px 8px", borderRadius: "var(--radii-sm)", fontFamily: "var(--font-mono)", fontSize: "0.62rem", background: clsMeta.bg, color: clsMeta.color, fontWeight: 700 }}>
                    {clsMeta.label.toUpperCase()}
                  </span>
                </div>
                <div style={{ fontFamily: "var(--font-sans)", fontSize: "0.95rem", color: "var(--foreground)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", fontWeight: 700 }} title={activeApp}>
                  {activeApp}
                </div>
              </div>
            </div>

            {/* Quick 1-Click Classification Buttons */}
            <div style={{ display: "flex", gap: 6 }}>
              {(["work", "recharge", "neutral"] as AppClass[]).map(cls => {
                const cm = CLASS_META[cls];
                const isSelected = classifiedApp === cls;
                return (
                  <button key={cls} 
                    onClick={async () => {
                      await onOverrideClassify(cls);
                      const targetName = activeProcess && activeProcess !== "None" && activeProcess !== "Detecting..." ? activeProcess : activeApp;
                      toast.success(`Classified as ${cm.label}`, { description: `Saved rule: ${targetName} -> ${cm.label}` });
                    }}
                    style={{
                      flex: 1, padding: "8px 0", borderRadius: "var(--radii-md)", cursor: "pointer", fontFamily: "'Nunito', sans-serif", fontSize: "0.74rem", fontWeight: 700,
                      background: isSelected ? (cls === "work" ? "var(--primary)" : cls === "recharge" ? "var(--secondary)" : "var(--muted)") : "transparent",
                      color: isSelected ? (cls === "work" ? "var(--primary-foreground)" : cls === "recharge" ? "var(--secondary-foreground)" : "var(--foreground)") : "var(--muted-foreground)",
                      border: `1px solid ${isSelected ? (cls === "work" ? "var(--primary)" : cls === "recharge" ? "var(--secondary)" : "var(--border)") : "var(--border)"}`,
                      transition: "all 0.2s",
                      display: "flex", alignItems: "center", justifyContent: "center", gap: 4
                    }}>
                    <span>{cls === "work" ? "💻" : cls === "recharge" ? "🎮" : "☕"}</span>
                    <span>{cm.label}</span>
                  </button>
                );
              })}
            </div>
          </motion.div>

          {/* 3. SMART FOCUS TIMER */}
          <FocusTimer />

          {/* 4. VITALITY & HABITS */}
          <VitalityTracker
            sleep={sleep} hydration={hydration}
            sleepTarget={settings?.daily_sleep_target ?? 8.0}
            stepsTarget={settings?.daily_step_target ?? 10000}
            waterTarget={settings?.hydration_target ?? 8}
            onSetSleep={onSetSleep} onSetHydration={onSetHydration}
          />

          {/* 5. QUICK CHECK-IN & GRATITUDE */}
          <CheckInGratitude currentFriction={friction} sleepTarget={settings?.daily_sleep_target ?? 8.0} />
        </div>

      </div>

      {/* Daily Digest Modal */}
      <DailyDigest
        isOpen={digestOpen}
        onClose={() => setDigestOpen(false)}
        todayWorkSeconds={todayWork}
        todayRechargeSeconds={todayRecharge}
        focusScore={focusScore}
        streakDays={streakDays}
      />
    </div>
  );
}
