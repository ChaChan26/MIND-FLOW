/**
 * Main application shell managing global state initialization, sidebar navigation, keyboard shortcuts, and theme contexts.
 *
 * Author: ChaChan26 <minhharry2006@gmail.com>
 * Copyright (c) 2026 ChaChan26. All rights reserved.
 */

import React, { useState, useEffect, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  LayoutDashboard, BarChart2, Leaf, Settings2,
  ShieldAlert, ShieldCheck, ShieldOff, RefreshCw, PanelLeftClose, PanelLeft, Trophy,
  Search, Keyboard, Sparkles, Activity
} from "lucide-react";
import { Toaster, toast } from "sonner";
import { Dashboard } from "./components/Dashboard";

const Analytics = React.lazy(() => import("./components/Analytics").then(m => ({ default: m.Analytics })));
const ZenSpace = React.lazy(() => import("./components/ZenSpace").then(m => ({ default: m.ZenSpace })));
const Achievements = React.lazy(() => import("./components/Achievements").then(m => ({ default: m.Achievements })));
const Preferences = React.lazy(() => import("./components/Preferences").then(m => ({ default: m.Preferences })));
import { BreakOverlay } from "./components/BreakOverlay";
import { ConstellationBg } from "./components/ConstellationBg";
import { Onboarding } from "./components/Onboarding";
import { CommandPalette } from "./components/CommandPalette";
import { ShortcutGuide } from "./components/ShortcutGuide";
import { CompanionMiniHud } from "./components/CompanionMiniHud";
import { useStaminaStore, useStaminaEngineInit, AppMode } from "./hooks/useStaminaEngine";
import { useLocalStorage } from "./hooks/useLocalStorage";

type Screen = "dashboard" | "analytics" | "zen" | "achievements" | "preferences";

export type AppTally = { work: number; recharge: number; neutral: number };

const NAV: { id: Screen; label: string; Icon: typeof LayoutDashboard; hint: string; key: string }[] = [
  { id: "dashboard",    label: "Home",              Icon: LayoutDashboard, hint: "Focus dashboard",    key: "1" },
  { id: "zen",          label: "Meditate",          Icon: Leaf,            hint: "Sensory recovery",   key: "2" },
  { id: "analytics",    label: "Analytics & Energy", Icon: BarChart2,       hint: "Weekly trends",      key: "3" },
  { id: "achievements", label: "Achievements",       Icon: Trophy,          hint: "Badges & milestones", key: "4" },
  { id: "preferences",  label: "Settings & Config", Icon: Settings2,       hint: "Config & rules",     key: "5" },
];

function fmtElapsed(ms: number) {
  const s = Math.floor(ms / 1000);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

function shieldConfig(mode: AppMode, battery: number) {
  if (mode === "rest")     return { label: "Shield Resting",    color: "var(--accent-3)", bg: "color-mix(in srgb, var(--accent-3) 12%, transparent)", Icon: ShieldOff };
  if (mode === "recharge") return { label: "Shield Recharging", color: "var(--accent-4)", bg: "color-mix(in srgb, var(--accent-4) 12%, transparent)", Icon: RefreshCw };
  if (battery > 55) return { label: "Shield Active",  color: "var(--primary)",   bg: "color-mix(in srgb, var(--primary) 12%, transparent)",  Icon: ShieldCheck };
  if (battery > 25) return { label: "Shield Partial", color: "var(--secondary)", bg: "color-mix(in srgb, var(--secondary) 12%, transparent)",Icon: ShieldAlert };
  return               { label: "Shield Critical", color: "var(--accent-1)", bg: "color-mix(in srgb, var(--accent-1) 12%, transparent)", Icon: ShieldAlert };
}

function SessionTimer({ start, color }: { start: number, color: string }) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const update = () => setElapsed(Date.now() - start);
    update();
    const intervalId = setInterval(update, 1000);
    return () => clearInterval(intervalId);
  }, [start]);
  return <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.6rem", color, marginTop: 2 }}>Today · {fmtElapsed(elapsed)}</div>;
}

class ErrorBoundary extends React.Component<{ children: React.ReactNode }, { hasError: boolean; error: Error | null }> {
  state = { hasError: false, error: null };
  static getDerivedStateFromError(error: Error) { return { hasError: true, error }; }
  componentDidCatch(error: Error) { console.error("UI ErrorBoundary caught error:", error); }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 40, color: "var(--destructive)", fontFamily: "var(--font-sans)" }}>
          <h3>Something went wrong rendering this view.</h3>
          <pre style={{ fontSize: "0.8rem", color: "var(--secondary)", background: "rgba(0,0,0,0.2)", padding: 12, borderRadius: "var(--radii-sm)", whiteSpace: "pre-wrap" }}>
            {this.state.error?.stack || String(this.state.error)}
          </pre>
          <button onClick={() => this.setState({ hasError: false, error: null })} style={{ padding: "8px 16px", borderRadius: "var(--radii-sm)", background: "var(--primary)", color: "var(--primary-foreground)", border: "none", cursor: "pointer", marginTop: 12 }}>
            Reload Component
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function App() {
  const initialScreen = (() => {
    try {
      const p = new URLSearchParams(window.location.search).get("screen");
      if (p && ["dashboard", "zen", "analytics", "achievements", "preferences"].includes(p)) return p as Screen;
    } catch (e) {}
    return "dashboard" as Screen;
  })();
  const [screen, setScreen]           = useLocalStorage<Screen>("mindflow_screen", initialScreen);
  const [manualBreak, setManualBreak] = useState(false);
  const [hoveredNav, setHoveredNav]   = useState<Screen | null>(null);
  const [collapsed, setCollapsed]     = useLocalStorage("mindflow_sidebar_collapsed", false);
  const [eyeCare, setEyeCare]         = useLocalStorage("mindflow_eyecare", false);
  const [autoSwap, setAutoSwap]       = useLocalStorage("mindflow_autoswap", false);
  const [hasCompletedOnboarding, setHasCompletedOnboarding] = useLocalStorage("mindflow_onboarded", false);

  // Command Palette & Shortcut Guide modals
  const [cmdOpen, setCmdOpen]           = useState(false);
  const [guideOpen, setGuideOpen]       = useState(false);
  const [miniHudOpen, setMiniHudOpen]   = useLocalStorage("mindflow_mini_hud", false);

  // Apply global eye care filter
  useEffect(() => {
    document.body.style.filter = eyeCare ? "sepia(0.2) brightness(0.88) saturate(0.85)" : "";
    return () => { document.body.style.filter = ""; };
  }, [eyeCare]);

  // ── Theme — persisted ──────────────────────────────────────────────────────
  const [activeTheme, setActiveTheme] = useLocalStorage<ThemeId>("mindflow_theme_v2", "silentmoon");
  const theme = THEMES[activeTheme] || THEMES.silentmoon;

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

  // ── App classification tally ────────────────────────────────────────────────
  useStaminaEngineInit();
  const battery = useStaminaStore(s => s.battery);
  const mode = useStaminaStore(s => s.mode);
  const setMode = useStaminaStore(s => s.setMode);
  const shield = shieldConfig(mode, battery);
  const ShieldIcon = shield.Icon;
  const showBreak = mode === "rest" || manualBreak;

  const triggerBreak = useCallback(() => {
    setManualBreak(true);
    toast("Break started", { description: "Step away — your shield is holding.", icon: "🧘" });
  }, []);

  const handleBreakDismiss = useCallback(() => {
    if (mode === "rest") setMode("work");
    setManualBreak(false);
  }, [mode, setMode]);

  // ── Keyboard shortcuts ──────────────────────────────────────────────────────
  useEffect(() => {
    const isInputActive = (target: HTMLElement | null): boolean => {
      if (!target) return false;
      const tag = target.tagName;
      const role = target.getAttribute?.("role");
      return (
        tag === "INPUT" ||
        tag === "TEXTAREA" ||
        target.isContentEditable ||
        role === "textbox"
      );
    };

    const onKey = (e: KeyboardEvent) => {
      // Ctrl+K / Cmd+K Command Palette trigger
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setCmdOpen(prev => !prev);
        return;
      }

      // ignore single-key shortcuts when typing in a field
      if (isInputActive(e.target as HTMLElement)) return;

      if (e.key === "?") {
        e.preventDefault();
        setGuideOpen(prev => !prev);
        return;
      }

      if (e.key === "Escape" && !collapsed) {
        setCollapsed(true);
        return;
      }

      if (e.metaKey || e.ctrlKey || e.altKey) return;

      const nav = NAV.find(n => n.key === e.key);
      if (nav) { setScreen(nav.id); return; }
      if (e.key.toLowerCase() === "b") { triggerBreak(); return; }
      if (e.key.toLowerCase() === "h") { setMiniHudOpen(h => !h); return; }
      if (e.key === "[") setCollapsed(c => !c);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setScreen, triggerBreak, setCollapsed, collapsed, setMiniHudOpen]);

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
  const RAIL_WIDTH = 68;
  const DRAWER_WIDTH = 236;

  if (!hasCompletedOnboarding) {
    return <Onboarding onComplete={() => setHasCompletedOnboarding(true)} />;
  }

  return (
    <div className="size-full flex" style={{ fontFamily: "'Nunito', sans-serif", background: theme.pageBg, color: theme.fg, transition: "background 0.4s ease" }}>
      <Toaster
        position="bottom-right"
        toastOptions={{
          style: {
            background: theme.cardBg, color: theme.fg,
            border: `1px solid ${theme.border}`,
            fontFamily: "'Nunito', sans-serif", borderRadius: "14px",
          },
        }}
      />

      {/* ── Docked Desktop Sidebar ── */}
      <aside
        className="flex flex-col select-none overflow-hidden h-screen"
        style={{
          width: collapsed ? RAIL_WIDTH : DRAWER_WIDTH,
          flexShrink: 0,
          paddingLeft: 10,
          paddingRight: 10,
          paddingTop: 18,
          paddingBottom: 16,
          gap: 4,
          background: theme.cardBg, 
          borderRight: `1px solid ${theme.border}`,
          boxShadow: collapsed ? "2px 0 12px rgba(0,0,0,0.02)" : "4px 0 20px rgba(0,0,0,0.04)",
          transition: "width 0.22s cubic-bezier(0.4,0,0.2,1)",
          zIndex: 30,
        }}
      >
        {/* Logo */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-start", padding: "0 10px", paddingBottom: 14 }}>
          <div style={{ width: 24, height: 24, borderRadius: 7, background: theme.primary, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
            <span style={{ fontSize: 13, color: "var(--primary-foreground)" }}>⬡</span>
          </div>
          <div
            className="flex-1 min-w-0 overflow-hidden"
            style={{
              opacity: collapsed ? 0 : 1,
              maxWidth: collapsed ? 0 : 160,
              marginLeft: collapsed ? 0 : 12,
              pointerEvents: collapsed ? "none" : "auto",
              transform: collapsed ? "translateX(-6px)" : "translateX(0)",
              transition: "opacity 0.18s ease, max-width 0.22s cubic-bezier(0.4,0,0.2,1), transform 0.18s ease, margin-left 0.22s ease",
            }}
          >
            <div style={{ fontFamily: "var(--font-sans)", fontSize: "0.95rem", fontWeight: 700, color: theme.fg, letterSpacing: "-0.01em", lineHeight: 1.1, whiteSpace: "nowrap" }}>
              MIND-FLOW <span style={{ fontSize: "0.5rem", background: "var(--primary)", color: "var(--card)", padding: "1px 4px", borderRadius: "4px", verticalAlign: "middle" }}>V2</span>
            </div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.5rem", color: theme.primary, letterSpacing: "0.08em", textTransform: "uppercase", marginTop: 2, whiteSpace: "nowrap" }}>Cognitive Shield</div>
          </div>
        </div>

        {/* Shield Status (Fixed vertical container with smooth height animation) */}
        <div style={{ padding: "0 2px", marginBottom: 6 }}>
          <div
            title={`${shield.label} · ${Math.round(battery)}%`}
            className="rounded-xl flex items-center"
            style={{
              background: shield.bg,
              border: `1px solid color-mix(in srgb, ${shield.color} 20%, transparent)`,
              height: collapsed ? 38 : 52,
              padding: collapsed ? "0 10px" : "8px 10px",
              overflow: "hidden",
              transition: "height 0.22s cubic-bezier(0.4,0,0.2,1), padding 0.22s ease",
            }}
          >
            <div style={{ width: 24, height: 24, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
              <ShieldIcon size={collapsed ? 14 : 12} style={{ color: shield.color }} />
            </div>
            <div
              className="flex flex-col gap-1 flex-1 min-w-0 overflow-hidden"
              style={{
                opacity: collapsed ? 0 : 1,
                maxWidth: collapsed ? 0 : 160,
                marginLeft: collapsed ? 0 : 10,
                pointerEvents: collapsed ? "none" : "auto",
                transition: "opacity 0.18s ease, max-width 0.22s cubic-bezier(0.4,0,0.2,1), margin-left 0.22s ease",
              }}
            >
              <div className="flex items-center justify-between">
                <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.56rem", color: shield.color, letterSpacing: "0.08em", textTransform: "uppercase", whiteSpace: "nowrap" }}>{shield.label}</span>
                <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.62rem", color: shield.color, fontWeight: 700 }}>{Math.round(battery)}%</span>
              </div>
              <div className="flex gap-0.5 w-full">
                {Array.from({ length: batterySegments }).map((_, i) => (
                  <div key={i} style={{ flex: 1, height: 3, borderRadius: 2, background: i < filledSegments ? shield.color : `color-mix(in srgb, ${shield.color} 20%, transparent)`, transition: "background 0.5s ease" }} />
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Theme Quick Switcher (Smooth height collapse to prevent nav buttons jumping) */}
        <div
          style={{
            maxHeight: collapsed ? 0 : 64,
            opacity: collapsed ? 0 : 1,
            overflow: "hidden",
            marginBottom: collapsed ? 0 : 8,
            padding: "0 2px",
            pointerEvents: collapsed ? "none" : "auto",
            transition: "max-height 0.22s cubic-bezier(0.4,0,0.2,1), opacity 0.18s ease, margin-bottom 0.22s ease",
          }}
        >
          <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.52rem", color: theme.mutedFg, letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 4, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span>Palette</span>
            <span style={{ fontSize: "0.5rem", color: theme.primary, fontWeight: 600 }}>{theme.name}</span>
          </div>
          <div style={{ display: "flex", gap: 4, padding: "4px 6px", borderRadius: 10, background: theme.muted, border: `1px solid ${theme.border}`, justifyContent: "space-between", alignItems: "center" }}>
            {(["silentmoon", "zenith", "cosmic", "ocean", "forest", "solar"] as ThemeId[]).map((tId) => {
              const tConf = THEMES[tId];
              const isSel = activeTheme === tId;
              return (
                <button
                  key={tId}
                  onClick={() => handleSetTheme(tId)}
                  title={`${tConf.name} (${tConf.sub})`}
                  style={{
                    width: 16, height: 16, borderRadius: "50%",
                    border: isSel ? `2px solid ${theme.fg}` : "1px solid transparent",
                    background: tConf.primary, cursor: "pointer", padding: 0,
                    transform: isSel ? "scale(1.2)" : "scale(0.95)",
                    boxShadow: isSel ? `0 2px 8px ${tConf.primary}66` : "none"
                  }}
                />
              );
            })}
          </div>
        </div>

        {/* Nav Items */}
        <nav className="flex flex-col flex-1 overflow-y-auto custom-scrollbar" style={{ gap: 3 }}>
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
                className="flex items-center w-full rounded-xl text-left transition-colors duration-150"
                style={{
                  height: 40,
                  padding: "0 10px",
                  justifyContent: "flex-start",
                  boxSizing: "border-box",
                  background: active ? theme.navActiveBg : hovered ? `${theme.muted}88` : "transparent",
                  boxShadow: active && !collapsed ? `inset 3px 0 0 ${theme.navActiveAccent}` : "none",
                  cursor: "pointer",
                  border: "none",
                }}
              >
                <div style={{ width: 24, height: 24, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                  <Icon size={16} strokeWidth={active ? 2 : 1.5} style={{ color: active ? theme.navActiveAccent : hovered ? theme.fg : theme.mutedFg, transition: "color 0.2s" }} />
                </div>
                <div
                  className="flex-1 min-w-0 flex items-center justify-between overflow-hidden"
                  style={{
                    opacity: collapsed ? 0 : 1,
                    maxWidth: collapsed ? 0 : 160,
                    marginLeft: collapsed ? 0 : 12,
                    pointerEvents: collapsed ? "none" : "auto",
                    transform: collapsed ? "translateX(-4px)" : "translateX(0)",
                    transition: "opacity 0.18s ease, max-width 0.22s cubic-bezier(0.4,0,0.2,1), transform 0.18s ease, margin-left 0.22s ease",
                  }}
                >
                  <div className="flex flex-col min-w-0">
                    <span style={{ fontSize: "0.82rem", fontWeight: active ? 600 : 400, color: active ? theme.fg : hovered ? theme.fg : theme.mutedFg, lineHeight: 1.2, whiteSpace: "nowrap" }}>{label}</span>
                    {hovered && !active && <span style={{ fontSize: "0.56rem", color: theme.mutedFg, whiteSpace: "nowrap" }}>{hint}</span>}
                  </div>
                  <kbd style={{
                    fontFamily: "'DM Mono', monospace", fontSize: "0.56rem",
                    color: active ? theme.navActiveAccent : theme.mutedFg,
                    background: active ? `${theme.navActiveAccent}1A` : `${theme.muted}`,
                    border: `1px solid ${theme.border}`, borderRadius: 4,
                    padding: "1px 4px", lineHeight: 1.3, flexShrink: 0,
                  }}>{key}</kbd>
                </div>
              </button>
            );
          })}
        </nav>

        {/* Action Buttons with Fixed Left Alignment */}
        <div style={{ display: "flex", flexDirection: "column", gap: 3, marginTop: "auto", paddingTop: 8 }}>
          {/* Force Break */}
          <button
            onClick={triggerBreak}
            title={collapsed ? "Force Break (B)" : undefined}
            className="flex items-center w-full rounded-xl transition-all duration-150 hover:opacity-90 active:scale-[0.98]"
            style={{
              height: 38,
              padding: "0 10px",
              justifyContent: "flex-start",
              background: "color-mix(in srgb, var(--destructive) 8%, transparent)",
              color: "var(--destructive)",
              border: "1px solid color-mix(in srgb, var(--destructive) 20%, transparent)",
              cursor: "pointer",
            }}
          >
            <div style={{ width: 24, height: 24, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
              <ShieldAlert size={15} strokeWidth={1.5} />
            </div>
            <div
              className="flex-1 min-w-0 flex items-center justify-between overflow-hidden"
              style={{
                opacity: collapsed ? 0 : 1,
                maxWidth: collapsed ? 0 : 160,
                marginLeft: collapsed ? 0 : 12,
                pointerEvents: collapsed ? "none" : "auto",
                transition: "opacity 0.18s ease, max-width 0.22s cubic-bezier(0.4,0,0.2,1), margin-left 0.22s ease",
              }}
            >
              <span style={{ fontSize: "0.8rem", fontWeight: 600, whiteSpace: "nowrap" }}>Force Break</span>
              <kbd style={{ fontFamily: "var(--font-mono)", fontSize: "0.56rem", color: "var(--destructive)", background: "color-mix(in srgb, var(--destructive) 10%, transparent)", border: "1px solid color-mix(in srgb, var(--destructive) 25%, transparent)", borderRadius: 4, padding: "1px 4px" }}>B</kbd>
            </div>
          </button>

          {/* Mini HUD Toggle Button */}
          <button
            onClick={() => setMiniHudOpen(prev => !prev)}
            title={collapsed ? "Floating Mini-HUD (H)" : undefined}
            className="flex items-center w-full rounded-xl transition-all duration-150 hover:opacity-90 active:scale-[0.98]"
            style={{
              height: 38,
              padding: "0 10px",
              justifyContent: "flex-start",
              background: miniHudOpen ? "var(--primary-alpha-20)" : "var(--muted)",
              color: miniHudOpen ? "var(--primary)" : "var(--foreground)",
              border: `1px solid ${miniHudOpen ? "var(--primary)" : "var(--border)"}`,
              cursor: "pointer",
            }}
          >
            <div style={{ width: 24, height: 24, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
              <Sparkles size={14} strokeWidth={1.5} style={{ color: "var(--primary)" }} />
            </div>
            <div
              className="flex-1 min-w-0 flex items-center justify-between overflow-hidden"
              style={{
                opacity: collapsed ? 0 : 1,
                maxWidth: collapsed ? 0 : 160,
                marginLeft: collapsed ? 0 : 12,
                pointerEvents: collapsed ? "none" : "auto",
                transition: "opacity 0.18s ease, max-width 0.22s cubic-bezier(0.4,0,0.2,1), margin-left 0.22s ease",
              }}
            >
              <span style={{ fontSize: "0.8rem", fontWeight: 600, whiteSpace: "nowrap" }}>Companion HUD</span>
              <kbd style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.56rem", color: "var(--primary)", background: "var(--primary-alpha-12)", border: "1px solid var(--primary-alpha-20)", borderRadius: 4, padding: "1px 4px" }}>H</kbd>
            </div>
          </button>

          {/* Commands */}
          <button
            onClick={() => setCmdOpen(true)}
            title={collapsed ? "Command Palette (Ctrl+K)" : undefined}
            className="flex items-center w-full rounded-xl transition-all duration-150 hover:opacity-90 active:scale-[0.98]"
            style={{
              height: 38,
              padding: "0 10px",
              justifyContent: "flex-start",
              background: "color-mix(in srgb, var(--primary) 10%, transparent)",
              color: "var(--primary)",
              border: "1px solid color-mix(in srgb, var(--primary) 20%, transparent)",
              cursor: "pointer",
            }}
          >
            <div style={{ width: 24, height: 24, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
              <Search size={14} />
            </div>
            <div
              className="flex-1 min-w-0 flex items-center justify-between overflow-hidden"
              style={{
                opacity: collapsed ? 0 : 1,
                maxWidth: collapsed ? 0 : 160,
                marginLeft: collapsed ? 0 : 12,
                pointerEvents: collapsed ? "none" : "auto",
                transition: "opacity 0.18s ease, max-width 0.22s cubic-bezier(0.4,0,0.2,1), margin-left 0.22s ease",
              }}
            >
              <span style={{ fontSize: "0.8rem", fontWeight: 600, whiteSpace: "nowrap" }}>Commands</span>
              <kbd style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.54rem", background: "color-mix(in srgb, var(--primary) 16%, transparent)", border: "1px solid color-mix(in srgb, var(--primary) 28%, transparent)", borderRadius: 4, padding: "1px 4px" }}>⌘K</kbd>
            </div>
          </button>

          {/* Shortcuts Cheat Sheet */}
          <button
            onClick={() => setGuideOpen(true)}
            title={collapsed ? "Shortcuts (?)" : undefined}
            className="flex items-center w-full rounded-xl transition-all duration-150 hover:opacity-90"
            style={{
              height: 32,
              padding: "0 10px",
              justifyContent: "flex-start",
              background: "transparent",
              color: theme.mutedFg,
              border: "none",
              cursor: "pointer",
            }}
          >
            <div style={{ width: 24, height: 24, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
              <Keyboard size={14} />
            </div>
            <div
              className="flex-1 min-w-0 overflow-hidden"
              style={{
                opacity: collapsed ? 0 : 1,
                maxWidth: collapsed ? 0 : 160,
                marginLeft: collapsed ? 0 : 12,
                pointerEvents: collapsed ? "none" : "auto",
                transition: "opacity 0.18s ease, max-width 0.22s cubic-bezier(0.4,0,0.2,1), margin-left 0.22s ease",
              }}
            >
              <span style={{ fontSize: "0.74rem", whiteSpace: "nowrap" }}>Shortcuts Sheet</span>
            </div>
          </button>
        </div>

        {/* Collapse Toggle & Session Section (Fixed Left Icon Baseline) */}
        <div style={{ borderTop: `1px solid ${theme.border}`, paddingTop: 10, marginTop: 6, display: "flex", flexDirection: "column", gap: 6 }}>
          <button
            onClick={() => setCollapsed(c => !c)}
            className="flex items-center w-full rounded-xl transition-all duration-150 hover:opacity-80 active:scale-[0.98]"
            style={{
              height: 36,
              padding: "0 10px",
              justifyContent: "flex-start",
              background: "transparent",
              border: "none",
              cursor: "pointer",
              color: theme.mutedFg,
            }}
            title={collapsed ? "Expand Navigation ([)" : "Collapse Navigation ([)"}
          >
            <div style={{ width: 24, height: 24, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
              {collapsed ? <PanelLeft size={16} style={{ color: theme.primary }} /> : <PanelLeftClose size={16} style={{ color: theme.mutedFg }} />}
            </div>
            <div
              className="flex-1 min-w-0 flex items-center justify-between overflow-hidden"
              style={{
                opacity: collapsed ? 0 : 1,
                maxWidth: collapsed ? 0 : 160,
                marginLeft: collapsed ? 0 : 12,
                pointerEvents: collapsed ? "none" : "auto",
                transition: "opacity 0.18s ease, max-width 0.22s cubic-bezier(0.4,0,0.2,1), margin-left 0.22s ease",
              }}
            >
              <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.62rem", letterSpacing: "0.04em", whiteSpace: "nowrap" }}>Collapse Sidebar</span>
              <kbd style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.54rem", border: `1px solid ${theme.border}`, borderRadius: 4, padding: "1px 4px" }}>[</kbd>
            </div>
          </button>

          <div
            style={{
              maxHeight: collapsed ? 0 : 44,
              opacity: collapsed ? 0 : 1,
              overflow: "hidden",
              padding: "0 10px",
              transition: "max-height 0.22s cubic-bezier(0.4,0,0.2,1), opacity 0.18s ease",
            }}
          >
            <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.56rem", color: theme.mutedFg, letterSpacing: "0.06em", textTransform: "uppercase" }}>Session #142</div>
            <SessionTimer start={sessionStart} color={theme.primary} />
          </div>
        </div>
      </aside>

      {/* ── Main ─────────────────────────────────────────────────────────── */}
      <main className="flex-1 min-w-0 overflow-hidden relative custom-scrollbar ambient-mesh-bg">
        <ConstellationBg color={theme.primary} density={28} />
        <ErrorBoundary>
          <motion.div key={screen} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }} className="h-full">
            <React.Suspense fallback={<div className="flex items-center justify-center h-full text-muted opacity-70">Loading...</div>}>
              {screen === "dashboard" && (
                <Dashboard />
              )}
              {screen === "analytics" && <Analytics />}
              {screen === "zen"       && <ZenSpace eyeCare={eyeCare} onSetEyeCare={setEyeCare} />}
              {screen === "achievements" && <Achievements />}
              {screen === "preferences" && (
                <Preferences
                  activeTheme={activeTheme}
                  eyeCare={eyeCare} onSetEyeCare={setEyeCare}
                  autoSwap={autoSwap} onSetAutoSwap={setAutoSwap}
                  onSetTheme={handleSetTheme}
                />
              )}
            </React.Suspense>
          </motion.div>
        </ErrorBoundary>
      </main>

      {showBreak && (
        <BreakOverlay
          onDismiss={handleBreakDismiss}
          isRestMode={mode === "rest"}
        />
      )}

      {/* ── Command Palette & Shortcut Guide Modals ───────────────────────── */}
      <CommandPalette
        isOpen={cmdOpen}
        onClose={() => setCmdOpen(false)}
        onNavigate={(sc) => setScreen(sc)}
        onToggleEyeCare={() => setEyeCare(prev => !prev)}
        eyeCareEnabled={eyeCare}
        onTriggerBreak={triggerBreak}
        onSetTheme={handleSetTheme}
        activeTheme={activeTheme}
      />

      <ShortcutGuide
        isOpen={guideOpen}
        onClose={() => setGuideOpen(false)}
      />

      {/* Floating Mini HUD */}
      <CompanionMiniHud
        isOpen={miniHudOpen}
        onToggle={() => setMiniHudOpen(false)}
        onExpand={() => setMiniHudOpen(false)}
      />
    </div>
  );
}
