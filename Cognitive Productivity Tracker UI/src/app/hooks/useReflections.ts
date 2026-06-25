import { useState, useEffect, useCallback } from "react";

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

export function useReflections() {
  const [reflections, setReflections] = useState<ReflectionEntry[]>([]);

  const fetchReflections = useCallback(async () => {
    try {
      const qs = window.location.search;
      const res = await fetch(`/api/reflections${qs}`);
      if (!res.ok) return;
      const data = await res.json();
      setReflections(data.map((r: any) => ({
        id: String(r.id),
        date: r.timestamp,
        time: r.timestamp,
        energy: r.energy_level,
        friction: r.friction_level,
        mood: r.mood || "Neutral",
        sleepHours: r.sleep_hours || 0,
        sleepQuality: r.sleep_quality || 3,
        wins: r.summary || "",
        roadblocks: ""
      })));
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
        headers: { "Content-Type": "application/json" },
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
