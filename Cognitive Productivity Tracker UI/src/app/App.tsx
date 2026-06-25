import { useState, useEffect, useCallback } from "react";
import {
  LayoutDashboard, BarChart2, Leaf, Settings2,
  ShieldAlert, ShieldCheck, ShieldOff, RefreshCw, PanelLeftClose, PanelLeft,
} from "lucide-react";
import { Toaster, toast } from "sonner";
import { Dashboard } from "./components/Dashboard";
import { Analytics } from "./components/Analytics";
import { ZenSpace } from "./components/ZenSpace";
import { Preferences, THEMES, ThemeId } from "./components/Preferences";
import { BreakOverlay } from "./components/BreakOverlay";
import { useStaminaEngine, AppMode } from "./hooks/useStaminaEngine";
import { useLocalStorage } from "./hooks/useLocalStorage";

type Screen = "dashboard" | "analytics" | "zen" | "preferences";

export type AppTally = { work: number; recharge: number; neutral: number };

const NAV: { id: Screen; label: string; Icon: typeof LayoutDashboard; hint: string; key: string }[] = [
  { id: "dashboard",   label: "Zen Hub",     Icon: LayoutDashboard, hint: "Focus dashboard",  key: "1" },
  { id: "analytics",   label: "Energy Map",  Icon: BarChart2,       hint: "Weekly trends",    key: "2" },
  { id: "zen",         label: "Zen Space",   Icon: Leaf,            hint: "Sensory recovery", key: "3" },
  { id: "preferences", label: "Preferences", Icon: Settings2,       hint: "Config & rules",   key: "4" },
];

function fmtElapsed(ms: number) {
  const s = Math.floor(ms / 1000);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

function shieldConfig(mode: AppMode, battery: number, primary: string) {
  if (mode === "rest")     return { label: "Shield Resting",    color: "#C5A882", bg: "rgba(197,168,130,0.12)", Icon: ShieldOff };
  if (mode === "recharge") return { label: "Shield Recharging", color: "#7A9BAA", bg: "rgba(122,155,170,0.12)", Icon: RefreshCw };
  if (battery > 55) return { label: "Shield Active",  color: primary,   bg: `${primary}1E`,            Icon: ShieldCheck };
  if (battery > 25) return { label: "Shield Partial", color: "#C5A882", bg: "rgba(197,168,130,0.12)",  Icon: ShieldAlert };
  return               { label: "Shield Critical", color: "#C17B6B", bg: "rgba(193,123,107,0.12)", Icon: ShieldAlert };
}

export default function App() {
  const [screen, setScreen]           = useLocalStorage<Screen>("mindflow_screen", "dashboard");
  const [manualBreak, setManualBreak] = useState(false);
  const [hoveredNav, setHoveredNav]   = useState<Screen | null>(null);
  const [collapsed, setCollapsed]     = useLocalStorage("mindflow_sidebar_collapsed", false);

  // ── Theme — persisted ──────────────────────────────────────────────────────
  const [activeTheme, setActiveTheme] = useLocalStorage<ThemeId>("mindflow_theme", "zenith");
  const theme = THEMES[activeTheme];

  const handleSetTheme = (id: ThemeId) => {
    setActiveTheme(id);
    toast.success(`Theme switched to ${THEMES[id].name}`, { description: THEMES[id].sub });
  };

  useEffect(() => {
    const root = document.documentElement;
    Object.entries(theme.vars).forEach(([k, v]) => root.style.setProperty(k, v));
  }, [theme]);

  // ── Session timer ──────────────────────────────────────────────────────────
  const [sessionStart] = useState(() => Date.now());
  const [sessionElapsed, setSessionElapsed] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setSessionElapsed(Date.now() - sessionStart), 1000);
    return () => clearInterval(id);
  }, [sessionStart]);

  // ── App classification tally ────────────────────────────────────────────────
  const [appTally, setAppTally] = useState<AppTally>({ work: 0, recharge: 0, neutral: 0 });
  const engine = useStaminaEngine();
  useEffect(() => {
    const cls = engine.classifiedApp;
    const id = setInterval(() => setAppTally(prev => ({ ...prev, [cls]: prev[cls] + 1 })), 1000);
    return () => clearInterval(id);
  }, [engine.classifiedApp]);

  const { battery, mode } = engine;
  const shield = shieldConfig(mode, battery, theme.primary);
  const ShieldIcon = shield.Icon;
  const showBreak = mode === "rest" || manualBreak;

  const triggerBreak = useCallback(() => {
    setManualBreak(true);
    toast("Break started", { description: "Step away — your shield is holding.", icon: "🧘" });
  }, []);

  const handleBreakDismiss = () => {
    if (mode === "rest") engine.setMode("work");
    setManualBreak(false);
  };

  // ── Keyboard shortcuts ──────────────────────────────────────────────────────
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // ignore when typing in a field
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || (e.target as HTMLElement)?.isContentEditable) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;

      const nav = NAV.find(n => n.key === e.key);
      if (nav) { setScreen(nav.id); return; }
      if (e.key.toLowerCase() === "b") { triggerBreak(); return; }
      if (e.key === "[") setCollapsed(c => !c);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setScreen, triggerBreak, setCollapsed]);

  // Toast when battery hits critical
  const [warnedCritical, setWarnedCritical] = useState(false);
  useEffect(() => {
    if (battery <= 20 && !warnedCritical) {
      setWarnedCritical(true);
      toast.warning("Mental battery critical", { description: "Consider a rest block to recover focus." });
    }
    if (battery > 35 && warnedCritical) setWarnedCritical(false);
  }, [battery, warnedCritical]);

  const batterySegments = 5;
  const filledSegments  = Math.round((battery / 100) * batterySegments);
  const sidebarW = collapsed ? 72 : 212;

  return (
    <div className="size-full flex" style={{ fontFamily: "'DM Sans', sans-serif", background: theme.pageBg, color: theme.fg, transition: "background 0.4s ease" }}>
      <Toaster
        position="bottom-right"
        toastOptions={{
          style: {
            background: theme.cardBg, color: theme.fg,
            border: `1px solid ${theme.border}`,
            fontFamily: "'DM Sans', sans-serif", borderRadius: "14px",
          },
        }}
      />

      {/* ── Sidebar ──────────────────────────────────────────────────────── */}
      <aside
        className="flex flex-col py-7 shrink-0"
        style={{
          width: sidebarW, paddingLeft: collapsed ? 10 : 16, paddingRight: collapsed ? 10 : 16, gap: 4,
          background: theme.cardBg, borderRight: `1px solid ${theme.border}`,
          boxShadow: "2px 0 24px rgba(0,0,0,0.05)",
          transition: "width 0.28s cubic-bezier(0.4,0,0.2,1), background 0.4s ease, padding 0.28s",
        }}
      >
        {/* Logo + collapse toggle */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: collapsed ? "center" : "space-between", paddingLeft: collapsed ? 0 : 6, paddingBottom: 18, paddingTop: 2 }}>
          {collapsed ? (
            <div style={{ width: 34, height: 34, borderRadius: 9, background: theme.primary, display: "flex", alignItems: "center", justifyContent: "center" }}>
              <span style={{ fontSize: 15, color: "#FDFCF9" }}>⬡</span>
            </div>
          ) : (
            <div style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "6px 10px", borderRadius: 10, background: `${theme.primary}14`, border: `1px solid ${theme.primary}28` }}>
              <div style={{ width: 22, height: 22, borderRadius: 7, background: theme.primary, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                <span style={{ fontSize: 11, color: "#FDFCF9" }}>⬡</span>
              </div>
              <div>
                <div style={{ fontFamily: "'Lora', serif", fontSize: "1rem", fontWeight: 600, color: theme.fg, letterSpacing: "-0.01em", lineHeight: 1 }}>MIND-FLOW</div>
                <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.52rem", color: theme.primary, letterSpacing: "0.1em", textTransform: "uppercase", marginTop: 1 }}>Cognitive Shield</div>
              </div>
            </div>
          )}
        </div>

        {/* Shield Status */}
        {!collapsed ? (
          <div style={{ paddingLeft: 6, paddingRight: 6, marginBottom: 12 }}>
            <div className="rounded-xl px-3 py-2.5 flex flex-col gap-1.5" style={{ background: shield.bg, border: `1px solid ${shield.color}33` }}>
              <div className="flex items-center gap-1.5">
                <ShieldIcon size={11} style={{ color: shield.color }} />
                <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.58rem", color: shield.color, letterSpacing: "0.1em", textTransform: "uppercase" }}>{shield.label}</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="flex gap-0.5 flex-1">
                  {Array.from({ length: batterySegments }).map((_, i) => (
                    <div key={i} style={{ flex: 1, height: 4, borderRadius: 2, background: i < filledSegments ? shield.color : `${shield.color}28`, transition: "background 0.5s ease" }} />
                  ))}
                </div>
                <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.65rem", color: shield.color }}>{Math.round(battery)}%</span>
              </div>
            </div>
          </div>
        ) : (
          <div title={`${shield.label} · ${Math.round(battery)}%`} style={{ display: "flex", justifyContent: "center", marginBottom: 12 }}>
            <div style={{ width: 36, height: 36, borderRadius: 10, background: shield.bg, border: `1px solid ${shield.color}33`, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
              <ShieldIcon size={13} style={{ color: shield.color }} />
              <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.5rem", color: shield.color, marginTop: 1 }}>{Math.round(battery)}</span>
            </div>
          </div>
        )}

        {/* Nav */}
        <nav className="flex flex-col flex-1" style={{ gap: 3 }}>
          {NAV.map(({ id, label, Icon, hint, key }) => {
            const active  = screen === id;
            const hovered = hoveredNav === id;
            return (
              <button
                key={id}
                onClick={() => setScreen(id)}
                onMouseEnter={() => setHoveredNav(id)}
                onMouseLeave={() => setHoveredNav(null)}
                title={collapsed ? `${label} (${key})` : undefined}
                className="flex items-center rounded-xl text-left transition-all duration-200"
                style={{
                  gap: collapsed ? 0 : 12,
                  justifyContent: collapsed ? "center" : "flex-start",
                  padding: collapsed ? "11px 0" : "10px 12px",
                  paddingLeft: collapsed ? 0 : active ? 14 : 12,
                  background: active ? theme.navActiveBg : hovered ? `${theme.muted}88` : "transparent",
                  boxShadow: active && !collapsed ? `inset 3px 0 0 ${theme.navActiveAccent}` : "none",
                }}
              >
                <Icon size={16} strokeWidth={active ? 2 : 1.5} style={{ color: active ? theme.navActiveAccent : hovered ? theme.fg : theme.mutedFg, transition: "color 0.2s", flexShrink: 0 }} />
                {!collapsed && (
                  <div className="flex-1 min-w-0">
                    <div style={{ fontSize: "0.85rem", fontWeight: active ? 500 : 400, color: active ? theme.fg : hovered ? theme.fg : theme.mutedFg, transition: "color 0.2s" }}>{label}</div>
                    <div style={{ fontSize: "0.6rem", color: theme.mutedFg, maxHeight: hovered && !active ? 14 : 0, overflow: "hidden", transition: "max-height 0.2s ease", fontFamily: "'DM Mono', monospace", letterSpacing: "0.04em" }}>{hint}</div>
                  </div>
                )}
                {!collapsed && (
                  <kbd style={{
                    fontFamily: "'DM Mono', monospace", fontSize: "0.58rem",
                    color: active ? theme.navActiveAccent : theme.mutedFg,
                    background: active ? `${theme.navActiveAccent}1A` : `${theme.muted}`,
                    border: `1px solid ${theme.border}`, borderRadius: 5,
                    padding: "1px 5px", lineHeight: 1.4, flexShrink: 0,
                    opacity: hovered || active ? 1 : 0.5, transition: "opacity 0.2s",
                  }}>{key}</kbd>
                )}
              </button>
            );
          })}
        </nav>

        {/* Force Break */}
        <button
          onClick={triggerBreak}
          title={collapsed ? "Force Break (B)" : undefined}
          className="flex items-center rounded-xl transition-all duration-200 mt-2 hover:opacity-90 active:scale-[0.97]"
          style={{
            gap: collapsed ? 0 : 12, justifyContent: "center",
            padding: collapsed ? "11px 0" : "10px 12px",
            background: "rgba(193,123,107,0.08)", color: "#C17B6B", border: "1px solid rgba(193,123,107,0.2)",
          }}
        >
          <ShieldAlert size={15} strokeWidth={1.5} />
          {!collapsed && <span style={{ fontSize: "0.82rem", flex: 1, textAlign: "left" }}>Force Break</span>}
          {!collapsed && <kbd style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.58rem", color: "#C17B6B", background: "rgba(193,123,107,0.1)", border: "1px solid rgba(193,123,107,0.25)", borderRadius: 5, padding: "1px 5px", lineHeight: 1.4 }}>B</kbd>}
        </button>

        {/* Collapse toggle + Session */}
        <div className="mt-2 pt-3" style={{ borderTop: `1px solid ${theme.border}` }}>
          <button
            onClick={() => setCollapsed(c => !c)}
            className="flex items-center rounded-lg transition-all duration-200 hover:opacity-80 w-full"
            style={{ gap: collapsed ? 0 : 8, justifyContent: collapsed ? "center" : "flex-start", padding: collapsed ? "8px 0" : "6px 8px", background: "transparent", border: "none", cursor: "pointer", marginBottom: collapsed ? 0 : 4 }}
            title={collapsed ? "Expand ([)" : "Collapse ([)"}
          >
            {collapsed ? <PanelLeft size={14} style={{ color: theme.mutedFg }} /> : <PanelLeftClose size={14} style={{ color: theme.mutedFg }} />}
            {!collapsed && <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.6rem", color: theme.mutedFg, letterSpacing: "0.04em" }}>Collapse</span>}
          </button>
          {!collapsed && (
            <div style={{ paddingLeft: 8 }}>
              <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.6rem", color: theme.mutedFg, letterSpacing: "0.06em", textTransform: "uppercase" }}>Session #142</div>
              <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.6rem", color: theme.primary, marginTop: 2 }}>Today · {fmtElapsed(sessionElapsed)}</div>
            </div>
          )}
        </div>
      </aside>

      {/* ── Main ─────────────────────────────────────────────────────────── */}
      <main className="flex-1 min-w-0 overflow-hidden relative">
        {screen === "dashboard" && (
          <Dashboard
            battery={engine.battery} mode={engine.mode}
            timerSeconds={engine.timerSeconds} timerMax={engine.timerMax}
            activeApp={engine.activeApp} classifiedApp={engine.classifiedApp}
            autopilot={engine.autopilot} energy={engine.energy} friction={engine.friction}
            sleep={engine.sleep} hydration={engine.hydration} fatigue={engine.fatigue}
            adaptedWorkSecs={engine.adaptedWorkSecs} adaptedRestSecs={engine.adaptedRestSecs}
            onSetMode={engine.setMode} onSetEnergy={engine.setEnergy} onSetFriction={engine.setFriction}
            onSetSleep={engine.setSleep} onSetHydration={engine.setHydration}
            onOverrideClassify={engine.overrideClassify}
          />
        )}
        {screen === "analytics" && <Analytics appTally={appTally} />}
        {screen === "zen"       && <ZenSpace />}
        {screen === "preferences" && (
          <Preferences
            autopilot={engine.autopilot} workKw={engine.workKw} rechargeKw={engine.rechargeKw}
            fatigue={engine.fatigue} adaptedWorkSecs={engine.adaptedWorkSecs}
            activeTheme={activeTheme}
            onSetAutopilot={engine.setAutopilot} onSetWorkKw={engine.setWorkKw}
            onSetRechargeKw={engine.setRechargeKw} onSetTheme={handleSetTheme}
          />
        )}
      </main>

      {showBreak && (
        <BreakOverlay
          onDismiss={handleBreakDismiss}
          isRestMode={mode === "rest"}
          restSecondsRemaining={mode === "rest" ? engine.timerSeconds : undefined}
          restSecondsMax={mode === "rest" ? engine.adaptedRestSecs : undefined}
        />
      )}
    </div>
  );
}
