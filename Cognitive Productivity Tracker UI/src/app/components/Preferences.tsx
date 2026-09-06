/**
 * Preferences and Settings interface managing multi-theme switching, app classification rules, and stamina parameters.
 *
 * Author: ChaChan26 <minhharry2006@gmail.com>
 * Copyright (c) 2026 ChaChan26. All rights reserved.
 */

import { useState, useEffect } from "react";
import {
  AlertTriangle, Power, PauseCircle, Brain, Clock, Zap,
  Droplets, Moon, Footprints, Timer, Coffee, Wind,
  ChevronRight, Palette, Check, Plus, Trash2, RefreshCw,
  Bell, Volume2, ShieldCheck, Sparkles, Activity
} from "lucide-react";
import { BASE_WORK, BASE_REST, useStaminaStore, SystemSettings, RunningApp } from "../hooks/useStaminaEngine";

// ─── Theme definitions ─────────────────────────────────────────────────────────
export { type ThemeId, type ThemeConfig, THEMES } from "../types/themes";
import { type ThemeId, type ThemeConfig, THEMES } from "../types/themes";

// ─── Style constants ───────────────────────────────────────────────────────────
const CARD: React.CSSProperties = {
  background: "var(--card)",
  border: "1px solid var(--border)",
  borderRadius: "var(--radii-xl)",
  padding: "20px 22px",
  boxShadow: "var(--shadow-lg)",
};

const SECTION_LABEL: React.CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.68rem",
  letterSpacing: "0.1em",
  color: "var(--muted-foreground)",
  textTransform: "uppercase",
  fontWeight: 700,
};

// ─── Toggle component ──────────────────────────────────────────────────────────
function Toggle({ checked, onChange }: { checked: boolean; onChange: () => void }) {
  return (
    <button
      onClick={onChange}
      style={{
        width: 36,
        height: 20,
        borderRadius: 10,
        padding: 2,
        background: checked ? "var(--primary)" : "var(--muted)",
        border: "1px solid var(--border)",
        cursor: "pointer",
        transition: "background 0.2s",
        display: "flex",
        alignItems: "center",
        flexShrink: 0,
      }}
    >
      <div
        style={{
          width: 14,
          height: 14,
          borderRadius: 7,
          background: checked ? "var(--primary-foreground)" : "var(--muted-foreground)",
          transform: checked ? "translateX(16px)" : "translateX(0)",
          transition: "transform 0.2s",
        }}
      />
    </button>
  );
}

// ─── Props ─────────────────────────────────────────────────────────────────────
interface Props {
  activeTheme: ThemeId;
  eyeCare: boolean;
  onSetEyeCare: (v: boolean | ((prev: boolean) => boolean)) => void;
  autoSwap: boolean;
  onSetAutoSwap: (v: boolean | ((prev: boolean) => boolean)) => void;
  onSetTheme: (id: ThemeId) => void;
}

// ─── Target Config ─────────────────────────────────────────────────────────────
function TargetConfig({ settings, updateSettings }: { settings: SystemSettings; updateSettings: (v: Partial<SystemSettings>) => void }) {
  const sleepTarget = (settings?.daily_sleep_target as number) ?? 8.0;
  const stepsTarget = (settings?.daily_step_target as number) ?? 10000;
  const waterTarget = (settings?.hydration_target as number) ?? 8;

  const [localSleep, setLocalSleep] = useState(sleepTarget);
  const [localSteps, setLocalSteps] = useState(stepsTarget);
  const [localWater, setLocalWater] = useState(waterTarget);

  useEffect(() => { setLocalSleep(sleepTarget); }, [sleepTarget]);
  useEffect(() => { setLocalSteps(stepsTarget); }, [stepsTarget]);
  useEffect(() => { setLocalWater(waterTarget); }, [waterTarget]);

  const [waterUnit, setWaterUnit] = useState<"cups" | "ml" | "oz">("cups");
  const waterMax = waterUnit === "cups" ? 16 : waterUnit === "ml" ? 4000 : 128;
  const waterStep = waterUnit === "cups" ? 0.5 : waterUnit === "ml" ? 100 : 4;
  
  const displayWater = waterUnit === "ml" ? localWater * 250 : localWater;
  const waterLabel = waterUnit === "cups" ? `${displayWater} cups` : waterUnit === "ml" ? `${displayWater} ml` : `${displayWater} oz`;

  return (
    <div style={CARD}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 20 }}>
        <div style={{ width: 28, height: 28, borderRadius: 10, background: "var(--muted)", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Droplets size={13} style={{ color: "var(--primary)" }} />
        </div>
        <div>
          <div style={{ fontFamily: "var(--font-sans)", fontSize: "0.95rem", fontWeight: 700, color: "var(--foreground)" }}>Daily Targets</div>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.6rem", color: "var(--muted-foreground)", letterSpacing: "0.06em" }}>Sleep · Steps · Hydration</div>
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        {/* Sleep */}
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <Moon size={12} style={{ color: "var(--primary)" }} />
              <span style={{ fontFamily: "var(--font-sans)", fontSize: "0.84rem", color: "var(--foreground)" }}>Sleep Target</span>
            </div>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.84rem", color: "var(--primary)" }}>{localSleep}h</span>
          </div>
          <input
            type="range" min={4} max={12} step={0.5} value={localSleep}
            onChange={(e) => {
              const val = Number(e.target.value);
              setLocalSleep(val);
              updateSettings({ daily_sleep_target: val });
            }}
            className="w-full h-1.5 rounded-full appearance-none outline-none cursor-pointer"
            style={{ accentColor: "var(--primary)", background: `linear-gradient(to right, var(--primary) ${((localSleep - 4) / 8) * 100}%, var(--muted) ${((localSleep - 4) / 8) * 100}%)` }}
          />
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span style={{ ...SECTION_LABEL, fontSize: "0.58rem" }}>4h</span>
            <span style={{ ...SECTION_LABEL, fontSize: "0.58rem" }}>12h</span>
          </div>
        </div>

        {/* Steps */}
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <Footprints size={12} style={{ color: "var(--primary)" }} />
              <span style={{ fontFamily: "var(--font-sans)", fontSize: "0.84rem", color: "var(--foreground)" }}>Daily Steps</span>
            </div>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.84rem", color: "var(--primary)" }}>{localSteps.toLocaleString()}</span>
          </div>
          <input
            type="range" min={1000} max={20000} step={500} value={localSteps}
            onChange={(e) => {
              const val = Number(e.target.value);
              setLocalSteps(val);
              updateSettings({ daily_step_target: val });
            }}
            className="w-full h-1.5 rounded-full appearance-none outline-none cursor-pointer"
            style={{ accentColor: "var(--primary)", background: `linear-gradient(to right, var(--primary) ${((localSteps - 1000) / 19000) * 100}%, var(--muted) ${((localSteps - 1000) / 19000) * 100}%)` }}
          />
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span style={{ ...SECTION_LABEL, fontSize: "0.58rem" }}>1k</span>
            <span style={{ ...SECTION_LABEL, fontSize: "0.58rem" }}>20k</span>
          </div>
        </div>

        {/* Water */}
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <Coffee size={12} style={{ color: "var(--primary)" }} />
              <span style={{ fontFamily: "var(--font-sans)", fontSize: "0.84rem", color: "var(--foreground)" }}>Water Intake</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <div style={{ display: "flex", borderRadius: 8, overflow: "hidden", border: "1px solid var(--border)" }}>
                {(["cups", "ml", "oz"] as const).map((u) => (
                  <button
                    key={u}
                    onClick={() => { setWaterUnit(u); }}
                    style={{
                      padding: "3px 8px", border: "none", cursor: "pointer",
                      fontFamily: "var(--font-mono)", fontSize: "0.62rem",
                      background: waterUnit === u ? "var(--primary)" : "var(--muted)",
                      color: waterUnit === u ? "var(--primary-foreground)" : "var(--muted-foreground)",
                      transition: "all 0.15s"
                    }}
                  >{u}</button>
                ))}
              </div>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.84rem", color: "var(--primary)" }}>{waterLabel}</span>
            </div>
          </div>
          <input
            type="range" min={waterUnit === "cups" ? 1 : waterUnit === "ml" ? 250 : 8} max={waterMax} step={waterStep} value={waterUnit === "ml" ? localWater * 250 : waterUnit === "oz" ? localWater * 8 : localWater}
            onChange={(e) => {
              const val = Number(e.target.value);
              const cups = waterUnit === "ml" ? val / 250 : waterUnit === "oz" ? val / 8 : val;
              setLocalWater(cups);
              updateSettings({ hydration_target: cups });
            }}
            className="w-full h-1.5 rounded-full appearance-none outline-none cursor-pointer"
            style={{
              accentColor: "var(--primary)",
              background: `linear-gradient(to right, var(--primary) ${((localWater - 1) / 15) * 100}%, var(--muted) ${((localWater - 1) / 15) * 100}%)`
            }}
          />
        </div>
      </div>
    </div>
  );
}

// ─── Proactive Cognitive Engine Config ──────────────────────────────────────────
function ProactivityConfig({ settings, updateSettings }: { settings: SystemSettings; updateSettings: (v: Partial<SystemSettings>) => void }) {
  const currentLevel = (settings?.proactivity_level as string) ?? "balanced";
  const toasts = (settings?.enable_desktop_toasts as boolean) ?? true;
  const audio = (settings?.enable_audio_chimes as boolean) ?? true;
  const distraction = (settings?.enable_distraction_nudges as boolean) ?? true;
  const thrashing = (settings?.enable_thrashing_nudges as boolean) ?? true;
  const eyeCare = ((settings?.enable_eyecare_nudges ?? settings?.enable_eye_care_nudges) as boolean) ?? true;
  const hydration = (settings?.enable_hydration_nudges as boolean) ?? true;

  const PROACTIVITY_PRESETS = [
    { id: "gentle", label: "Gentle", sub: "Soft whispers, 10m cooldowns, non-intrusive" },
    { id: "balanced", label: "Balanced", sub: "Standard 5m cadence, smart shield alerts" },
    { id: "strict", label: "Strict", sub: "Rapid 2m pacing, strong guardian against distraction" },
    { id: "disabled", label: "Silent", sub: "Nudges disabled, silent logging only" },
  ];

  return (
    <div style={CARD}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ width: 28, height: 28, borderRadius: 10, background: "var(--primary-alpha-12)", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Sparkles size={14} style={{ color: "var(--primary)" }} />
          </div>
          <div>
            <div style={{ fontFamily: "var(--font-sans)", fontSize: "0.95rem", fontWeight: 700, color: "var(--foreground)" }}>Proactive Cognitive Companion Engine</div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.6rem", color: "var(--muted-foreground)", letterSpacing: "0.06em" }}>Behavioral nudges · Real-time intervention</div>
          </div>
        </div>
      </div>

      <div style={{ ...SECTION_LABEL, marginBottom: 10 }}>Proactivity Stance</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10, marginBottom: 20 }}>
        {PROACTIVITY_PRESETS.map((p) => {
          const active = currentLevel === p.id;
          return (
            <button
              key={p.id}
              onClick={() => updateSettings({ proactivity_level: p.id })}
              style={{
                padding: "12px 14px",
                borderRadius: 12,
                cursor: "pointer",
                textAlign: "left",
                background: active ? "var(--muted)" : "transparent",
                border: `1.5px solid ${active ? "var(--primary)" : "var(--border)"}`,
                transition: "all 0.18s ease"
              }}
            >
              <div style={{ fontFamily: "var(--font-sans)", fontSize: "0.86rem", fontWeight: 700, color: active ? "var(--primary)" : "var(--foreground)", marginBottom: 4 }}>
                {p.label}
              </div>
              <div style={{ fontFamily: "var(--font-sans)", fontSize: "0.68rem", color: "var(--muted-foreground)", lineHeight: 1.35 }}>
                {p.sub}
              </div>
            </button>
          );
        })}
      </div>

      <div style={{ ...SECTION_LABEL, marginBottom: 12 }}>Intervention Channels & Triggers</div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        {[
          { icon: <Bell size={13} />, label: "Windows Desktop Notifications", sub: "Non-blocking OS toast alerts", key: "enable_desktop_toasts", val: toasts },
          { icon: <Volume2 size={13} />, label: "Harmonic Auditory Chimes", sub: "Subtle WebAudio harmonic tones", key: "enable_audio_chimes", val: audio },
          { icon: <AlertTriangle size={13} />, label: "Distraction Drift Guard", sub: "30s grace alerts when drifting into entertainment", key: "enable_distraction_nudges", val: distraction },
          { icon: <Activity size={13} />, label: "Context Switching Thrash Shield", sub: "Detects rapid window thrashing >5 switches", key: "enable_thrashing_nudges", val: thrashing },
          { icon: <Wind size={13} />, label: "20-20-20 Eye Care Reminders", sub: "Look 20ft away every 20 minutes", key: "enable_eyecare_nudges", val: eyeCare },
          { icon: <Coffee size={13} />, label: "Hourly Hydration Prompts", sub: "Gentle reminders to drink water", key: "enable_hydration_nudges", val: hydration },
        ].map(({ icon, label, sub, key, val }) => (
          <div key={key} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 14px", borderRadius: 12, background: "var(--muted)", border: "1px solid var(--border)" }}>
            <div style={{ display: "flex", alignItems: "flex-start", gap: 8, paddingRight: 8 }}>
              <span style={{ color: "var(--primary)", marginTop: 2 }}>{icon}</span>
              <div>
                <div style={{ fontFamily: "var(--font-sans)", fontSize: "0.82rem", fontWeight: 600, color: "var(--foreground)" }}>{label}</div>
                <div style={{ fontFamily: "var(--font-sans)", fontSize: "0.7rem", color: "var(--muted-foreground)" }}>{sub}</div>
              </div>
            </div>
            <Toggle checked={val} onChange={() => updateSettings({ [key]: !val })} />
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Pacing Sensitivities ──────────────────────────────────────────────────────
function PacingConfig({ settings, updateSettings, adaptedWorkSecs, fatigue }: { settings: SystemSettings; updateSettings: (v: Partial<SystemSettings>) => void; adaptedWorkSecs: number; fatigue: number }) {
  const workBlock = (settings?.work_duration_minutes as number) ?? Math.floor(BASE_WORK / 60);
  const restDuration = (settings?.rest_duration_seconds as number) ? Math.round((settings.rest_duration_seconds as number) / 60) : Math.floor(BASE_REST / 60);
  const idleTimeout = (settings?.idle_timeout_seconds as number) ? Math.round((settings.idle_timeout_seconds as number) / 60) : 3;
  const zenLevel = (settings?.zen_level as string) ?? "drift";

  const [localWork, setLocalWork] = useState(workBlock);
  const [localRest, setLocalRest] = useState(restDuration);
  const [localIdle, setLocalIdle] = useState(idleTimeout);

  useEffect(() => { setLocalWork(workBlock); }, [workBlock]);
  useEffect(() => { setLocalRest(restDuration); }, [restDuration]);
  useEffect(() => { setLocalIdle(idleTimeout); }, [idleTimeout]);

  const ZEN_LEVELS = [
    { id: "whisper" as const, label: "Whisper", sub: "Subtle ambient, light blur", icon: "◌" },
    { id: "drift" as const, label: "Drift", sub: "Soft sound, gentle transitions", icon: "◎" },
    { id: "deep" as const, label: "Deep", sub: "Immersive soundscape, full dim", icon: "●" },
    { id: "void" as const, label: "Void", sub: "Total silence, max blackout", icon: "◉" },
  ];

  return (
    <div style={CARD}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 20 }}>
        <div style={{ width: 28, height: 28, borderRadius: 10, background: "var(--muted)", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Timer size={13} style={{ color: "var(--primary)" }} />
        </div>
        <div>
          <div style={{ fontFamily: "var(--font-sans)", fontWeight: 700, fontSize: "0.95rem", color: "var(--foreground)" }}>Pacing Sensitivities</div>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.6rem", color: "var(--muted-foreground)", letterSpacing: "0.06em" }}>Block timings · Zen preset</div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 20 }}>
        {[
          { label: "Work Block Limit", icon: <Clock size={11} />, value: localWork, set: setLocalWork, min: 10, max: 90, step: 5, unit: "min", note: localWork < 25 ? `${25 - localWork}m below baseline` : localWork > 25 ? `+${localWork - 25}m above baseline` : "At baseline", onCommit: (v: number) => updateSettings({ work_duration_minutes: v }) },
          { label: "Rest Duration", icon: <Wind size={11} />, value: localRest, set: setLocalRest, min: 2, max: 30, step: 1, unit: "min", note: `~${Math.round(localRest / localWork * 100)}% of work block`, onCommit: (v: number) => updateSettings({ rest_duration_seconds: v * 60 }) },
          { label: "Idle Timeout", icon: <Zap size={11} />, value: localIdle, set: setLocalIdle, min: 1, max: 15, step: 1, unit: "min", note: "Auto-pause on inactivity", onCommit: (v: number) => updateSettings({ idle_timeout_seconds: v * 60 }) },
          { label: "Recharge Block", icon: <Brain size={11} />, value: 15, set: () => {}, min: 5, max: 30, step: 5, unit: "min", note: "Walk / stretching window", onCommit: () => {} },
        ].map(({ label, icon, value, set, min, max, step, unit, note, onCommit }) => (
          <div key={label} style={{ padding: "14px 16px", borderRadius: 14, background: "var(--muted)", border: "1px solid var(--border)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 5, marginBottom: 8 }}>
              <span style={{ color: "var(--primary)" }}>{icon}</span>
              <span style={{ ...SECTION_LABEL }}>{label}</span>
            </div>
            <div style={{ fontFamily: "var(--font-sans)", fontWeight: 700, fontSize: "1.3rem", color: "var(--foreground)", marginBottom: 6 }}>
              {value}<span style={{ fontFamily: "var(--font-sans)", fontSize: "0.7rem", color: "var(--muted-foreground)", marginLeft: 3 }}>{unit}</span>
            </div>
            <input
              type="range" min={min} max={max} step={step} value={value}
              onChange={(e) => {
                const v = Number(e.target.value);
                set(v);
                onCommit(v);
              }}
              className="w-full h-1.5 rounded-full appearance-none outline-none cursor-pointer"
              style={{ accentColor: "var(--primary)", marginBottom: 6, background: `linear-gradient(to right, var(--primary) ${((value - min) / (max - min)) * 100}%, var(--muted) ${((value - min) / (max - min)) * 100}%)` }}
            />
            <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.58rem", color: "var(--muted-foreground)" }}>{note}</div>
          </div>
        ))}
      </div>

      {/* Zen Level */}
      <div>
        <div style={{ ...SECTION_LABEL, marginBottom: 10 }}>Zen Space Level Preset</div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 8 }}>
          {ZEN_LEVELS.map(({ id, label, sub, icon }) => (
            <button
              key={id}
              onClick={() => updateSettings({ zen_level: id })}
              style={{
                padding: "12px 10px", borderRadius: 12, cursor: "pointer", textAlign: "center",
                background: zenLevel === id ? "var(--primary)" : "var(--muted)",
                border: `1px solid ${zenLevel === id ? "transparent" : "var(--border)"}`,
                transition: "all 0.2s",
              }}
            >
              <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "1.1rem", marginBottom: 4, color: zenLevel === id ? "var(--primary-foreground)" : "var(--foreground)" }}>{icon}</div>
              <div style={{ fontFamily: "'Nunito', sans-serif", fontSize: "0.78rem", color: zenLevel === id ? "var(--primary-foreground)" : "var(--foreground)", marginBottom: 2 }}>{label}</div>
              <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.58rem", color: zenLevel === id ? "var(--card)" : "var(--muted-foreground)", opacity: zenLevel === id ? 0.8 : 1, lineHeight: 1.4 }}>{sub}</div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── App Rules & Recategorization Engine ─────────────────────────────────────
function AppRulesManager() {
  const engine = useStaminaStore();
  const appRules = engine.appRules || [];
  const runningApps = engine.runningApps || [];
  const recentApps = engine.recentApps || [];
  const recategorizeApp = engine.recategorizeApp;
  const deleteAppRule = engine.deleteAppRule;
  const fetchRunningApps = engine.fetchRunningApps;
  
  const [selectedRunning, setSelectedRunning] = useState("");
  const [customInput, setCustomInput] = useState("");
  const [targetCategory, setTargetCategory] = useState<"work" | "recharge" | "neutral">("work");
  const [ruleFilter, setRuleFilter] = useState<"all" | "work" | "recharge" | "neutral">("all");

  const handleAddRule = () => {
    const name = customInput.trim() || selectedRunning.trim();
    if (name) {
      recategorizeApp(name, targetCategory);
      setCustomInput("");
      setSelectedRunning("");
    }
  };

  const filteredRules = appRules.filter(r => ruleFilter === "all" || r.category === ruleFilter);

  return (
    <div style={CARD}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
        <div>
          <div style={{ fontFamily: "var(--font-sans)", fontWeight: 700, fontSize: "1.05rem", color: "var(--foreground)" }}>App Rules & Categorization</div>
          <div style={{ fontFamily: "'Nunito', sans-serif", fontSize: "0.76rem", color: "var(--muted-foreground)", marginTop: 2 }}>
            Manage how MIND-FLOW classifies desktop applications and window titles.
          </div>
        </div>
        <button
          onClick={() => fetchRunningApps()}
          style={{ display: "flex", alignItems: "center", gap: 6, padding: "6px 12px", borderRadius: 10, background: "var(--muted)", border: "1px solid var(--border)", cursor: "pointer", fontFamily: "'Nunito', sans-serif", fontSize: "0.75rem", color: "var(--foreground)" }}
        >
          <RefreshCw size={12} /> Scan Apps
        </button>
      </div>

      {/* Recent Apps Quick Chips */}
      {recentApps.length > 0 && (
        <div style={{ marginBottom: 16, padding: "10px 12px", borderRadius: 12, background: "var(--muted)", border: "1px solid var(--border)" }}>
          <div style={{ ...SECTION_LABEL, fontSize: "0.6rem", marginBottom: 6 }}>Recent Tracked Apps (Click to quick-add as {targetCategory.toUpperCase()})</div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", maxHeight: 72, overflowY: "auto" }}>
            {recentApps.slice(0, 15).map((app) => {
              const isConfigured = appRules.some(r => r.app_name.toLowerCase() === app.process.toLowerCase());
              return (
                <button
                  key={app.process}
                  onClick={() => {
                    recategorizeApp(app.process, targetCategory);
                  }}
                  style={{
                    display: "flex", alignItems: "center", gap: 4,
                    padding: "3px 9px", borderRadius: 16, border: "1px solid var(--border)",
                    background: isConfigured ? "var(--muted)" : "var(--card)",
                    cursor: "pointer", fontFamily: "'Nunito', sans-serif", fontSize: "0.72rem",
                    color: "var(--foreground)", opacity: isConfigured ? 0.6 : 1,
                    transition: "all 0.15s"
                  }}
                  title={app.last_title ? `Last title: ${app.last_title}` : app.process}
                >
                  <span style={{ fontSize: "0.65rem", color: "var(--primary)" }}>+</span>
                  <span style={{ fontFamily: "'DM Mono', monospace" }}>{app.display_name}</span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Add New App Control Bar */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 10, padding: 14, borderRadius: 14, background: "var(--muted)", border: "1px solid var(--border)", marginBottom: 20 }}>
        {/* Running Process Picker Dropdown */}
        <div style={{ flex: 1, minWidth: 180 }}>
          <select
            value={selectedRunning}
            onChange={(e) => {
              setSelectedRunning(e.target.value);
              if (e.target.value) setCustomInput(e.target.value);
            }}
            style={{ width: "100%", padding: "9px 12px", borderRadius: 10, border: "1px solid var(--border)", background: "var(--card)", color: "var(--foreground)", fontFamily: "'Nunito', sans-serif", fontSize: "0.82rem", outline: "none" }}
          >
            <option value="">-- Pick Running App --</option>
            {runningApps.map((a) => (
              <option key={a.process} value={a.process}>
                ⚡ {a.display_name} ({a.process})
              </option>
            ))}
          </select>
        </div>

        {/* Custom Input */}
        <div style={{ flex: 1, minWidth: 180 }}>
          <input
            type="text"
            placeholder="Or type app / keyword..."
            value={customInput}
            onChange={(e) => setCustomInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAddRule()}
            style={{ width: "100%", padding: "9px 12px", borderRadius: 10, border: "1px solid var(--border)", background: "var(--card)", color: "var(--foreground)", fontFamily: "'Nunito', sans-serif", fontSize: "0.82rem", outline: "none", boxSizing: "border-box" }}
          />
        </div>

        {/* Category Selector */}
        <div style={{ display: "flex", background: "var(--card)", borderRadius: 10, padding: 3, border: "1px solid var(--border)" }}>
          {(["work", "recharge", "neutral"] as const).map((cat) => (
            <button
              key={cat}
              onClick={() => setTargetCategory(cat)}
              style={{
                padding: "6px 12px", borderRadius: 8, border: "none", cursor: "pointer",
                fontFamily: "'Nunito', sans-serif", fontSize: "0.78rem", fontWeight: targetCategory === cat ? 600 : 400,
                background: targetCategory === cat ? (cat === "work" ? "var(--primary)" : cat === "recharge" ? "#C5A882" : "var(--muted)") : "transparent",
                color: targetCategory === cat ? (cat === "work" ? "var(--primary-foreground)" : cat === "recharge" ? "#FFF" : "var(--foreground)") : "var(--muted-foreground)",
                transition: "all 0.15s"
              }}
            >
              {cat === "work" ? "💻 Work" : cat === "recharge" ? "🎮 Recharge" : "☕ Neutral"}
            </button>
          ))}
        </div>

        {/* Add Button */}
        <button
          onClick={handleAddRule}
          style={{ padding: "9px 16px", borderRadius: 10, border: "none", background: "var(--primary)", color: "var(--primary-foreground)", fontFamily: "'Nunito', sans-serif", fontSize: "0.82rem", fontWeight: 600, cursor: "pointer", display: "flex", alignItems: "center", gap: 6 }}
        >
          <Plus size={14} /> Add Rule
        </button>
      </div>

      {/* Filter Tabs */}
      <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
        {(["all", "work", "recharge", "neutral"] as const).map((f) => (
          <button
            key={f}
            onClick={() => setRuleFilter(f)}
            style={{
              padding: "5px 12px", borderRadius: 20, border: "1px solid var(--border)", cursor: "pointer",
              fontFamily: "'Nunito', sans-serif", fontSize: "0.74rem",
              background: ruleFilter === f ? "var(--foreground)" : "transparent",
              color: ruleFilter === f ? "var(--background)" : "var(--muted-foreground)",
              transition: "all 0.15s"
            }}
          >
            {f.charAt(0).toUpperCase() + f.slice(1)} ({appRules.filter(r => f === "all" || r.category === f).length})
          </button>
        ))}
      </div>

      {/* Rule Chips Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 10, maxHeight: 320, overflowY: "auto" }}>
        {filteredRules.length === 0 ? (
          <div style={{ gridColumn: "1 / -1", padding: 24, textAlign: "center", color: "var(--muted-foreground)", fontFamily: "'Nunito', sans-serif", fontSize: "0.82rem" }}>
            No app rules configured for this filter.
          </div>
        ) : (
          filteredRules.map((rule) => {
            const isWork = rule.category === "work";
            const isRecharge = rule.category === "recharge";
            return (
              <div
                key={rule.app_name}
                style={{
                  display: "flex", alignItems: "center", justifyContent: "space-between",
                  padding: "8px 12px", borderRadius: 12, background: "var(--muted)",
                  border: `1px solid ${isWork ? "rgba(142,151,253,0.3)" : isRecharge ? "rgba(197,168,130,0.3)" : "var(--border)"}`,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0, flex: 1 }}>
                  <span style={{ fontSize: "0.9rem" }}>{isWork ? "💻" : isRecharge ? "🎮" : "☕"}</span>
                  <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.8rem", color: "var(--foreground)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                    {rule.app_name}
                  </span>
                </div>
                
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  {/* Category toggle pill */}
                  <select
                    value={rule.category}
                    onChange={(e) => recategorizeApp(rule.app_name, e.target.value as any)}
                    style={{
                      padding: "2px 6px", borderRadius: 6, border: "none",
                      fontFamily: "'Nunito', sans-serif", fontSize: "0.68rem", cursor: "pointer",
                      background: isWork ? "var(--primary)" : isRecharge ? "#C5A882" : "var(--card)",
                      color: isWork ? "var(--primary-foreground)" : isRecharge ? "#FFF" : "var(--foreground)",
                    }}
                  >
                    <option value="work">Work</option>
                    <option value="recharge">Recharge</option>
                    <option value="neutral">Neutral</option>
                  </select>

                  <button
                    onClick={() => deleteAppRule(rule.app_name)}
                    style={{ border: "none", background: "transparent", cursor: "pointer", opacity: 0.5, padding: 4 }}
                    title="Delete rule"
                  >
                    <Trash2 size={13} style={{ color: "var(--destructive)" }} />
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

// ─── Theme Selector ────────────────────────────────────────────────────────────
function ThemeSelector({ activeTheme, onSetTheme }: { activeTheme: ThemeId; onSetTheme: (id: ThemeId) => void }) {
  return (
    <div style={CARD}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 20 }}>
        <div style={{ width: 28, height: 28, borderRadius: 10, background: "var(--muted)", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Palette size={13} style={{ color: "var(--primary)" }} />
        </div>
        <div>
          <div style={{ fontFamily: "'Lora', serif", fontSize: "0.95rem", color: "var(--foreground)" }}>Visual Themes</div>
          <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.6rem", color: "var(--muted-foreground)", letterSpacing: "0.06em" }}>Apply a new colour environment</div>
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {Object.values(THEMES).map((theme) => {
          const active = theme.id === activeTheme;
          return (
            <button
              key={theme.id}
              onClick={() => onSetTheme(theme.id)}
              className="card-interactive"
              style={{
                display: "flex", alignItems: "center", gap: 14,
                padding: "14px 16px", borderRadius: 14, cursor: "pointer", textAlign: "left",
                background: active ? "var(--muted)" : "transparent",
                border: `1px solid ${active ? "var(--primary)" : "var(--border)"}`,
                transition: "all 0.2s",
                position: "relative",
              }}
            >
              {/* Palette swatches */}
              <div style={{ display: "flex", gap: 3, flexShrink: 0 }}>
                {theme.palette.map((c, i) => (
                  <div
                    key={`${theme.id}-swatch-${i}`}
                    style={{
                      width: i === 0 ? 28 : 16,
                      height: 28,
                      borderRadius: i === 0 ? 8 : 6,
                      background: c,
                      border: "1px solid rgba(0,0,0,0.06)",
                    }}
                  />
                ))}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontFamily: "'Nunito', sans-serif", fontSize: "0.9rem", color: "var(--foreground)", marginBottom: 2 }}>{theme.name}</div>
                <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.62rem", color: "var(--muted-foreground)" }}>{theme.sub}</div>
              </div>
              {active && (
                <div style={{ width: 22, height: 22, borderRadius: "50%", background: "var(--primary)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                  <Check size={12} style={{ color: "var(--primary-foreground)" }} />
                </div>
              )}
            </button>
          );
        })}
      </div>

      {/* Preview mini strip */}
      <div style={{ marginTop: 16, padding: "12px 14px", borderRadius: 12, background: "var(--muted)", border: "1px solid var(--border)" }}>
        <div style={{ ...SECTION_LABEL, marginBottom: 8 }}>Active — {THEMES[activeTheme].name}</div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <div style={{ height: 24, flex: 2, borderRadius: 6, background: THEMES[activeTheme].pageBg, border: "1px solid rgba(0,0,0,0.06)" }} />
          <div style={{ height: 24, flex: 1, borderRadius: 6, background: THEMES[activeTheme].cardBg, border: "1px solid rgba(0,0,0,0.06)" }} />
          <div style={{ height: 24, flex: 1, borderRadius: 6, background: THEMES[activeTheme].primary }} />
          <div style={{ height: 24, flex: 1, borderRadius: 6, background: THEMES[activeTheme].muted, border: "1px solid rgba(0,0,0,0.06)" }} />
        </div>
        <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
          {["Background", "Card", "Primary", "Muted"].map((l) => (
            <div key={l} style={{ flex: 1, fontFamily: "'DM Mono', monospace", fontSize: "0.55rem", color: "var(--muted-foreground)", textAlign: l === "Background" ? "left" : "center" }}>{l}</div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Main Preferences ──────────────────────────────────────────────────────────
export function Preferences({
  activeTheme, eyeCare, onSetEyeCare, autoSwap, onSetAutoSwap, onSetTheme,
}: Props) {
  const autopilot = useStaminaStore(s => s.autopilot);
  const workKw = useStaminaStore(s => s.workKw);
  const rechargeKw = useStaminaStore(s => s.rechargeKw);
  const fatigue = useStaminaStore(s => s.fatigue);
  const adaptedWorkSecs = useStaminaStore(s => s.adaptedWorkSecs);
  const settings = useStaminaStore(s => s.settings);
  const updateSettings = useStaminaStore(s => s.updateSettings);
  const onSetAutopilot = useStaminaStore(s => s.setAutopilot);
  const onSetWorkKw = useStaminaStore(s => s.setWorkKw);
  const onSetRechargeKw = useStaminaStore(s => s.setRechargeKw);
  const [localWorkKw, setLocalWorkKw] = useState(workKw || "");
  const [localRechargeKw, setLocalRechargeKw] = useState(rechargeKw || "");

  useEffect(() => { setLocalWorkKw(workKw || ""); }, [workKw]);
  useEffect(() => { setLocalRechargeKw(rechargeKw || ""); }, [rechargeKw]);

  const [showShutdown, setShowShutdown] = useState(false);
  const [activeTab, setActiveTab] = useState<"autopilot" | "targets" | "pacing" | "theme">("autopilot");

  const workReduction = Math.round((BASE_WORK - adaptedWorkSecs) / 60);
  const fatigueLevel = fatigue < 30 ? "Low" : fatigue < 55 ? "Moderate" : fatigue < 75 ? "High" : "Critical";
  const fatigueLevelColor = fatigue < 30 ? "var(--primary)" : fatigue < 55 ? "var(--chart-3)" : "var(--destructive)";

  const TABS: { id: typeof activeTab; label: string }[] = [
    { id: "autopilot", label: "Classifier & Autopilot" },
    { id: "targets", label: "Daily Targets" },
    { id: "pacing", label: "Pacing & Zen" },
    { id: "theme", label: "Themes" },
  ];

  return (
    <div className="flex flex-col h-full" style={{ background: "var(--background)" }}>
      {/* Header */}
      <div style={{ padding: "24px 28px 0", background: "var(--card)", borderBottom: "1px solid var(--border)" }}>
        <div style={{ marginBottom: 16 }}>
          <h2 style={{ fontFamily: "var(--font-sans)", fontWeight: 700, color: "var(--foreground)", margin: 0, fontSize: "1.35rem" }}>
            Preferences & Customization
          </h2>
          <p style={{ fontFamily: "var(--font-sans)", fontSize: "0.8rem", color: "var(--muted-foreground)", margin: "4px 0 0" }}>
            Configure your companion's behaviour, targets, and visual environment.
          </p>
        </div>
        <div style={{ display: "flex", gap: 2 }}>
          {TABS.map(({ id, label }) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              style={{
                padding: "8px 16px", borderRadius: "10px 10px 0 0", border: "none", cursor: "pointer",
                fontFamily: "var(--font-sans)", fontSize: "0.8rem",
                background: activeTab === id ? "var(--background)" : "transparent",
                color: activeTab === id ? "var(--foreground)" : "var(--muted-foreground)",
                borderBottom: activeTab === id ? `2px solid var(--primary)` : "2px solid transparent",
                transition: "all 0.18s",
              }}
            >{label}</button>
          ))}
        </div>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto custom-scrollbar" style={{ padding: "24px 28px", display: "flex", flexDirection: "column", gap: 18 }}>
        {activeTab === "autopilot" && (
          <>
            {/* Cognitive Autopilot */}
            <div style={CARD}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Brain size={15} style={{ color: autopilot ? "var(--primary)" : "var(--muted-foreground)" }} />
                  <div style={{ ...SECTION_LABEL }}>Cognitive Autopilot</div>
                </div>
                <Toggle checked={autopilot} onChange={() => onSetAutopilot(!autopilot)} />
              </div>
              <p style={{ fontFamily: "var(--font-sans)", fontSize: "0.8rem", color: "var(--muted-foreground)", lineHeight: 1.6, marginBottom: 16 }}>
                Dynamically scales your focus and rest durations based on real-time fatigue, sleep quality, hydration, and energy from your vitality check-in.
              </p>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 10 }}>
                {[
                  { Icon: Zap, label: "Current Fatigue", value: `${fatigue}/100`, sub: fatigueLevel, color: fatigueLevelColor },
                  { Icon: Clock, label: "Active Work Block", value: `${Math.floor(adaptedWorkSecs / 60)}m`, sub: workReduction > 0 ? `Reduced by ${workReduction}m` : "At baseline (25m)", color: "var(--primary)" },
                  { Icon: Brain, label: "Adaptation", value: autopilot ? "On" : "Off", sub: autopilot ? "Scaling in real-time" : "Locked to base timers", color: autopilot ? "var(--primary)" : "var(--muted-foreground)" },
                ].map(({ Icon, label, value, sub, color }) => (
                  <div key={label} style={{ padding: "12px 14px", borderRadius: 12, background: "var(--muted)", border: "1px solid var(--border)" }}>
                    <Icon size={12} style={{ color, marginBottom: 6 }} />
                    <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.9rem", color: "var(--foreground)" }}>{value}</div>
                    <div style={{ fontFamily: "var(--font-sans)", fontSize: "0.65rem", color: "var(--muted-foreground)", marginTop: 2 }}>{label}</div>
                    <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.58rem", color, marginTop: 2 }}>{sub}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Proactive Cognitive Engine */}
            <ProactivityConfig settings={settings} updateSettings={updateSettings} />

            {/* App Rules & Categorization Engine */}
            <AppRulesManager />

            {/* System Toggles */}
            <div style={CARD}>
              <div style={{ ...SECTION_LABEL, marginBottom: 14 }}>System Toggles</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                {[
                  { label: "Eye Care Shield", sub: "20-20-20 reminders every 20 minutes", val: eyeCare, set: onSetEyeCare },
                  { label: "Auto-clear Desktop on Profile Switch", sub: "Moves files to a temporary swap folder before switching", val: autoSwap, set: onSetAutoSwap },
                ].map(({ label, sub, val, set }) => (
                  <div key={label} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "4px 0" }}>
                    <div>
                      <div style={{ fontFamily: "var(--font-sans)", fontSize: "0.88rem", color: "var(--foreground)" }}>{label}</div>
                      <div style={{ fontFamily: "var(--font-sans)", fontSize: "0.75rem", color: "var(--muted-foreground)" }}>{sub}</div>
                    </div>
                    <Toggle checked={val} onChange={() => set((v: boolean) => !v)} />
                  </div>
                ))}
              </div>
              <div style={{ display: "flex", alignItems: "flex-start", gap: 10, padding: "12px 14px", borderRadius: 12, background: "color-mix(in srgb, var(--secondary) 10%, transparent)", border: "1px solid color-mix(in srgb, var(--secondary) 25%, transparent)", marginTop: 14 }}>
                <AlertTriangle size={13} style={{ color: "var(--secondary)", marginTop: 1, flexShrink: 0 }} />
                <span style={{ fontFamily: "var(--font-sans)", fontSize: "0.76rem", color: "var(--muted-foreground)", lineHeight: 1.55 }}>
                  <strong style={{ color: "var(--secondary)" }}>Cloud Sync Detected:</strong> Auto-clear disabled while OneDrive is active.
                </span>
              </div>
            </div>
          </>
        )}

        {activeTab === "targets" && <TargetConfig settings={settings} updateSettings={updateSettings} />}
        {activeTab === "pacing" && <PacingConfig settings={settings} updateSettings={updateSettings} adaptedWorkSecs={adaptedWorkSecs} fatigue={fatigue} />}
        {activeTab === "theme" && <ThemeSelector activeTheme={activeTheme} onSetTheme={onSetTheme} />}
      </div>

      {/* Bottom Bar */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 28px", background: "var(--card)", borderTop: "1px solid var(--border)", flexShrink: 0 }}>
        <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.68rem", color: "var(--muted-foreground)", letterSpacing: "0.06em" }}>
          MIND-FLOW v2.4.1 · Session #142 · {THEMES[activeTheme].name}
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <button
            style={{
              display: "flex", alignItems: "center", gap: 7, padding: "8px 18px", borderRadius: 12, border: "1px solid var(--border)", cursor: "pointer",
              fontFamily: "var(--font-sans)", fontSize: "0.82rem", color: "var(--muted-foreground)", background: "var(--muted)",
            }}
          >
            <PauseCircle size={14} />Pause Companion
          </button>
          <button
            onClick={() => setShowShutdown(true)}
            style={{
              display: "flex", alignItems: "center", gap: 7, padding: "8px 18px", borderRadius: 12, cursor: "pointer",
              fontFamily: "var(--font-sans)", fontSize: "0.82rem", color: "var(--destructive)",
              background: "color-mix(in srgb, var(--destructive) 10%, transparent)", border: "1px solid color-mix(in srgb, var(--destructive) 30%, transparent)",
            }}
          >
            <Power size={14} />Graceful Shutdown
          </button>
        </div>
      </div>

      {showShutdown && (
        <div style={{ position: "fixed", inset: 0, zIndex: 50, display: "flex", alignItems: "center", justifyContent: "center", background: "rgba(0,0,0,0.5)", backdropFilter: "blur(4px)" }}>
          <div style={{ ...CARD, maxWidth: 380, width: "100%", margin: "0 24px" }}>
            <h3 style={{ fontFamily: "var(--font-sans)", fontWeight: 700, fontSize: "1.15rem", color: "var(--foreground)", margin: "0 0 8px" }}>Graceful Shutdown</h3>
            <p style={{ fontFamily: "var(--font-sans)", fontSize: "0.85rem", color: "var(--muted-foreground)", lineHeight: 1.65, margin: "0 0 24px" }}>
              MIND-FLOW will save your session, log your current state, and quietly exit.
            </p>
            <div style={{ display: "flex", gap: 10 }}>
              <button onClick={() => setShowShutdown(false)} style={{ flex: 1, padding: "10px", borderRadius: 12, border: "1px solid var(--border)", fontFamily: "var(--font-sans)", fontSize: "0.85rem", color: "var(--muted-foreground)", background: "var(--muted)", cursor: "pointer" }}>
                Cancel
              </button>
              <button
                onClick={async () => {
                  try {
                    const qs = window.location.search;
                    await fetch(`/api/shutdown${qs}`, { method: "POST" });
                  } catch (e) {}
                  setShowShutdown(false);
                }}
                style={{ flex: 1, padding: "10px", borderRadius: 12, border: "none", fontFamily: "var(--font-sans)", fontSize: "0.85rem", color: "var(--destructive-foreground)", background: "var(--destructive)", cursor: "pointer" }}
              >
                Shut Down
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
