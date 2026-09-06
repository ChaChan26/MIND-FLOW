/**
 * Core stamina and mode state management store (Zustand) with API synchronization.
 *
 * Author: ChaChan26 <minhharry2006@gmail.com>
 * Copyright (c) 2026 ChaChan26. All rights reserved.
 */

import { create } from "zustand";
import { useEffect } from "react";

export type AppMode = "work" | "recharge" | "neutral" | "rest";
export type AppClass = "work" | "recharge" | "neutral";

export interface AppRule {
  app_name: string;
  category: "work" | "recharge" | "neutral";
}

export interface RunningApp {
  process: string;
  display_name: string;
  last_title?: string;
}

export interface NudgeAction {
  label: string;
  action: string;
  variant?: "primary" | "secondary" | "ghost";
}

export interface ActiveNudge {
  id: string;
  type: "critical" | "warning" | "info";
  title: string;
  message: string;
  actions: NudgeAction[];
}

export interface SystemSettings {
  daily_step_target?: number;
  daily_sleep_target?: number;
  hydration_target?: number;
  work_keywords?: string[] | string;
  recharge_keywords?: string[] | string;
  adaptive_timers_enabled?: boolean;
  work_duration_minutes?: number;
  rest_duration_seconds?: number;
  idle_timeout_seconds?: number;
  enable_audio_chimes?: boolean;
  [key: string]: unknown;
}

export const BASE_WORK = 25 * 60;
export const BASE_RECHARGE = 15 * 60;
export const BASE_REST = 5 * 60;

let sharedAudioCtx: AudioContext | null = null;

export function playHarmonicChime(type: "critical" | "warning" | "info" = "info") {
  try {
    const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    if (!AudioCtx) return;
    if (!sharedAudioCtx || sharedAudioCtx.state === "closed") {
      sharedAudioCtx = new AudioCtx();
    }
    if (sharedAudioCtx.state === "suspended") {
      sharedAudioCtx.resume().catch(() => {});
    }
    const ctx = sharedAudioCtx;
    const now = ctx.currentTime;
    const freqs = type === "critical" ? [440, 330, 220] : (type === "warning" ? [523.25, 659.25] : [523.25, 659.25, 783.99]);
    freqs.forEach((freq, idx) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(freq, now + idx * 0.12);
      gain.gain.setValueAtTime(0.001, now + idx * 0.12);
      gain.gain.exponentialRampToValueAtTime(0.12, now + idx * 0.12 + 0.04);
      gain.gain.exponentialRampToValueAtTime(0.0001, now + idx * 0.12 + 0.55);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(now + idx * 0.12);
      osc.stop(now + idx * 0.12 + 0.6);
    });
  } catch (e) {}
}

export function modeSeconds(mode: AppMode, fatigue: number, autopilot: boolean): number {
  return BASE_WORK; // Placeholder
}

interface StaminaState {
  battery: number;
  mode: AppMode;
  timerSeconds: number;
  timerMax: number;
  activeApp: string;
  activeProcess: string;
  classifiedApp: AppClass;
  energy: number;
  friction: number;
  sleep: number;
  hydration: number;
  fatigue: number;
  todayWork: number;
  todayRecharge: number;
  todayRest: number;
  settings: SystemSettings;
  workKw: string;
  rechargeKw: string;
  appRules: AppRule[];
  runningApps: RunningApp[];
  recentApps: RunningApp[];
  
  autopilot: boolean;
  adaptedWorkSecs: number;
  adaptedRestSecs: number;
  activeNudge: ActiveNudge | null;
  sessionExtensionSeconds: number;
  companionMessage: string;
  focusScore: number;
  streakDays: number;
  
  setMode: (m: AppMode) => Promise<void>;
  setAutopilot: (v: boolean) => Promise<void>;
  handleNudgeAction: (action: string, nudgeId?: string) => Promise<void>;
  dismissNudge: () => Promise<void>;
  extendFocus: (seconds?: number) => Promise<void>;
  takeBreak: () => Promise<void>;
  startFocus: () => Promise<void>;
  resetTimer: () => Promise<void>;
  setEnergy: (v: number) => void;
  setFriction: (v: number) => void;
  setSleep: (v: number) => void;
  setHydration: (v: number) => void;
  setWorkKw: (v: string) => void;
  setRechargeKw: (v: string) => void;
  recategorizeApp: (appName: string, category: "work" | "recharge" | "neutral") => Promise<void>;
  deleteAppRule: (appName: string) => Promise<void>;
  fetchAppRules: () => Promise<void>;
  fetchRunningApps: () => Promise<void>;
  fetchRecentApps: () => Promise<void>;
  overrideClassify: (cls: AppClass) => Promise<void>;
  updateSettings: (newSettings: Partial<SystemSettings>) => Promise<void>;
  fetchSettings: () => Promise<void>;
  fetchStatus: (signal?: AbortSignal) => Promise<void>;
}

export function getAuthHeaders(extraHeaders: Record<string, string> = {}): Record<string, string> {
  const headers: Record<string, string> = { ...extraHeaders };
  const params = new URLSearchParams(window.location.search);
  const token = params.get("token");
  if (token) {
    headers["X-MIND-FLOW-TOKEN"] = token;
  }
  return headers;
}

export const useStaminaStore = create<StaminaState>((set, get) => ({
  battery: 100,
  mode: "work",
  timerSeconds: 0,
  timerMax: 1,
  activeApp: "Detecting...",
  activeProcess: "None",
  classifiedApp: "neutral",
  energy: 3,
  friction: 3,
  sleep: 8,
  hydration: 0,
  fatigue: 0,
  todayWork: 0,
  todayRecharge: 0,
  todayRest: 0,
  settings: {
    daily_step_target: 10000,
    daily_sleep_target: 8.0,
    hydration_target: 8,
    work_keywords: ["obsidian", "godot", "mysql", "vscode", "terminal"],
    recharge_keywords: ["arknights", "youtube", "reddit", "twitter", "discord"],
    adaptive_timers_enabled: true,
    work_duration_minutes: 25,
    rest_duration_seconds: 300,
    idle_timeout_seconds: 180,
  },
  workKw: "obsidian\ngodot\nmysql\nvscode\nterminal",
  rechargeKw: "arknights\nyoutube\nreddit\ntwitter\ndiscord",
  appRules: [],
  runningApps: [],
  recentApps: [],

  autopilot: true,
  adaptedWorkSecs: BASE_WORK,
  adaptedRestSecs: BASE_REST,
  activeNudge: null,
  sessionExtensionSeconds: 0,
  companionMessage: "Your cognitive shield is active. Looking good!",
  focusScore: 85,
  streakDays: 1,

  fetchAppRules: async () => {
    try {
      const qs = window.location.search;
      const res = await fetch(`/api/app_rules${qs}`, { headers: getAuthHeaders() });
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data.rules)) {
          set({ appRules: data.rules });
        }
      }
    } catch (e) {}
  },

  fetchRunningApps: async () => {
    try {
      const qs = window.location.search;
      const res = await fetch(`/api/app_rules/running${qs}`, { headers: getAuthHeaders() });
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data.running_apps)) {
          set({ runningApps: data.running_apps });
        }
      }
    } catch (e) {}
  },

  fetchRecentApps: async () => {
    try {
      const qs = window.location.search;
      const res = await fetch(`/api/app_rules/recent${qs}`, { headers: getAuthHeaders() });
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data.recent_apps)) {
          set({ recentApps: data.recent_apps });
        }
      }
    } catch (e) {}
  },

  recategorizeApp: async (appName: string, category: "work" | "recharge" | "neutral") => {
    try {
      const qs = window.location.search;
      const res = await fetch(`/api/app_rules/recategorize${qs}`, {
        method: "POST",
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ app_name: appName, category })
      });
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data.rules)) {
          set({ appRules: data.rules });
        }
        get().fetchSettings();
        get().fetchAppRules();
        get().fetchStatus();
      }
    } catch (e) {}
  },

  deleteAppRule: async (appName: string) => {
    try {
      const qs = window.location.search;
      const res = await fetch(`/api/app_rules${qs}`, {
        method: "DELETE",
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ app_name: appName })
      });
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data.rules)) {
          set({ appRules: data.rules });
        }
        get().fetchSettings();
        get().fetchAppRules();
        get().fetchStatus();
      }
    } catch (e) {}
  },

  updateSettings: async (newSettings: Partial<SystemSettings>) => {
    try {
      const qs = window.location.search;
      const res = await fetch(`/api/settings${qs}`, {
        method: "POST",
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(newSettings)
      });
      if (res.ok) {
        get().fetchSettings();
        get().fetchStatus();
      }
    } catch (e) {}
  },

  fetchSettings: async () => {
    try {
      const qs = window.location.search;
      const res = await fetch(`/api/settings${qs}`, {
        headers: getAuthHeaders()
      });
      if (res.ok) {
        const s = await res.json();
        set({
          settings: s,
          autopilot: s?.adaptive_timers_enabled ?? true,
          adaptedWorkSecs: (s?.work_duration_minutes ?? 25) * 60,
          adaptedRestSecs: s?.rest_duration_seconds ?? BASE_REST
        });
        if (Array.isArray(s?.work_keywords)) set({ workKw: s.work_keywords.join("\n") });
        else if (typeof s?.work_keywords === "string") set({ workKw: s.work_keywords });
        if (Array.isArray(s?.recharge_keywords)) set({ rechargeKw: s.recharge_keywords.join("\n") });
        else if (typeof s?.recharge_keywords === "string") set({ rechargeKw: s.recharge_keywords });
      }
    } catch (e) {}
  },

  fetchStatus: async (signal?: AbortSignal) => {
    try {
      const qs = window.location.search;
      const res = await fetch(`/api/status${qs}`, { signal, headers: getAuthHeaders() });
      if (!res.ok) return;
      const data = await res.json();
      if (signal?.aborted) return;
      
      const rawCategory = data.active_category || data.category || data.current_mode;
      const classifiedApp: AppClass = (rawCategory === "work" || rawCategory === "recharge") ? rawCategory : "neutral";

      const prevNudge = get().activeNudge;
      const newNudge: ActiveNudge | null = data.active_nudge || null;
      if (newNudge && (!prevNudge || prevNudge.id !== newNudge.id)) {
        if (data.settings?.enable_audio_chimes ?? true) {
          playHarmonicChime(newNudge.type);
        }
      }

      const titleStr = (data.active_window_title || "").toLowerCase();
      const procStr = (data.active_process_name || "").toLowerCase();
      const isIde = ["code.exe", "cursor.exe", "devenv.exe", "pycharm64.exe", "pycharm.exe", "sublime_text.exe", "notepad++.exe", "windsurf.exe", "zed.exe", "clion64.exe", "idea64.exe"].includes(procStr);
      const isDashboardSelf = !isIde && (
        titleStr.includes("mind-flow // cognitive companion") || 
        titleStr.includes("cognitive companion dashboard") || 
        titleStr.includes("mind-flow dashboard") ||
        titleStr === "none" ||
        titleStr === "paused" ||
        titleStr === "detecting..." ||
        (procStr === "python.exe" && !titleStr.includes("python") && !titleStr.includes(".py"))
      );

      const resolvedActiveApp = (isDashboardSelf && data.last_external_window && data.last_external_window !== "None")
        ? data.last_external_window
        : (!isDashboardSelf && data.active_window_title && data.active_window_title !== "None"
            ? data.active_window_title
            : (data.last_external_window && data.last_external_window !== "None"
                ? data.last_external_window
                : (data.active_process_name && data.active_process_name !== "None" && data.active_process_name !== "python.exe" ? data.active_process_name : "Detecting...")));

      const resolvedActiveProcess = (isDashboardSelf && data.last_external_process && data.last_external_process !== "None")
        ? data.last_external_process
        : (!isDashboardSelf && data.active_process_name && data.active_process_name !== "None" && data.active_process_name !== "python.exe"
            ? data.active_process_name
            : (data.last_external_process && data.last_external_process !== "None" ? data.last_external_process : "None"));

      const isRechargeOrRest = data.current_mode === "recharge" || data.current_mode === "rest";
      const totalLimit = isRechargeOrRest
        ? (data.adaptive_rest_limit_seconds || data.rest_limit_seconds || 300)
        : ((data.adaptive_work_limit_seconds || 1500) + (data.session_extension_seconds || 0));

      const remainingSeconds = Math.max(0, totalLimit - (data.elapsed_seconds || 0));

      set({
        todayWork: data.today_work_seconds || 0,
        todayRecharge: data.today_recharge_seconds || 0,
        todayRest: data.today_rest_seconds || 0,
        battery: data.battery_capacity ?? 100,
        fatigue: Math.round(100 - (data.battery_capacity ?? 100)),
        mode: (data.current_mode === "neutral" ? "work" : data.current_mode) as AppMode,
        activeApp: resolvedActiveApp,
        activeProcess: resolvedActiveProcess,
        timerSeconds: remainingSeconds,
        timerMax: totalLimit,
        energy: data.current_energy ?? 3,
        hydration: data.hydration?.cups ?? 0,
        classifiedApp,
        activeNudge: newNudge,
        sessionExtensionSeconds: data.session_extension_seconds ?? 0,
        companionMessage: data.companion_message || "Your cognitive shield is active. Looking good!",
        focusScore: data.focus_score ?? 85,
        streakDays: data.streak_days ?? 1,
      });
    } catch (e) {
      console.error("API error", e);
    }
  },

  handleNudgeAction: async (action: string, nudgeId?: string) => {
    // Optimistic UI clear
    set({ activeNudge: null });
    try {
      const qs = window.location.search;
      const res = await fetch(`/api/nudge/action${qs}`, {
        method: "POST",
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ action, nudge_id: nudgeId })
      });
      if (res.ok) {
        get().fetchStatus();
      }
    } catch (e) {
      console.error("Error executing nudge action", e);
    }
  },

  dismissNudge: async () => {
    get().handleNudgeAction("dismiss");
  },

  extendFocus: async (seconds: number = 300) => {
    await get().handleNudgeAction(seconds === 120 ? "extend_2m" : "extend_5m");
  },

  takeBreak: async () => {
    await get().handleNudgeAction("take_break");
  },

  startFocus: async () => {
    await get().handleNudgeAction("start_focus");
  },

  resetTimer: async () => {
    await get().handleNudgeAction("reset_timer");
  },

  setMode: async (m: AppMode) => {
    set({ mode: m });
    try {
      const qs = window.location.search;
      await fetch(`/api/set_mode${qs}`, {
        method: "POST",
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ mode: m })
      });
      get().fetchStatus();
    } catch (e) {}
  },
  
  setAutopilot: async (v: boolean) => get().updateSettings({ adaptive_timers_enabled: v }),
  setEnergy: (v: number) => set({ energy: v }),
  setFriction: (v: number) => set({ friction: v }),
  setSleep: (v: number) => set({ sleep: v }),
  setHydration: (v: number) => set({ hydration: v }),
  setWorkKw: (v: string) => {
    set({ workKw: v });
    get().updateSettings({ work_keywords: v.split("\n").map(k => k.trim()).filter(Boolean) });
  },
  setRechargeKw: (v: string) => {
    set({ rechargeKw: v });
    get().updateSettings({ recharge_keywords: v.split("\n").map(k => k.trim()).filter(Boolean) });
  },
  overrideClassify: async (cls: AppClass) => {
    set({ classifiedApp: cls });
    const state = get();
    const target = (state.activeProcess && state.activeProcess !== "None" && state.activeProcess !== "Detecting...")
      ? state.activeProcess
      : (state.activeApp && state.activeApp !== "Detecting..." && state.activeApp !== "None" ? state.activeApp : "");
    if (target) {
      await state.recategorizeApp(target, cls);
    }
  },
}));

export function useStaminaEngineInit() {
  const fetchSettings = useStaminaStore(s => s.fetchSettings);
  const fetchAppRules = useStaminaStore(s => s.fetchAppRules);
  const fetchRunningApps = useStaminaStore(s => s.fetchRunningApps);
  const fetchRecentApps = useStaminaStore(s => s.fetchRecentApps);
  const fetchStatus = useStaminaStore(s => s.fetchStatus);

  useEffect(() => {
    fetchSettings();
    fetchAppRules();
    fetchRunningApps();
    fetchRecentApps();
  }, [fetchSettings, fetchAppRules, fetchRunningApps, fetchRecentApps]);

  useEffect(() => {
    let timeoutId: ReturnType<typeof setTimeout>;
    let isCancelled = false;
    const controller = new AbortController();

    const poll = async () => {
      const isHidden = document.hidden;
      if (!isHidden) {
        try {
          await fetchStatus(controller.signal);
        } catch (e) {
          if ((e as Error).name !== 'AbortError') console.error(e);
        }
      }
      if (!isCancelled) {
        timeoutId = setTimeout(poll, isHidden ? 3000 : 1000);
      }
    };

    const handleVisibilityChange = () => {
      if (!document.hidden && !isCancelled) {
        clearTimeout(timeoutId);
        poll();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    poll();

    return () => {
      isCancelled = true;
      controller.abort();
      clearTimeout(timeoutId);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [fetchStatus]);
}

// Granular selector hooks to eliminate 1-second full component tree re-renders
export const useBattery = () => useStaminaStore(s => s.battery);
export const useCurrentMode = () => useStaminaStore(s => s.mode);
export const useTimerSeconds = () => useStaminaStore(s => s.timerSeconds);
export const useTimerMax = () => useStaminaStore(s => s.timerMax);
export const useActiveApp = () => useStaminaStore(s => s.activeApp);
export const useActiveProcess = () => useStaminaStore(s => s.activeProcess);
export const useClassifiedApp = () => useStaminaStore(s => s.classifiedApp);
export const useActiveNudge = () => useStaminaStore(s => s.activeNudge);
export const useCompanionMsg = () => useStaminaStore(s => s.companionMessage);
export const useFatigue = () => useStaminaStore(s => s.fatigue);
export const useSystemSettings = () => useStaminaStore(s => s.settings);


