/**
 * Hook managing user cognitive check-in reflections and CBT distortion logs.
 *
 * Author: ChaChan26 <minhharry2006@gmail.com>
 * Copyright (c) 2026 ChaChan26. All rights reserved.
 */

import { useState, useEffect, useCallback } from "react";
import { getAuthHeaders } from "./useStaminaEngine";

export type Mood = "Calm" | "Focused" | "Neutral" | "Anxious" | "Overwhelmed" | "Frustrated" | "Exhausted";

export interface ReflectionEntry {
  id: string;
  date: string;
  time: string;
  energy: number;
  friction: number;
  stress?: number;
  mood: Mood;
  sleepHours: number;
  sleepQuality?: number;
  wins: string;
  roadblocks: string;
  winTags?: string[];
  blockTags?: string[];
}

interface BackendReflectionRecord {
  id: number | string;
  timestamp: string;
  energy_level: number;
  friction_level: number;
  mood?: Mood;
  sleep_hours?: number;
  sleep_quality?: number;
  summary?: string;
}

export function useReflections() {
  const [reflections, setReflections] = useState<ReflectionEntry[]>([]);

  const fetchReflections = useCallback(async () => {
    try {
      const qs = window.location.search;
      const res = await fetch(`/api/reflections${qs}`, { headers: getAuthHeaders() });
      if (!res.ok) return;
      const data: BackendReflectionRecord[] = await res.json();
      if (!Array.isArray(data)) return;
      setReflections(data.map((r: BackendReflectionRecord) => {
        const dt = new Date(r.timestamp);
        const parts = (r.summary || "").split(" | ");
        return {
          id: String(r.id),
          date: !isNaN(dt.getTime())
            ? dt.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })
            : r.timestamp,
          time: !isNaN(dt.getTime())
            ? dt.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
            : r.timestamp,
          energy: r.energy_level,
          friction: r.friction_level,
          mood: r.mood || "Neutral",
          sleepHours: r.sleep_hours || 0,
          sleepQuality: r.sleep_quality || 3,
          wins: parts[0] || "",
          roadblocks: parts[1] || ""
        };
      }));
    } catch (e) {
      console.error(e);
    }
  }, []);

  useEffect(() => {
    fetchReflections();
  }, [fetchReflections]);

  const addReflection = async (entry: Omit<ReflectionEntry, "id" | "date" | "time">) => {
    try {
      const qs = window.location.search;
      await fetch(`/api/reflections${qs}`, {
        method: "POST",
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          energy_level: entry.energy,
          friction_level: entry.friction,
          summary: entry.wins + (entry.roadblocks ? " | " + entry.roadblocks : ""),
          mood: entry.mood,
          sleep_hours: entry.sleepHours,
          sleep_quality: entry.sleepQuality
        })
      });
      fetchReflections();
    } catch (e) {
      console.error(e);
    }
  };

  return { reflections, addReflection };
}
