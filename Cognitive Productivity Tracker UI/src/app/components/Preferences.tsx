import { useState, useEffect } from "react";
import {
  AlertTriangle, Power, PauseCircle, Brain, Clock, Zap,
  Droplets, Moon, Footprints, Timer, Coffee, Wind,
  ChevronRight, Palette, Check,
} from "lucide-react";
import { BASE_WORK, BASE_REST } from "../hooks/useStaminaEngine";

// ─── Theme definitions ─────────────────────────────────────────────────────────
export type ThemeId = "zenith" | "cosmic" | "ocean" | "forest" | "solar";

export interface ThemeConfig {
  id: ThemeId;
  name: string;
  sub: string;
  palette: string[];
  fg: string;
  cardBg: string;
  pageBg: string;
  primary: string;
  muted: string;
  mutedFg: string;
  border: string;
  secondaryBg: string;
  navActiveBg: string;
  navActiveAccent: string;
  vars: Record<string, string>;
}

export const THEMES: Record<ThemeId, ThemeConfig> = {
  zenith: {
    id: "zenith",
    name: "Zenith Ethereal",
    sub: "Sage & Blush — default calm",
    palette: ["#F7F5F0", "#FDFCF9", "#8FA08D", "#C5A882", "#7A9BAA"],
    fg: "#2D312E",
    cardBg: "#FDFCF9",
    pageBg: "#F7F5F0",
    primary: "#8FA08D",
    muted: "#EDE8DF",
    mutedFg: "#7D8579",
    border: "rgba(45,49,46,0.1)",
    secondaryBg: "#EDE8DF",
    navActiveBg: "#E4EDE3",
    navActiveAccent: "#8FA08D",
    vars: {
      "--background": "#F7F5F0",
      "--foreground": "#2D312E",
      "--card": "#FDFCF9",
      "--card-foreground": "#2D312E",
      "--primary": "#8FA08D",
      "--primary-foreground": "#FDFCF9",
      "--secondary": "#EDE8DF",
      "--secondary-foreground": "#2D312E",
      "--muted": "#EDE8DF",
      "--muted-foreground": "#7D8579",
      "--accent": "#8FA08D",
      "--accent-foreground": "#FDFCF9",
      "--border": "rgba(45, 49, 46, 0.1)",
      "--ring": "#8FA08D",
      "--input-background": "#F0EDE6",
      "--switch-background": "#C5BDAF",
    },
  },
  cosmic: {
    id: "cosmic",
    name: "Cosmic Flow",
    sub: "Violet — deep space focus",
    palette: ["#1A1526", "#231D35", "#9B7FD4", "#C5A8D4", "#6A5AAA"],
    fg: "#E8E0F4",
    cardBg: "#231D35",
    pageBg: "#1A1526",
    primary: "#9B7FD4",
    muted: "#2D2540",
    mutedFg: "#9A8FB5",
    border: "rgba(155,127,212,0.18)",
    secondaryBg: "#2D2540",
    navActiveBg: "rgba(155,127,212,0.15)",
    navActiveAccent: "#9B7FD4",
    vars: {
      "--background": "#1A1526",
      "--foreground": "#E8E0F4",
      "--card": "#231D35",
      "--card-foreground": "#E8E0F4",
      "--primary": "#9B7FD4",
      "--primary-foreground": "#1A1526",
      "--secondary": "#2D2540",
      "--secondary-foreground": "#E8E0F4",
      "--muted": "#2D2540",
      "--muted-foreground": "#9A8FB5",
      "--accent": "#7B5FC4",
      "--accent-foreground": "#E8E0F4",
      "--border": "rgba(155, 127, 212, 0.18)",
      "--ring": "#9B7FD4",
      "--input-background": "#2D2540",
      "--switch-background": "#4A3F6A",
    },
  },
  ocean: {
    id: "ocean",
    name: "Ocean Waves",
    sub: "Teal — deep water clarity",
    palette: ["#0C1E2A", "#132A38", "#4AACBC", "#7DC5D2", "#2A8090"],
    fg: "#D4EEF5",
    cardBg: "#132A38",
    pageBg: "#0C1E2A",
    primary: "#4AACBC",
    muted: "#1A3545",
    mutedFg: "#7AAAB8",
    border: "rgba(74,172,188,0.18)",
    secondaryBg: "#1A3545",
    navActiveBg: "rgba(74,172,188,0.14)",
    navActiveAccent: "#4AACBC",
    vars: {
      "--background": "#0C1E2A",
      "--foreground": "#D4EEF5",
      "--card": "#132A38",
      "--card-foreground": "#D4EEF5",
      "--primary": "#4AACBC",
      "--primary-foreground": "#0C1E2A",
      "--secondary": "#1A3545",
      "--secondary-foreground": "#D4EEF5",
      "--muted": "#1A3545",
      "--muted-foreground": "#7AAAB8",
      "--accent": "#3A9CAC",
      "--accent-foreground": "#D4EEF5",
      "--border": "rgba(74, 172, 188, 0.18)",
      "--ring": "#4AACBC",
      "--input-background": "#1A3545",
      "--switch-background": "#2A5060",
    },
  },
  forest: {
    id: "forest",
    name: "Forest Light",
    sub: "Green — dappled daylight",
    palette: ["#EFF5EC", "#F8FCF6", "#5A8A5A", "#A8C5A6", "#3D6B4A"],
    fg: "#1E3020",
    cardBg: "#F8FCF6",
    pageBg: "#EFF5EC",
    primary: "#5A8A5A",
    muted: "#D4E8CF",
    mutedFg: "#5A7060",
    border: "rgba(30,48,32,0.1)",
    secondaryBg: "#D4E8CF",
    navActiveBg: "#D4E8CF",
    navActiveAccent: "#5A8A5A",
    vars: {
      "--background": "#EFF5EC",
      "--foreground": "#1E3020",
      "--card": "#F8FCF6",
      "--card-foreground": "#1E3020",
      "--primary": "#5A8A5A",
      "--primary-foreground": "#F8FCF6",
      "--secondary": "#D4E8CF",
      "--secondary-foreground": "#1E3020",
      "--muted": "#D4E8CF",
      "--muted-foreground": "#5A7060",
      "--accent": "#3D6B4A",
      "--accent-foreground": "#F8FCF6",
      "--border": "rgba(30, 48, 32, 0.1)",
      "--ring": "#5A8A5A",
      "--input-background": "#E2EFE0",
      "--switch-background": "#8AB58A",
    },
  },
  solar: {
    id: "solar",
    name: "Solar Breeze",
    sub: "Amber — warm golden morning",
    palette: ["#FFFDF5", "#FDFAF0", "#C49A20", "#E8C840", "#8A6A10"],
    fg: "#3A2E00",
    cardBg: "#FDFAF0",
    pageBg: "#FFFDF5",
    primary: "#C49A20",
    muted: "#F5ECC8",
    mutedFg: "#7A6A30",
    border: "rgba(58,46,0,0.1)",
    secondaryBg: "#F5ECC8",
    navActiveBg: "#EDE5B0",
    navActiveAccent: "#C49A20",
    vars: {
      "--background": "#FFFDF5",
      "--foreground": "#3A2E00",
      "--card": "#FDFAF0",
      "--card-foreground": "#3A2E00",
      "--primary": "#C49A20",
      "--primary-foreground": "#FFFDF5",
      "--secondary": "#F5ECC8",
      "--secondary-foreground": "#3A2E00",
      "--muted": "#F5ECC8",
      "--muted-foreground": "#7A6A30",
      "--accent": "#A07A10",
      "--accent-foreground": "#FFFDF5",
      "--border": "rgba(58, 46, 0, 0.1)",
      "--ring": "#C49A20",
      "--input-background": "#F0E8C0",
      "--switch-background": "#C5B080",
    },
  },
};

// ─── Shared component ──────────────────────────────────────────────────────────
function Toggle({ checked, onChange }: { checked: boolean; onChange: () => void }) {
  return (
    <button
      onClick={onChange}
      className="relative flex-shrink-0 w-10 h-5 rounded-full transition-colors duration-200"
      style={{ background: checked ? "var(--primary)" : "var(--switch-background)" }}
    >
      <div
        className="absolute top-0.5 w-4 h-4 rounded-full bg-white shadow-sm transition-transform duration-200"
        style={{ transform: checked ? "translateX(22px)" : "translateX(2px)" }}
      />
    </button>
  );
}

const SECTION_LABEL: React.CSSProperties = {
  fontFamily: "'DM Sans', sans-serif",
  fontSize: "0.65rem",
  letterSpacing: "0.12em",
  color: "var(--muted-foreground)",
  textTransform: "uppercase" as const,
};

const CARD: React.CSSProperties = {
  background: "var(--card)",
  border: "1px solid var(--border)",
  borderRadius: 20,
  padding: "22px 24px",
  boxShadow: "0 4px 20px rgba(0,0,0,0.05)",
};

// ─── Props ─────────────────────────────────────────────────────────────────────
interface Props {
  autopilot: boolean;
  workKw: string;
  rechargeKw: string;
  fatigue: number;
  adaptedWorkSecs: number;
  activeTheme: ThemeId;
  onSetAutopilot: (v: boolean) => void;
  onSetWorkKw: (v: string) => void;
  onSetRechargeKw: (v: string) => void;
  onSetTheme: (id: ThemeId) => void;
}

// ─── Target Config ─────────────────────────────────────────────────────────────
function TargetConfig() {
  const [sleepTarget, setSleepTarget] = useState(8);
  const [stepsTarget, setStepsTarget] = useState(8000);
  const [waterUnit, setWaterUnit] = useState<"cups" | "ml" | "oz">("cups");
  const [waterTarget, setWaterTarget] = useState(8);

  const waterMax = waterUnit === "cups" ? 16 : waterUnit === "ml" ? 4000 : 128;
  const waterStep = waterUnit === "cups" ? 0.5 : waterUnit === "ml" ? 100 : 4;
  const waterLabel = waterUnit === "cups" ? `${waterTarget} cups` : waterUnit === "ml" ? `${waterTarget} ml` : `${waterTarget} oz`;

  return (
    <div style={CARD}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 20 }}>
        <div style={{ width: 28, height: 28, borderRadius: 10, background: "var(--muted)", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Droplets size={13} style={{ color: "var(--primary)" }} />
        </div>
        <div>
          <div style={{ fontFamily: "'Lora', serif", fontSize: "0.95rem", color: "var(--foreground)" }}>Daily Targets</div>
          <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.6rem", color: "var(--muted-foreground)", letterSpacing: "0.06em" }}>Sleep · Steps · Hydration</div>
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        {/* Sleep */}
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <Moon size={12} style={{ color: "var(--primary)" }} />
              <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.84rem", color: "var(--foreground)" }}>Sleep Target</span>
            </div>
            <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.84rem", color: "var(--primary)" }}>{sleepTarget}h</span>
          </div>
          <input
            type="range" min={4} max={12} step={0.5} value={sleepTarget}
            onChange={(e) => setSleepTarget(Number(e.target.value))}
            style={{ width: "100%", accentColor: "var(--primary)" }}
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
              <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.84rem", color: "var(--foreground)" }}>Daily Steps</span>
            </div>
            <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.84rem", color: "var(--primary)" }}>{stepsTarget.toLocaleString()}</span>
          </div>
          <input
            type="range" min={1000} max={20000} step={500} value={stepsTarget}
            onChange={(e) => setStepsTarget(Number(e.target.value))}
            style={{ width: "100%", accentColor: "var(--primary)" }}
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
              <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.84rem", color: "var(--foreground)" }}>Water Intake</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <div style={{ display: "flex", borderRadius: 8, overflow: "hidden", border: "1px solid var(--border)" }}>
                {(["cups", "ml", "oz"] as const).map((u) => (
                  <button
                    key={u}
                    onClick={() => { setWaterUnit(u); setWaterTarget(u === "cups" ? 8 : u === "ml" ? 2000 : 64); }}
                    style={{
                      padding: "3px 8px", border: "none", cursor: "pointer",
                      fontFamily: "'DM Mono', monospace", fontSize: "0.62rem",
                      background: waterUnit === u ? "var(--primary)" : "transparent",
                      color: waterUnit === u ? "var(--primary-foreground)" : "var(--muted-foreground)",
                      transition: "all 0.15s",
                    }}
                  >{u}</button>
                ))}
              </div>
              <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.84rem", color: "var(--primary)" }}>{waterLabel}</span>
            </div>
          </div>
          <input
            type="range" min={waterUnit === "cups" ? 1 : waterUnit === "ml" ? 250 : 8} max={waterMax} step={waterStep} value={waterTarget}
            onChange={(e) => setWaterTarget(Number(e.target.value))}
            style={{ width: "100%", accentColor: "var(--primary)" }}
          />
        </div>
      </div>
    </div>
  );
}

// ─── Pacing Sensitivities ──────────────────────────────────────────────────────
function PacingConfig({ adaptedWorkSecs, fatigue }: { adaptedWorkSecs: number; fatigue: number }) {
  const [workBlock, setWorkBlock] = useState(Math.floor(BASE_WORK / 60));
  const [restDuration, setRestDuration] = useState(Math.floor(BASE_REST / 60));
  const [idleTimeout, setIdleTimeout] = useState(3);
  const [zenLevel, setZenLevel] = useState<"whisper" | "drift" | "deep" | "void">("drift");

  const ZEN_LEVELS = [
    { id: "whisper" as const, label: "Whisper", sub: "Subtle ambient, light blur", icon: "◌" },
    { id: "drift" as const, label: "Drift", sub: "Soft sound, gentle transitions", icon: "◎" },
    { id: "deep" as const, label: "Deep", sub: "Immersive soundscape, full dim", icon: "●" },
    { id: "void" as const, label: "Void", sub: "Total silence, max blackout", icon: "◉" },
  ];

  const workReduction = Math.round((BASE_WORK / 60) - workBlock);

  return (
    <div style={CARD}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 20 }}>
        <div style={{ width: 28, height: 28, borderRadius: 10, background: "var(--muted)", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Timer size={13} style={{ color: "var(--primary)" }} />
        </div>
        <div>
          <div style={{ fontFamily: "'Lora', serif", fontSize: "0.95rem", color: "var(--foreground)" }}>Pacing Sensitivities</div>
          <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.6rem", color: "var(--muted-foreground)", letterSpacing: "0.06em" }}>Block timings · Zen preset</div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 20 }}>
        {[
          { label: "Work Block Limit", icon: <Clock size={11} />, value: workBlock, set: setWorkBlock, min: 10, max: 90, step: 5, unit: "min", note: workBlock < 25 ? `${25 - workBlock}m below baseline` : workBlock > 25 ? `+${workBlock - 25}m above baseline` : "At baseline" },
          { label: "Rest Duration", icon: <Wind size={11} />, value: restDuration, set: setRestDuration, min: 2, max: 30, step: 1, unit: "min", note: `~${Math.round(restDuration / workBlock * 100)}% of work block` },
          { label: "Idle Timeout", icon: <Zap size={11} />, value: idleTimeout, set: setIdleTimeout, min: 1, max: 15, step: 1, unit: "min", note: "Auto-pause on inactivity" },
          { label: "Recharge Block", icon: <Brain size={11} />, value: 15, set: () => {}, min: 5, max: 30, step: 5, unit: "min", note: "Walk / stretching window" },
        ].map(({ label, icon, value, set, min, max, step, unit, note }) => (
          <div key={label} style={{ padding: "14px 16px", borderRadius: 14, background: "var(--muted)", border: "1px solid var(--border)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 5, marginBottom: 8 }}>
              <span style={{ color: "var(--primary)" }}>{icon}</span>
              <span style={{ ...SECTION_LABEL }}>{label}</span>
            </div>
            <div style={{ fontFamily: "'Lora', serif", fontSize: "1.3rem", color: "var(--foreground)", marginBottom: 6 }}>
              {value}<span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.7rem", color: "var(--muted-foreground)", marginLeft: 3 }}>{unit}</span>
            </div>
            <input
              type="range" min={min} max={max} step={step} value={value}
              onChange={(e) => set(Number(e.target.value))}
              style={{ width: "100%", accentColor: "var(--primary)", marginBottom: 6 }}
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
              onClick={() => setZenLevel(id)}
              style={{
                padding: "12px 10px", borderRadius: 12, cursor: "pointer", textAlign: "center",
                background: zenLevel === id ? "var(--primary)" : "var(--muted)",
                border: `1px solid ${zenLevel === id ? "transparent" : "var(--border)"}`,
                transition: "all 0.2s",
              }}
            >
              <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "1.1rem", marginBottom: 4, color: zenLevel === id ? "var(--primary-foreground)" : "var(--foreground)" }}>{icon}</div>
              <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.78rem", color: zenLevel === id ? "var(--primary-foreground)" : "var(--foreground)", marginBottom: 2 }}>{label}</div>
              <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.58rem", color: zenLevel === id ? `${THEMES.zenith.cardBg}99` : "var(--muted-foreground)", lineHeight: 1.4 }}>{sub}</div>
            </button>
          ))}
        </div>
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
                <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.9rem", color: "var(--foreground)", marginBottom: 2 }}>{theme.name}</div>
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
  autopilot, workKw, rechargeKw, fatigue, adaptedWorkSecs,
  activeTheme,
  onSetAutopilot, onSetWorkKw, onSetRechargeKw, onSetTheme,
}: Props) {
  const [autoSwap, setAutoSwap] = useState(false);
  const [eyeCare, setEyeCare] = useState(true);
  const [showShutdown, setShowShutdown] = useState(false);
  const [activeTab, setActiveTab] = useState<"autopilot" | "targets" | "pacing" | "theme">("autopilot");

  const workReduction = Math.round((BASE_WORK - adaptedWorkSecs) / 60);
  const fatigueLevel = fatigue < 30 ? "Low" : fatigue < 55 ? "Moderate" : fatigue < 75 ? "High" : "Critical";
  const fatigueLevelColor = fatigue < 30 ? "var(--primary)" : fatigue < 55 ? "#C5A882" : "#C17B6B";

  const TABS: { id: typeof activeTab; label: string }[] = [
    { id: "autopilot", label: "Classifier & Autopilot" },
    { id: "targets", label: "Daily Targets" },
    { id: "pacing", label: "Pacing & Zen" },
    { id: "theme", label: "Themes" },
  ];

  return (
    <div className="flex flex-col h-full" style={{ background: "var(--background)" }}>
      {/* Header */}
      <div style={{ padding: "24px 32px 0", background: "var(--card)", borderBottom: "1px solid var(--border)" }}>
        <div style={{ marginBottom: 16 }}>
          <h2 style={{ fontFamily: "'Lora', serif", fontWeight: 500, color: "var(--foreground)", margin: 0, fontSize: "1.35rem" }}>
            Preferences & Customization
          </h2>
          <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.8rem", color: "var(--muted-foreground)", margin: "4px 0 0" }}>
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
                fontFamily: "'DM Sans', sans-serif", fontSize: "0.8rem",
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
      <div className="flex-1 overflow-y-auto" style={{ padding: "24px 32px", display: "flex", flexDirection: "column", gap: 18 }}>
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
              <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.8rem", color: "var(--muted-foreground)", lineHeight: 1.6, marginBottom: 16 }}>
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
                    <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.9rem", color: "var(--foreground)" }}>{value}</div>
                    <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.65rem", color: "var(--muted-foreground)", marginTop: 2 }}>{label}</div>
                    <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.58rem", color, marginTop: 2 }}>{sub}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Classifier Keywords */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              {[
                { title: "Work Keywords", value: workKw, set: onSetWorkKw, color: "var(--primary)", bg: "var(--muted)" },
                { title: "Recharge Keywords", value: rechargeKw, set: onSetRechargeKw, color: "#7A9BAA", bg: "var(--muted)" },
              ].map(({ title, value, set, color, bg }) => (
                <div key={title} style={CARD}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
                    <span style={{ width: 8, height: 8, borderRadius: 2, background: color, display: "inline-block" }} />
                    <span style={{ ...SECTION_LABEL }}>{title}</span>
                  </div>
                  <textarea
                    value={value}
                    onChange={(e) => set(e.target.value)}
                    rows={7}
                    style={{
                      width: "100%", borderRadius: 12, padding: "10px 14px",
                      border: "1px solid var(--border)", outline: "none", resize: "none",
                      fontFamily: "'DM Mono', monospace", fontSize: "0.8rem",
                      background: bg, color: "var(--foreground)", lineHeight: 1.8, boxSizing: "border-box",
                    }}
                  />
                  <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.68rem", color: "var(--muted-foreground)", marginTop: 6 }}>
                    One keyword per line · Applied to active window title in real-time
                  </div>
                </div>
              ))}
            </div>

            {/* System Toggles */}
            <div style={CARD}>
              <div style={{ ...SECTION_LABEL, marginBottom: 14 }}>System Toggles</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                {[
                  { label: "Eye Care Shield", sub: "20-20-20 reminders every 20 minutes", val: eyeCare, set: setEyeCare },
                  { label: "Auto-clear Desktop on Profile Switch", sub: "Moves files to a temporary swap folder before switching", val: autoSwap, set: setAutoSwap },
                ].map(({ label, sub, val, set }) => (
                  <div key={label} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "4px 0" }}>
                    <div>
                      <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.88rem", color: "var(--foreground)" }}>{label}</div>
                      <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.75rem", color: "var(--muted-foreground)" }}>{sub}</div>
                    </div>
                    <Toggle checked={val} onChange={() => set((v: boolean) => !v)} />
                  </div>
                ))}
              </div>
              <div style={{ display: "flex", alignItems: "flex-start", gap: 10, padding: "12px 14px", borderRadius: 12, background: "rgba(197,168,130,0.08)", border: "1px solid rgba(197,168,130,0.25)", marginTop: 14 }}>
                <AlertTriangle size={13} style={{ color: "#C5A882", marginTop: 1, flexShrink: 0 }} />
                <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.76rem", color: "var(--muted-foreground)", lineHeight: 1.55 }}>
                  <strong style={{ color: "#C5A882" }}>Cloud Sync Detected:</strong> Auto-clear disabled while OneDrive is active.
                </span>
              </div>
            </div>
          </>
        )}

        {activeTab === "targets" && <TargetConfig />}
        {activeTab === "pacing" && <PacingConfig adaptedWorkSecs={adaptedWorkSecs} fatigue={fatigue} />}
        {activeTab === "theme" && <ThemeSelector activeTheme={activeTheme} onSetTheme={onSetTheme} />}
      </div>

      {/* Bottom Bar */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 32px", background: "var(--card)", borderTop: "1px solid var(--border)", flexShrink: 0 }}>
        <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.68rem", color: "var(--muted-foreground)", letterSpacing: "0.06em" }}>
          MIND-FLOW v2.4.1 · Session #142 · {THEMES[activeTheme].name}
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <button
            style={{
              display: "flex", alignItems: "center", gap: 7, padding: "8px 18px", borderRadius: 12, border: "1px solid var(--border)", cursor: "pointer",
              fontFamily: "'DM Sans', sans-serif", fontSize: "0.82rem", color: "var(--muted-foreground)", background: "var(--muted)",
            }}
          >
            <PauseCircle size={14} />Pause Companion
          </button>
          <button
            onClick={() => setShowShutdown(true)}
            style={{
              display: "flex", alignItems: "center", gap: 7, padding: "8px 18px", borderRadius: 12, cursor: "pointer",
              fontFamily: "'DM Sans', sans-serif", fontSize: "0.82rem", color: "#C17B6B",
              background: "rgba(193,123,107,0.08)", border: "1px solid rgba(193,123,107,0.28)",
            }}
          >
            <Power size={14} />Graceful Shutdown
          </button>
        </div>
      </div>

      {showShutdown && (
        <div style={{ position: "fixed", inset: 0, zIndex: 50, display: "flex", alignItems: "center", justifyContent: "center", background: "rgba(0,0,0,0.35)", backdropFilter: "blur(4px)" }}>
          <div style={{ ...CARD, maxWidth: 380, width: "100%", margin: "0 24px" }}>
            <h3 style={{ fontFamily: "'Lora', serif", fontSize: "1.15rem", color: "var(--foreground)", margin: "0 0 8px" }}>Graceful Shutdown</h3>
            <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.85rem", color: "var(--muted-foreground)", lineHeight: 1.65, margin: "0 0 24px" }}>
              MIND-FLOW will save your session, log your current state, and quietly exit.
            </p>
            <div style={{ display: "flex", gap: 10 }}>
              <button onClick={() => setShowShutdown(false)} style={{ flex: 1, padding: "10px", borderRadius: 12, border: "1px solid var(--border)", fontFamily: "'DM Sans', sans-serif", fontSize: "0.85rem", color: "var(--muted-foreground)", background: "var(--muted)", cursor: "pointer" }}>
                Cancel
              </button>
              <button style={{ flex: 1, padding: "10px", borderRadius: 12, border: "none", fontFamily: "'DM Sans', sans-serif", fontSize: "0.85rem", color: "#FDFCF9", background: "#C17B6B", cursor: "pointer" }}>
                Shut Down
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
