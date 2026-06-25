import { useState, useEffect, useCallback, useRef } from "react";

export type AppMode = "work" | "recharge" | "rest" | "neutral";
export type AppClass = "work" | "recharge" | "neutral";

export const BASE_WORK = 25 * 60;
export const BASE_RECHARGE = 15 * 60;
export const BASE_REST = 5 * 60;

export function modeSeconds(mode: AppMode, fatigue: number, autopilot: boolean): number {
  return BASE_WORK; // Placeholder
}

export function useStaminaEngine() {
  const [battery, setBattery] = useState(100);
  const [mode, setModeState] = useState<AppMode>("work");
  const [timerSeconds, setTimerSeconds] = useState(0);
  const [timerMax, setTimerMax] = useState(1);
  const [activeApp, setActiveApp] = useState("Detecting...");
  const [classifiedApp, setClassifiedApp] = useState<AppClass>("neutral");
  const [autopilot, setAutopilot] = useState(true);
  const [energy, setEnergy] = useState(3);
  const [friction, setFriction] = useState(3);
  const [sleep, setSleep] = useState(8);
  const [hydration, setHydration] = useState(0);
  const [workKw, setWorkKw] = useState("obsidian\ngodot\nmysql\nvscode\nterminal");
  const [rechargeKw, setRechargeKw] = useState("arknights\nyoutube\nreddit\ntwitter\ndiscord");
  const [fatigue, setFatigue] = useState(0);

  const fetchStatus = useCallback(async () => {
    try {
      const qs = window.location.search;
      const res = await fetch(`/api/status${qs}`);
      if (!res.ok) return;
      const data = await res.json();
      
      setBattery(data.battery_capacity ?? 100);
      setModeState((data.current_mode === "neutral" ? "work" : data.current_mode) as AppMode);
      setActiveApp(data.active_window_title || data.active_process_name || "Unknown");
      setTimerSeconds(Math.max(0, data.adaptive_work_limit_seconds - data.elapsed_seconds));
      setTimerMax(data.adaptive_work_limit_seconds || 1500);
      setEnergy(data.current_energy ?? 3);
      setHydration(data.hydration?.cups ?? 0);
      
      // Classification
      const wkws = workKw.split("\n").map(k => k.trim().toLowerCase()).filter(Boolean);
      const rkws = rechargeKw.split("\n").map(k => k.trim().toLowerCase()).filter(Boolean);
      const lowerApp = (data.active_window_title || "").toLowerCase();
      if (wkws.some(k => lowerApp.includes(k))) setClassifiedApp("work");
      else if (rkws.some(k => lowerApp.includes(k))) setClassifiedApp("recharge");
      else setClassifiedApp("neutral");
      
    } catch (e) {
      console.error("API error", e);
    }
  }, [workKw, rechargeKw]);

  useEffect(() => {
    fetchStatus();
    const id = setInterval(fetchStatus, 1000);
    return () => clearInterval(id);
  }, [fetchStatus]);

  const setMode = useCallback(async (m: AppMode) => {
    setModeState(m);
    try {
      const qs = window.location.search;
      await fetch(`/api/set_mode${qs}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: m })
      });
      fetchStatus();
    } catch (e) {}
  }, [fetchStatus]);

  return {
    battery,
    mode,
    timerSeconds,
    timerMax,
    activeApp,
    classifiedApp,
    autopilot,
    energy,
    friction,
    sleep,
    hydration,
    workKw,
    rechargeKw,
    fatigue,
    adaptedWorkSecs: BASE_WORK,
    adaptedRestSecs: BASE_REST,
    // actions
    setMode,
    setAutopilot,
    setEnergy,
    setFriction,
    setSleep,
    setHydration,
    setWorkKw,
    setRechargeKw,
    overrideClassify: (cls: AppClass) => setClassifiedApp(cls),
  };
}
