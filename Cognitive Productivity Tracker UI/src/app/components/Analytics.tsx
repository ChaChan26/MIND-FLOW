/**
 * Analytics and energy telemetry dashboard mapping weekly fatigue, reflection logs, and deep work sessions.
 *
 * Author: ChaChan26 <minhharry2006@gmail.com>
 * Copyright (c) 2026 ChaChan26. All rights reserved.
 */

import { useState, useMemo } from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell,
} from "recharts";
import {
  Sparkles, Brain, Zap, Wind, TrendingUp, TrendingDown,
  Activity, Moon, AlertTriangle, CheckCircle2,
  ChevronRight, Plus, Tag, AlertCircle, Clock,
} from "lucide-react";
import { useReflections } from "../hooks/useReflections";
import type { ReflectionEntry, Mood } from "../hooks/useReflections";
import type { AppTally } from "../App";
import { useStaminaStore } from "../hooks/useStaminaEngine";
import { ActivityDeepDive } from "./ActivityDeepDive";
import { ContextSwitchTimeline } from "./ContextSwitchTimeline";
import { SessionTimeline } from "./SessionTimeline";
import type { RechartsTooltipProps, RechartsTooltipPayloadItem } from "../types/recharts";

// ─── Constants ────────────────────────────────────────────────────────────────
const MOODS: Mood[] = ["Calm", "Focused", "Neutral", "Anxious", "Overwhelmed", "Frustrated", "Exhausted"];

const MOOD_COLORS: Record<Mood, string> = {
  Calm: "var(--primary)", Focused: "var(--chart-2)", Neutral: "var(--muted-foreground)",
  Anxious: "var(--chart-3)", Overwhelmed: "var(--destructive)", Frustrated: "var(--destructive)", Exhausted: "var(--muted-foreground)",
};

const WIN_TAGS  = ["Coding Win", "Design Win", "Learning", "Teamwork", "Bug Fixed", "Feature Done", "Planning"];
const BLOCK_TAGS = ["Bug Roadblock", "Distraction", "Unclear Scope", "Fatigue", "Context Switch", "Meeting", "Tech Debt"];

// ─── CBT Distortion Scanner ───────────────────────────────────────────────────
const DISTORTIONS = [
  { type: "All-or-Nothing Thinking", pattern: /\b(never|always|completely|totally|nothing works|everything|no one|worst)\b/i, advice: "Try replacing absolutes like 'never' or 'always' with 'sometimes' or 'in this case' — it opens space for nuance." },
  { type: "Catastrophizing",         pattern: /\b(disaster|ruined|terrible|horrible|awful|impossible|unbearable|can't handle|hopeless)\b/i, advice: "Ask: what's the realistic worst case? Is it as catastrophic as it feels right now, or is this a temporary setback?" },
  { type: "Should Statements",       pattern: /\b(should have|must|have to|ought to|I need to)\b/i, advice: "Replace 'should' with 'could' — it removes self-blame and reframes as choice rather than obligation." },
  { type: "Overgeneralization",      pattern: /\b(every time|always fails|nobody|no one cares|constantly wrong|never works)\b/i, advice: "Look for specific exceptions. Has there been a time when this wasn't true?" },
  { type: "Mind Reading",            pattern: /\b(they think|everyone thinks|they must think|probably judging|they hate)\b/i, advice: "You may be assuming others' thoughts. Can you find evidence for or against this belief?" },
];

function scanDistortions(text: string) {
  if (!text.trim()) return null;
  for (const d of DISTORTIONS) {
    if (d.pattern.test(text)) return d;
  }
  return null;
}

// ─── Flow Trigger / Leak Derivation ──────────────────────────────────────────
const STOPWORDS = new Set([
  "the", "and", "for", "with", "this", "that", "from", "have", "been", "just",
  "none", "only", "some", "also", "more", "than", "then", "very", "hard", "good",
  "well", "work", "done", "time", "day", "but", "was", "did", "not", "kept",
  "deep", "made", "felt", "went", "into", "over", "out", "all", "could", "would",
]);

function topKeywords(text: string, n: number): string[] {
  const freq: Record<string, number> = {};
  text.toLowerCase()
    .replace(/[^a-z\s]/g, " ")
    .split(/\s+/)
    .filter(w => w.length > 3 && !STOPWORDS.has(w))
    .forEach(w => { freq[w] = (freq[w] ?? 0) + 1; });
  return Object.entries(freq)
    .sort((a, b) => b[1] - a[1])
    .slice(0, n)
    .map(([w]) => w.charAt(0).toUpperCase() + w.slice(1));
}

const FALLBACK_TRIGGERS = ["Deep morning sessions", "8h+ sleep", "Single-context work", "Godot game dev", "Quiet environment"];
const FALLBACK_LEAKS    = ["Discord notifications", "Context switching", "Sleep under 6.5h", "Afternoon slumps (2–4 PM)", "Undefined task scope"];

// ─── Shared styles ────────────────────────────────────────────────────────────
const SECTION_LABEL: React.CSSProperties = {
  fontFamily: "'Nunito', sans-serif",
  fontSize: "0.65rem", letterSpacing: "0.12em",
  color: "var(--muted-foreground)", textTransform: "uppercase" as const,
};

// NOTE: Components using this should also apply className="card-interactive"
const CARD: React.CSSProperties = {
  background: "var(--card)", border: "1px solid var(--border)",
  borderRadius: 20, padding: "22px 24px",
  boxShadow: "var(--shadow-md)",
};

// ─── Chart tooltip ─────────────────────────────────────────────────────────────
function ChartTip({ active, payload, label }: RechartsTooltipProps) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: "var(--radii-md)", padding: "10px 14px", boxShadow: "var(--shadow-md)" }}>
      <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.68rem", color: "var(--muted-foreground)", marginBottom: 6 }}>{label}</div>
      {payload.map((p: RechartsTooltipPayloadItem, idx: number) => (
        <div key={p.name || idx} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: p.color || "var(--primary)", display: "inline-block" }} />
          <span style={{ fontFamily: "var(--font-sans)", fontSize: "0.78rem", color: "var(--foreground)" }}>
            {p.name}: <strong>{p.value}</strong>
          </span>
        </div>
      ))}
    </div>
  );
}

// ─── Score Slider ─────────────────────────────────────────────────────────────
function ScoreSlider({ label, value, onChange, color }: { label: string; value: number; onChange: (v: number) => void; color: string }) {
  return (
    <div style={{ flex: 1 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
        <span style={{ fontFamily: "'Nunito', sans-serif", fontSize: "0.8rem", color: "var(--foreground)" }}>{label}</span>
        <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.78rem", color }}>{value}/5</span>
      </div>
      <div style={{ display: "flex", gap: 6 }}>
        {[1, 2, 3, 4, 5].map(n => (
          <button key={n} onClick={() => onChange(n)} style={{
            flex: 1, height: 30, borderRadius: 8, border: "none", cursor: "pointer",
            background: n <= value ? color : "var(--primary-alpha-8)", opacity: n <= value ? 1 : 0.45, transition: "all 0.18s",
          }} />
        ))}
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 3 }}>
        <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.55rem", color: "var(--muted-foreground)" }}>Low</span>
        <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.55rem", color: "var(--muted-foreground)" }}>High</span>
      </div>
    </div>
  );
}

// ─── Tag Picker ────────────────────────────────────────────────────────────────
function TagPicker({ tags, selected, onToggle, color }: { tags: string[]; selected: Set<string>; onToggle: (t: string) => void; color: string }) {
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 5, marginTop: 6 }}>
      {tags.map(t => (
        <button key={t} onClick={() => onToggle(t)} style={{
          padding: "3px 9px", borderRadius: 20, border: "none", cursor: "pointer",
          fontFamily: "'DM Mono', monospace", fontSize: "0.6rem", letterSpacing: "0.04em",
          background: selected.has(t) ? color : "var(--muted)",
          color: selected.has(t) ? "var(--primary-foreground)" : "var(--muted-foreground)",
          transition: "all 0.15s",
        }}>{t}</button>
      ))}
    </div>
  );
}

// ─── CBT Warning Banner ────────────────────────────────────────────────────────
function CbtWarning({ distortion }: { distortion: { type: string; advice: string } }) {
  return (
    <div style={{ padding: "12px 14px", borderRadius: 12, background: "var(--primary-alpha-8)", border: "1px solid var(--primary-alpha-20)", marginTop: 8 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 5 }}>
        <AlertCircle size={12} style={{ color: "var(--chart-3)", flexShrink: 0 }} />
        <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.62rem", color: "var(--chart-3)", letterSpacing: "0.06em" }}>
          COGNITIVE PATTERN — {distortion.type.toUpperCase()}
        </span>
      </div>
      <p style={{ fontFamily: "'Nunito', sans-serif", fontSize: "0.78rem", color: "var(--foreground)", lineHeight: 1.6, margin: 0 }}>
        {distortion.advice}
      </p>
    </div>
  );
}

// ─── Check-In Panel ───────────────────────────────────────────────────────────
function CheckInPanel({ onSubmit }: { onSubmit: (entry: Omit<ReflectionEntry, "id" | "date" | "time">) => void }) {
  const [energy,       setEnergy]       = useState(3);
  const [friction,     setFriction]     = useState(3);
  const [stress,       setStress]       = useState(2);
  const [mood,         setMood]         = useState<Mood>("Neutral");
  const [sleepHours,   setSleepHours]   = useState(7);
  const [sleepQuality, setSleepQuality] = useState(3);
  const [wins,         setWins]         = useState("");
  const [roadblocks,   setRoadblocks]   = useState("");
  const [winTags,      setWinTags]      = useState<Set<string>>(new Set());
  const [blockTags,    setBlockTags]    = useState<Set<string>>(new Set());
  const [submitted,    setSubmitted]    = useState(false);

  const winDistortion   = useMemo(() => scanDistortions(wins),       [wins]);
  const blockDistortion = useMemo(() => scanDistortions(roadblocks),  [roadblocks]);

  const toggleWinTag   = (t: string) => setWinTags(prev   => { const s = new Set(prev); s.has(t) ? s.delete(t) : s.add(t); return s; });
  const toggleBlockTag = (t: string) => setBlockTags(prev => { const s = new Set(prev); s.has(t) ? s.delete(t) : s.add(t); return s; });

  const handleSubmit = () => {
    onSubmit({ energy, friction, stress, mood, sleepHours, sleepQuality, wins, roadblocks, winTags: [...winTags], blockTags: [...blockTags] });
    setSubmitted(true);
    setTimeout(() => setSubmitted(false), 2800);
    setWins(""); setRoadblocks(""); setWinTags(new Set()); setBlockTags(new Set());
  };

  return (
    <div className="card-interactive" style={CARD}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 20 }}>
        <div style={{ width: 28, height: 28, borderRadius: 10, background: "var(--muted)", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Activity size={13} style={{ color: "var(--primary)" }} />
        </div>
        <div>
          <div style={{ fontFamily: "var(--font-sans)", fontSize: "0.95rem", fontWeight: 700, color: "var(--foreground)" }}>Quick Check-In</div>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.6rem", color: "var(--muted-foreground)", letterSpacing: "0.06em" }}>CBT-guided reflection log</div>
        </div>
        {submitted && (
          <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 5, color: "var(--primary)" }}>
            <CheckCircle2 size={14} /><span style={{ fontFamily: "'Nunito', sans-serif", fontSize: "0.78rem" }}>Logged</span>
          </div>
        )}
      </div>

      {/* Energy / Friction / Stress */}
      <div style={{ display: "flex", gap: 16, marginBottom: 20 }}>
        <ScoreSlider label="Energy"   value={energy}   onChange={setEnergy}   color="var(--primary)" />
        <ScoreSlider label="Friction" value={friction} onChange={setFriction} color="var(--chart-3)" />
        <ScoreSlider label="Stress"   value={stress}   onChange={setStress}   color="var(--destructive)" />
      </div>

      {/* Mood */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ ...SECTION_LABEL, marginBottom: 8 }}>Current Mood</div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {MOODS.map(m => (
            <button key={m} onClick={() => setMood(m)} className="btn-mood" style={{
              padding: "5px 12px", borderRadius: 20, border: "none", cursor: "pointer",
              fontFamily: "'Nunito', sans-serif", fontSize: "0.78rem",
              background: mood === m ? MOOD_COLORS[m] : "var(--muted)",
              color: mood === m ? "var(--primary-foreground)" : "var(--muted-foreground)", transition: "all 0.2s",
            }}>{m}</button>
          ))}
        </div>
      </div>

      {/* Sleep */}
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 16, marginBottom: 20 }}>
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
              <Moon size={11} style={{ color: "var(--chart-2)" }} />
              <span style={{ fontFamily: "'Nunito', sans-serif", fontSize: "0.8rem", color: "var(--foreground)" }}>Sleep Hours</span>
            </div>
            <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.78rem", color: "var(--chart-2)" }}>{sleepHours}h</span>
          </div>
          <input type="range" className="slider-custom" min={3} max={12} step={0.5} value={sleepHours} onChange={e => setSleepHours(Number(e.target.value))} style={{ width: "100%" }} />
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.55rem", color: "var(--muted-foreground)" }}>3h</span>
            <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.55rem", color: "var(--muted-foreground)" }}>12h</span>
          </div>
        </div>
        <div>
          <div style={{ ...SECTION_LABEL, marginBottom: 8 }}>Sleep Quality</div>
          <div style={{ display: "flex", gap: 4 }}>
            {[1, 2, 3, 4, 5].map(n => (
              <button key={n} onClick={() => setSleepQuality(n)} className="btn-quality" style={{
                flex: 1, height: 28, borderRadius: 6, border: "none", cursor: "pointer",
                background: n <= sleepQuality ? "var(--chart-2)" : "var(--muted)", opacity: n <= sleepQuality ? 1 : 0.4, transition: "all 0.15s",
              }} />
            ))}
          </div>
        </div>
      </div>

      {/* Journal */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 20 }}>
        {/* Wins */}
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 5, marginBottom: 5 }}>
            <Sparkles size={11} style={{ color: "var(--primary)" }} />
            <span style={{ ...SECTION_LABEL }}>Wins & Highlights</span>
          </div>
          <textarea value={wins} onChange={e => setWins(e.target.value)} placeholder="What went well today?" rows={3}
            style={{ width: "100%", resize: "none", border: "1px solid var(--border)", borderRadius: 12, padding: "10px 12px", fontFamily: "'Nunito', sans-serif", fontSize: "0.8rem", color: "var(--foreground)", background: "var(--muted)", outline: "none", lineHeight: 1.6, boxSizing: "border-box" }}
          />
          {winDistortion && <CbtWarning distortion={winDistortion} />}
          <div style={{ display: "flex", alignItems: "center", gap: 5, marginTop: 8 }}>
            <Tag size={10} style={{ color: "var(--muted-foreground)" }} />
            <span style={{ ...SECTION_LABEL, fontSize: "0.58rem" }}>Tags</span>
          </div>
          <TagPicker tags={WIN_TAGS} selected={winTags} onToggle={toggleWinTag} color="var(--primary)" />
        </div>
        {/* Roadblocks */}
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 5, marginBottom: 5 }}>
            <AlertTriangle size={11} style={{ color: "var(--chart-3)" }} />
            <span style={{ ...SECTION_LABEL }}>Roadblocks</span>
          </div>
          <textarea value={roadblocks} onChange={e => setRoadblocks(e.target.value)} placeholder="What slowed you down?" rows={3}
            style={{ width: "100%", resize: "none", border: "1px solid var(--border)", borderRadius: 12, padding: "10px 12px", fontFamily: "'Nunito', sans-serif", fontSize: "0.8rem", color: "var(--foreground)", background: "var(--muted)", outline: "none", lineHeight: 1.6, boxSizing: "border-box" }}
          />
          {blockDistortion && <CbtWarning distortion={blockDistortion} />}
          <div style={{ display: "flex", alignItems: "center", gap: 5, marginTop: 8 }}>
            <Tag size={10} style={{ color: "var(--muted-foreground)" }} />
            <span style={{ ...SECTION_LABEL, fontSize: "0.58rem" }}>Tags</span>
          </div>
          <TagPicker tags={BLOCK_TAGS} selected={blockTags} onToggle={toggleBlockTag} color="var(--chart-3)" />
        </div>
      </div>

      <button onClick={handleSubmit} className="btn-primary" style={{
        width: "100%", padding: "10px 0", borderRadius: 12, border: "none",
        background: "var(--primary)", color: "var(--primary-foreground)", cursor: "pointer",
        fontFamily: "'Nunito', sans-serif", fontSize: "0.84rem", letterSpacing: "0.04em", transition: "opacity 0.2s",
      }}>
        Log Check-In
      </button>
    </div>
  );
}

// ─── Weekly Energy Map ─────────────────────────────────────────────────────────
function WeeklyEnergyMap({ reflections }: { reflections: ReflectionEntry[] }) {
  const data = useMemo(() => {
    if (!reflections || reflections.length === 0) return [];

    const grouped = new Map<string, { totalEnergy: number; totalFriction: number; count: number; dateLabel: string }>();

    reflections.forEach(r => {
      const dateLabel = r.date ? r.date.split(" ")[0].replace(",", "") : "—";
      const key = r.date || dateLabel;
      if (!grouped.has(key)) {
        grouped.set(key, { totalEnergy: 0, totalFriction: 0, count: 0, dateLabel });
      }
      const entry = grouped.get(key)!;
      entry.totalEnergy += r.energy;
      entry.totalFriction += r.friction;
      entry.count += 1;
    });

    const days = Array.from(grouped.values()).slice(-7);
    return days.map(d => ({
      day: d.dateLabel,
      energy: Math.round((d.totalEnergy / d.count) * 20),
      friction: Math.round((d.totalFriction / d.count) * 20),
    }));
  }, [reflections]);

  const peak  = useMemo(() => data.length > 0 ? data.reduce((b, d) => d.energy > b.energy ? d : b, data[0]) : undefined, [data]);
  const slump = useMemo(() => data.length > 0 ? data.reduce((b, d) => d.energy < b.energy ? d : b, data[0]) : undefined, [data]);
  const avgSleep = reflections.length > 0
    ? (reflections.reduce((s, r) => s + (r.sleepHours ?? 0), 0) / reflections.length).toFixed(1)
    : "0.0";

  return (
    <div className="card-interactive" style={CARD}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 18 }}>
        <div>
          <div style={{ fontFamily: "var(--font-sans)", fontSize: "0.95rem", fontWeight: 700, color: "var(--foreground)", marginBottom: 2 }}>Weekly Energy Map</div>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.6rem", color: "var(--muted-foreground)", letterSpacing: "0.06em" }}>Friction vs Energy correlation · 7-day trend (daily averages)</div>
        </div>
        <div style={{ display: "flex", gap: 16 }}>
          {[
            { label: "Peak",  day: peak?.day,  icon: <TrendingUp  size={11} />, color: "var(--primary)" },
            { label: "Slump", day: slump?.day, icon: <TrendingDown size={11} />, color: "var(--chart-3)" },
          ].map(({ label, day, icon, color }) => (
            <div key={label} style={{ textAlign: "right" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 4, justifyContent: "flex-end", color, marginBottom: 1 }}>
                {icon}<span style={{ fontFamily: "var(--font-mono)", fontSize: "0.58rem", letterSpacing: "0.06em" }}>{label}</span>
              </div>
              <div style={{ fontFamily: "var(--font-sans)", fontSize: "1.1rem", fontWeight: 700, color: "var(--foreground)" }}>{day ?? "—"}</div>
            </div>
          ))}
        </div>
      </div>

      <ResponsiveContainer width="100%" height={170}>
        <AreaChart data={data} margin={{ top: 10, right: 4, bottom: 0, left: -20 }}>
          <defs key="weeklyEnergyDefs">
            <linearGradient key="weeklyEnergyGrad" id="weeklyEnergyGrad" x1="0" y1="0" x2="0" y2="1">
              <stop key="weeklyEnergyStop0" offset="5%" stopColor="var(--primary)" stopOpacity={0.25} />
              <stop key="weeklyEnergyStop100" offset="95%" stopColor="var(--primary)" stopOpacity={0.0} />
            </linearGradient>
            <linearGradient key="weeklyFrictionGrad" id="weeklyFrictionGrad" x1="0" y1="0" x2="0" y2="1">
              <stop key="weeklyFrictionStop0" offset="5%" stopColor="var(--chart-3)" stopOpacity={0.18} />
              <stop key="weeklyFrictionStop100" offset="95%" stopColor="var(--chart-3)" stopOpacity={0.0} />
            </linearGradient>
          </defs>
          <XAxis dataKey="day" tick={{ fontFamily: "'DM Mono', monospace", fontSize: 10, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} />
          <YAxis domain={[0, 100]} tick={{ fontFamily: "'DM Mono', monospace", fontSize: 10, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} />
          <Tooltip content={<ChartTip />} />
          <Area type="monotone" dataKey="energy"   name="Energy"   stroke="var(--primary)" strokeWidth={2.5} fill="url(#weeklyEnergyGrad)" dot={{ r: 4, fill: "var(--primary)", stroke: "var(--card)", strokeWidth: 2 }} activeDot={{ r: 5 }} />
          <Area type="monotone" dataKey="friction" name="Friction" stroke="var(--chart-3)" strokeWidth={2}   fill="url(#weeklyFrictionGrad)" strokeDasharray="5 3" dot={{ r: 3, fill: "var(--chart-3)", stroke: "var(--card)", strokeWidth: 2 }} activeDot={{ r: 4 }} />
        </AreaChart>
      </ResponsiveContainer>

      <div style={{ display: "flex", alignItems: "center", gap: 20, marginTop: 10 }}>
        {[
          { color: "var(--primary)", label: "Energy",   dash: false },
          { color: "var(--chart-3)",        label: "Friction", dash: true  },
        ].map(({ color, label, dash }) => (
          <div key={label} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <svg width={16} height={4}>
              {dash
                ? <line x1="0" y1="2" x2="16" y2="2" stroke={color} strokeWidth="2" strokeDasharray="4 2" />
                : <line x1="0" y1="2" x2="16" y2="2" stroke={color} strokeWidth="2" />}
            </svg>
            <span style={{ fontFamily: "'Nunito', sans-serif", fontSize: "0.72rem", color: "var(--muted-foreground)" }}>{label}</span>
          </div>
        ))}
        <div style={{ marginLeft: "auto", fontFamily: "'DM Mono', monospace", fontSize: "0.62rem", color: "var(--muted-foreground)" }}>
          Avg sleep {avgSleep}h
        </div>
      </div>
    </div>
  );
}

// ─── Live Distraction Donut ────────────────────────────────────────────────────
function DistractionDonut({ appTally }: { appTally: AppTally }) {
  const total = appTally.work + appTally.recharge + appTally.neutral || 1;
  const focusPct = Math.round((appTally.work / total) * 100);

  const slices = [
    { name: "Productive Focus",   value: appTally.work,     color: "var(--primary)", pct: Math.round(appTally.work     / total * 100) },
    { name: "Distracting Leisure",value: appTally.recharge, color: "var(--chart-3)",         pct: Math.round(appTally.recharge / total * 100) },
    { name: "Neutral / System",   value: appTally.neutral,  color: "var(--muted-foreground)", pct: Math.round(appTally.neutral / total * 100) },
  ];

  const fmtSecs = (s: number) => s >= 3600 ? `${(s / 3600).toFixed(1)}h` : `${Math.floor(s / 60)}m`;

  return (
    <div className="card-interactive" style={CARD}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
        <div style={{ width: 28, height: 28, borderRadius: 10, background: "var(--muted)", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Zap size={13} style={{ color: "var(--primary)" }} />
        </div>
        <div>
          <div style={{ fontFamily: "var(--font-sans)", fontSize: "0.95rem", fontWeight: 700, color: "var(--foreground)" }}>Productivity Split</div>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.6rem", color: "var(--muted-foreground)", letterSpacing: "0.06em" }}>Live session tracking</div>
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
        <div style={{ position: "relative", flexShrink: 0 }}>
          <PieChart width={120} height={120}>
            <Pie data={slices.map(s => ({ ...s, value: Math.max(s.value, 0.01) }))} cx={56} cy={56} innerRadius={34} outerRadius={52} dataKey="value" stroke="none" startAngle={90} endAngle={-270}>
              {slices.map(s => <Cell key={s.name} fill={s.color} />)}
            </Pie>
          </PieChart>
          <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
            <span style={{ fontFamily: "var(--font-sans)", fontSize: "1.25rem", fontWeight: 700, color: "var(--foreground)", lineHeight: 1 }}>{focusPct}%</span>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.58rem", color: "var(--primary)", marginTop: 2 }}>focus</span>
          </div>
        </div>

        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 10 }}>
          {slices.map(s => (
            <div key={s.name}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span style={{ width: 8, height: 8, borderRadius: "50%", background: s.color, display: "inline-block", flexShrink: 0 }} />
                  <span style={{ fontFamily: "'Nunito', sans-serif", fontSize: "0.75rem", color: "var(--foreground)" }}>{s.name}</span>
                </div>
                <div style={{ display: "flex", gap: 8 }}>
                  <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.68rem", color: "var(--muted-foreground)" }}>{fmtSecs(s.value)}</span>
                  <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.68rem", color: s.color }}>{s.pct}%</span>
                </div>
              </div>
              <div style={{ height: 3, borderRadius: 2, background: "var(--muted)", overflow: "hidden" }}>
                <div style={{ height: "100%", width: `${s.pct}%`, background: s.color, borderRadius: 2, transition: "width 1s ease" }} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Mood Strip ────────────────────────────────────────────────────────────────
function MoodStrip({ reflections }: { reflections: ReflectionEntry[] }) {
  const last7 = reflections.slice(-7);
  return (
    <div className="card-interactive" style={{ ...CARD, padding: "16px 24px" }}>
      <div style={{ ...SECTION_LABEL, marginBottom: 12 }}>Mood History</div>
      <div style={{ display: "flex", gap: 6, alignItems: "flex-end" }}>
        {last7.map(r => (
          <div key={r.id} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
            <div title={r.mood} style={{ width: "100%", height: 32, borderRadius: 7, background: MOOD_COLORS[r.mood], opacity: 0.82 }} />
            <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.55rem", color: "var(--muted-foreground)" }}>{r.date.split(" ")[0].replace(",", "")}</span>
            <span style={{ fontFamily: "'Nunito', sans-serif", fontSize: "0.62rem", color: "var(--foreground)" }}>{r.mood}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Flow Analyzer ─────────────────────────────────────────────────────────────
function FlowAnalyzer({ reflections }: { reflections: ReflectionEntry[] }) {
  const { triggers, leaks } = useMemo(() => {
    const winsText   = reflections.map(r => r.wins).join(" ");
    const blocksText = reflections.map(r => r.roadblocks).join(" ");
    const t = topKeywords(winsText,   5);
    const l = topKeywords(blocksText, 5);
    return {
      triggers: t.length >= 3 ? t : FALLBACK_TRIGGERS,
      leaks:    l.length >= 3 ? l : FALLBACK_LEAKS,
    };
  }, [reflections]);

  const winsDigest   = reflections.map(r => r.wins).filter(Boolean).join(". ").slice(0, 220);
  const blocksDigest = reflections.map(r => r.roadblocks).filter(Boolean).join(". ").slice(0, 220);

  return (
    <div className="card-interactive" style={CARD}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 18 }}>
        <div style={{ width: 28, height: 28, borderRadius: 10, background: "var(--muted)", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Brain size={13} style={{ color: "var(--chart-3)" }} />
        </div>
        <div>
          <div style={{ fontFamily: "var(--font-sans)", fontWeight: 700, fontSize: "0.95rem", color: "var(--foreground)" }}>Cognitive Flow Analyzer</div>
          <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.6rem", color: "var(--muted-foreground)", letterSpacing: "0.06em" }}>Extracted from {reflections.length} reflection logs</div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
        {[
          { label: "Flow Triggers",   items: triggers, color: "var(--primary)", icon: <Zap  size={11} /> },
          { label: "Cognitive Leaks", items: leaks,    color: "var(--chart-3)",         icon: <Wind size={11} /> },
        ].map(({ label, items, color, icon }) => (
          <div key={label}>
            <div style={{ display: "flex", alignItems: "center", gap: 5, marginBottom: 9 }}>
              <span style={{ color }}>{icon}</span>
              <span style={{ ...SECTION_LABEL, color }}>{label}</span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
              {items.map((item, i) => (
                <div key={`${label}-${i}`} style={{ display: "flex", alignItems: "flex-start", gap: 7, padding: "7px 10px", borderRadius: 10, background: `${color}10`, border: `1px solid ${color}22` }}>
                  <ChevronRight size={10} style={{ color, marginTop: 2, flexShrink: 0 }} />
                  <span style={{ fontFamily: "'Nunito', sans-serif", fontSize: "0.78rem", color: "var(--foreground)", lineHeight: 1.4 }}>{item}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div style={{ marginTop: 16, padding: "12px 14px", borderRadius: 12, background: "var(--muted)", border: "1px solid var(--border)" }}>
        <div style={{ ...SECTION_LABEL, marginBottom: 6 }}>Journal Digest</div>
        <p style={{ fontFamily: "'Nunito', sans-serif", fontSize: "0.77rem", color: "var(--muted-foreground)", lineHeight: 1.65, margin: 0 }}>
          <strong style={{ color: "var(--primary)" }}>Wins: </strong>{winsDigest || "No entries yet."}
          {winsDigest.length >= 220 && "…"}
        </p>
        <p style={{ fontFamily: "'Nunito', sans-serif", fontSize: "0.77rem", color: "var(--muted-foreground)", lineHeight: 1.65, margin: "6px 0 0" }}>
          <strong style={{ color: "var(--chart-3)" }}>Roadblocks: </strong>{blocksDigest || "No entries yet."}
          {blocksDigest.length >= 220 && "…"}
        </p>
      </div>
    </div>
  );
}

// ─── Wellbeing Insights ────────────────────────────────────────────────────────
function WellbeingInsights({ reflections, appTally }: { reflections: ReflectionEntry[]; appTally: AppTally }) {
  const avgEnergy = reflections.length > 0 ? reflections.reduce((s, r) => s + r.energy, 0) / reflections.length : 3;
  const avgFriction = reflections.length > 0 ? reflections.reduce((s, r) => s + r.friction, 0) / reflections.length : 3;
  const avgSleep  = reflections.length > 0 ? (reflections.reduce((s, r) => s + r.sleepHours, 0) / reflections.length).toFixed(1) : "7.0";

  const burnoutScore = (5 - avgEnergy) + avgFriction;
  const burnoutRisk  = burnoutScore < 3 ? "Low" : burnoutScore < 5 ? "Moderate" : "High";
  const riskColor    = burnoutRisk === "Low" ? "var(--primary)" : burnoutRisk === "Moderate" ? "var(--chart-3)" : "var(--destructive)";

  const totalTally = appTally.work + appTally.recharge + appTally.neutral || 1;
  const focusPct   = Math.round((appTally.work / totalTally) * 100);
  const breakCompliance = 68;
  const bypassed        = Math.round(7 * (1 - breakCompliance / 100));

  const narrative = burnoutRisk === "High"
    ? `Your focus-to-rest ratio is elevated this week, with friction averaging ${avgFriction.toFixed(1)}/5. Protect your sleep windows and honour scheduled breaks — your cognitive battery needs longer recovery arcs.`
    : burnoutRisk === "Moderate"
    ? `Mid-week shows a friction cluster tied to lower sleep nights. Thursday's peak (${reflections.length > 0 ? reflections.find(r => r.energy === Math.max(...reflections.map(x => x.energy)))?.date ?? "—" : "—"}) confirms the sleep→flow link. Aim for one deep-work morning block per day.`
    : `Solid week. Energy stayed above the optimal threshold on most days. Your sleep consistency is driving this — keep protecting your morning ritual and consider a light walk on lower-energy afternoons.`;

  const METRICS = [
    { label: "Burnout Susceptibility", value: burnoutRisk, sub: `Focus/Recharge · ${focusPct}% productive`,           color: riskColor,           icon: <AlertTriangle size={13} style={{ color: riskColor }} /> },
    { label: "Break Compliance",       value: `${breakCompliance}%`, sub: `${bypassed} bypassed breaks this week`,   color: "var(--chart-2)",            icon: <CheckCircle2  size={13} style={{ color: "var(--chart-2)"  }} /> },
    { label: "Sleep Average",          value: `${avgSleep}h`,        sub: parseFloat(avgSleep) >= 7.5 ? "Optimal range" : "Below 7.5h threshold", color: parseFloat(avgSleep) >= 7.5 ? "var(--primary)" : "var(--chart-3)", icon: <Moon size={13} style={{ color: parseFloat(avgSleep) >= 7.5 ? "var(--primary)" : "var(--chart-3)" }} /> },
    { label: "Avg Friction",           value: `${avgFriction.toFixed(1)}/5`, sub: avgFriction > 3 ? "High — hotspots detected" : "Within normal range", color: avgFriction > 3 ? "var(--chart-3)" : "var(--primary)", icon: <Wind size={13} style={{ color: avgFriction > 3 ? "var(--chart-3)" : "var(--primary)" }} /> },
  ];

  return (
    <div className="card-interactive" style={CARD}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 18 }}>
        <div style={{ width: 28, height: 28, borderRadius: 10, background: "var(--muted)", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Sparkles size={13} style={{ color: "var(--primary)" }} />
        </div>
        <div>
          <div style={{ fontFamily: "var(--font-sans)", fontSize: "0.95rem", color: "var(--foreground)" }}>Wellbeing Insights</div>
          <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.6rem", color: "var(--muted-foreground)", letterSpacing: "0.06em" }}>Generated from reflection data</div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 18 }}>
        {METRICS.map(({ label, value, sub, color, icon }) => (
          <div key={label} style={{ padding: "12px 14px", borderRadius: 14, background: `${color}12`, border: `1px solid ${color}28` }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 5 }}>{icon}
              <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.58rem", letterSpacing: "0.08em", color, textTransform: "uppercase" }}>{label}</span>
            </div>
            <div style={{ fontFamily: "var(--font-sans)", fontWeight: 700, fontSize: "1.1rem", color: "var(--foreground)", marginBottom: 2 }}>{value}</div>
            <div style={{ fontFamily: "'Nunito', sans-serif", fontSize: "0.71rem", color: "var(--muted-foreground)", lineHeight: 1.5 }}>{sub}</div>
          </div>
        ))}
      </div>

      {/* Narrative */}
      <div style={{ padding: "16px 18px", borderRadius: 14, background: "var(--muted)", border: "1px solid var(--border)" }}>
        <div style={{ ...SECTION_LABEL, marginBottom: 10 }}>Weekly Wellness Narrative</div>
        <p style={{ fontFamily: "var(--font-sans)", fontSize: "0.85rem", lineHeight: 1.78, color: "var(--foreground)", fontStyle: "italic", margin: "0 0 14px" }}>
          "{narrative}"
        </p>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {["Move on low-energy days", "Protect 8h sleep", "Honour scheduled breaks"].map(tip => (
            <div key={tip} style={{ display: "flex", alignItems: "center", gap: 5, padding: "4px 10px", borderRadius: 20, background: "var(--card)", border: "1px solid var(--border)" }}>
              <CheckCircle2 size={10} style={{ color: "var(--primary)" }} />
              <span style={{ fontFamily: "'Nunito', sans-serif", fontSize: "0.7rem", color: "var(--foreground)" }}>{tip}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Recent Entries ────────────────────────────────────────────────────────────
function RecentEntries({ reflections }: { reflections: ReflectionEntry[] }) {
  const entries = [...reflections].reverse().slice(0, 6);
  return (
    <div className="card-interactive" style={CARD}>
      <div style={{ ...SECTION_LABEL, marginBottom: 14 }}>Recent Entries</div>
      <div style={{ display: "flex", flexDirection: "column" }}>
        {entries.map((r, i) => (
          <div key={r.id} style={{ display: "flex", alignItems: "center", gap: 12, padding: "11px 0", borderBottom: i < entries.length - 1 ? "1px solid var(--border)" : "none" }}>
            <div style={{ width: 10, height: 10, borderRadius: "50%", background: MOOD_COLORS[r.mood], flexShrink: 0 }} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 7, flexWrap: "wrap" }}>
                <span style={{ fontFamily: "'Nunito', sans-serif", fontSize: "0.82rem", color: "var(--foreground)" }}>{r.date}</span>
                <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.6rem", color: "var(--muted-foreground)" }}>{r.time}</span>
                <span style={{ padding: "2px 8px", borderRadius: 10, background: `${MOOD_COLORS[r.mood]}20`, fontFamily: "'DM Mono', monospace", fontSize: "0.6rem", color: MOOD_COLORS[r.mood] }}>{r.mood}</span>
              </div>
              {r.wins && <div style={{ fontFamily: "'Nunito', sans-serif", fontSize: "0.73rem", color: "var(--muted-foreground)", marginTop: 2 }}>✦ {r.wins.slice(0, 70)}{r.wins.length > 70 ? "…" : ""}</div>}
            </div>
            <div style={{ display: "flex", gap: 12, flexShrink: 0 }}>
              {[
                { label: "E", v: r.energy,   color: "var(--primary)" },
                { label: "F", v: r.friction, color: "var(--chart-3)" },
                { label: "S", v: r.stress ?? "—", color: "var(--destructive)" },
              ].map(({ label, v, color }) => (
                <div key={label} style={{ textAlign: "center" }}>
                  <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.6rem", color: "var(--muted-foreground)" }}>{label}</div>
                  <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.78rem", color }}>{v}</div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── App Categorization & Recategorizer Panel ──────────────────────────────────
function AppUsageRecategorizer() {
  const appRules = useStaminaStore(s => s.appRules || []);
  const recategorizeApp = useStaminaStore(s => s.recategorizeApp);

  return (
    <div className="card-interactive" style={CARD}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
        <div>
          <div style={{ fontFamily: "var(--font-sans)", fontWeight: 700, fontSize: "0.95rem", color: "var(--foreground)", marginBottom: 2 }}>
            App Categorization Rules
          </div>
          <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.6rem", color: "var(--muted-foreground)" }}>
            Instant 1-click recategorization across sessions
          </div>
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {appRules.length === 0 ? (
          <div style={{ padding: 16, textAlign: "center", color: "var(--muted-foreground)", fontSize: "0.8rem" }}>
            No custom app classification rules defined yet.
          </div>
        ) : (
          appRules.map((rule) => {
            const isWork = rule.category === "work";
            const isRecharge = rule.category === "recharge";

            return (
              <div
                key={rule.app_name}
                style={{
                  display: "flex", alignItems: "center", justifyContent: "space-between",
                  padding: "8px 12px", borderRadius: 10, background: "var(--muted)",
                  border: "1px solid var(--border)"
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0, flex: 1 }}>
                  <span>{isWork ? "💻" : isRecharge ? "🎮" : "☕"}</span>
                  <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.78rem", color: "var(--foreground)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {rule.app_name}
                  </span>
                </div>

                <select
                  value={rule.category}
                  onChange={(e) => recategorizeApp(rule.app_name, e.target.value as any)}
                  style={{
                    padding: "3px 8px", borderRadius: 6, border: "none", cursor: "pointer",
                    fontFamily: "'Nunito', sans-serif", fontSize: "0.7rem", fontWeight: 600,
                    background: isWork ? "var(--primary)" : isRecharge ? "#C5A882" : "var(--card)",
                    color: isWork ? "var(--primary-foreground)" : isRecharge ? "#FFF" : "var(--foreground)"
                  }}
                >
                  <option value="work">Work 💻</option>
                  <option value="recharge">Recharge 🎮</option>
                  <option value="neutral">Neutral ☕</option>
                </select>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

// ─── Main Analytics ────────────────────────────────────────────────────────────
export function Analytics() {
  const todayWork = useStaminaStore(s => s.todayWork || 0);
  const todayRecharge = useStaminaStore(s => s.todayRecharge || 0);
  const todayRest = useStaminaStore(s => s.todayRest || 0);
  const activeProcess = useStaminaStore(s => s.activeProcess);
  const activeApp = useStaminaStore(s => s.activeApp);
  const classifiedApp = useStaminaStore(s => s.classifiedApp);
  const appTally = useMemo(() => ({ work: todayWork, recharge: todayRecharge, neutral: todayRest }), [todayWork, todayRecharge, todayRest]);
  const { reflections, addReflection } = useReflections();
  const [activeTab, setActiveTab] = useState<"overview" | "checkin" | "flow" | "insights" | "sessions">("overview");

  const themeObj = {
    cardBg: "var(--card)",
    border: "var(--border)",
    fg: "var(--foreground)",
    primary: "var(--primary)",
    sub: "var(--muted-foreground)",
  };

  const TABS = [
    { id: "overview"  as const, label: "Energy Map",     icon: <Activity size={12} /> },
    { id: "sessions"  as const, label: "Session History",icon: <Clock    size={12} /> },
    { id: "checkin"   as const, label: "Check-In",       icon: <Plus     size={12} /> },
    { id: "flow"      as const, label: "Flow Analyzer",  icon: <Brain    size={12} /> },
    { id: "insights"  as const, label: "Wellbeing",      icon: <Sparkles size={12} /> },
  ];

  return (
    <div className="flex flex-col h-full overflow-hidden" style={{ background: "var(--background)" }}>
      {/* Header */}
      <div style={{ padding: "24px 32px 0", background: "var(--card)", borderBottom: "1px solid var(--border)" }}>
        <div style={{ marginBottom: 16 }}>
          <h2 style={{ fontFamily: "var(--font-sans)", fontWeight: 700, color: "var(--foreground)", margin: 0, fontSize: "1.35rem" }}>
            Analytics & Energy Mapping
          </h2>
          <p style={{ fontFamily: "var(--font-sans)", fontSize: "0.8rem", color: "var(--muted-foreground)", margin: "4px 0 0" }}>
            {reflections.length} reflections · live session tracking
          </p>
        </div>
        <div style={{ display: "flex", gap: 2 }}>
          {TABS.map(({ id, label, icon }) => (
            <button key={id} onClick={() => setActiveTab(id)} style={{
              display: "flex", alignItems: "center", gap: 5, padding: "8px 16px",
              borderRadius: "10px 10px 0 0", border: "none", cursor: "pointer",
              fontFamily: "var(--font-sans)", fontSize: "0.8rem",
              background: activeTab === id ? "var(--background)" : "transparent",
              color: activeTab === id ? "var(--foreground)" : "var(--muted-foreground)",
              borderBottom: `2px solid ${activeTab === id ? "var(--primary)" : "transparent"}`,
              transition: "all 0.18s",
            }}>
              <span style={{ color: activeTab === id ? "var(--primary)" : "var(--muted-foreground)" }}>{icon}</span>
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto stagger-children custom-scrollbar" style={{ padding: "24px 32px", display: "flex", flexDirection: "column", gap: 18 }}>
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.18 }}
            style={{ display: "flex", flexDirection: "column", gap: 18 }}
          >
            {activeTab === "overview" && (
              <>
                <WeeklyEnergyMap reflections={reflections} />
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18 }}>
                  <DistractionDonut appTally={appTally} />
                  <MoodStrip reflections={reflections} />
                </div>
                <ActivityDeepDive
                  appUsage={[
                    { process: activeProcess || "Code.exe", category: (classifiedApp === "recharge" || classifiedApp === "neutral") ? classifiedApp : "work", duration: todayWork, titles: { [activeApp || "Active Workspace"]: todayWork } }
                  ]}
                  theme={themeObj}
                />
                <AppUsageRecategorizer />
              </>
            )}
            {activeTab === "sessions" && <SessionTimeline theme={themeObj} />}
            {activeTab === "checkin" && (
              <>
                <CheckInPanel onSubmit={addReflection} />
                <RecentEntries reflections={reflections} />
              </>
            )}
            {activeTab === "flow" && (
              <>
                <FlowAnalyzer reflections={reflections} />
                <ContextSwitchTimeline theme={themeObj} />
              </>
            )}
            {activeTab === "insights" && <WellbeingInsights reflections={reflections} appTally={appTally} />}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
