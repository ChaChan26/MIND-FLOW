/**
 * Hook managing system achievement milestones, badges, and streak statistics.
 *
 * Author: ChaChan26 <minhharry2006@gmail.com>
 * Copyright (c) 2026 ChaChan26. All rights reserved.
 */

import { useState, useEffect, useCallback } from 'react';
import { getAuthHeaders } from './useStaminaEngine';

export interface Achievement {
  id: string;
  name: string;
  description: string;
  icon: string;
  color: string;
  awarded_at: string | null;
}

interface BackendAchievementRecord {
  id?: number | string;
  name: string;
  awarded_at: string;
}

const ACHIEVEMENT_REGISTRY: Omit<Achievement, 'awarded_at'>[] = [
  { id: 'first_step', name: 'First Step', description: 'Log your first deep work focus session.', icon: 'Footprints', color: 'var(--primary)' },
  { id: 'shield_guardian', name: 'Shield Guardian', description: 'Maintain a 7-day focus tracking streak.', icon: 'Shield', color: 'var(--accent-2)' },
  { id: 'hydration_hero', name: 'Hydration Hero', description: 'Meet your daily hydration target 3 days in a row.', icon: 'Droplets', color: 'var(--accent-4)' },
  { id: 'zero_bypass_week', name: 'Zero Bypass Week', description: 'Complete a 7-day focus streak without skipping any breaks.', icon: 'ShieldCheck', color: 'var(--accent-2)' },
  { id: 'mindfulness_master', name: 'Mindfulness Master', description: 'Log 5 or more state reflections within a single week.', icon: 'Brain', color: 'var(--accent-1)' },
  { id: 'night_owl', name: 'Night Owl', description: 'Complete a deep focus session after 10 PM.', icon: 'Moon', color: 'var(--accent-3)' },
  { id: 'early_bird', name: 'Early Bird', description: 'Complete a deep focus session before 8 AM.', icon: 'Sunrise', color: 'var(--secondary)' },
  { id: 'flow_architect', name: 'Flow Architect', description: 'Enter a flow state 3 separate times.', icon: 'Zap', color: 'var(--primary)' },
  { id: 'century_club', name: 'Century Club', description: 'Log 100 deep work focus sessions.', icon: 'Target', color: 'var(--accent-1)' },
  { id: 'marathon_runner', name: 'Marathon Runner', description: 'Accumulate 2 or more hours of deep focus in a single day.', icon: 'Timer', color: 'var(--accent-4)' },
];

export function useAchievements() {
  const [achievements, setAchievements] = useState<Achievement[]>(ACHIEVEMENT_REGISTRY.map(a => ({ ...a, awarded_at: null })));
  const [unlockedCount, setUnlockedCount] = useState(0);
  const [totalCount] = useState(ACHIEVEMENT_REGISTRY.length);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const [streakDays, setStreakDays] = useState(0);
  const [longestStreakDays, setLongestStreakDays] = useState(0);

  const fetchAchievements = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const qs = window.location.search;
      const [achievementsRes, statusRes] = await Promise.all([
        fetch(`/api/achievements${qs}`, { headers: getAuthHeaders() }),
        fetch(`/api/status${qs}`, { headers: getAuthHeaders() })
      ]);
      
      if (achievementsRes.ok) {
        const data: BackendAchievementRecord[] = await achievementsRes.json();
        if (Array.isArray(data)) {
          const merged = ACHIEVEMENT_REGISTRY.map(reg => {
            const unlocked = data.find((a: BackendAchievementRecord) => a.name === reg.name);
            return {
              ...reg,
              awarded_at: unlocked ? unlocked.awarded_at : null
            };
          });
          
          setAchievements(merged);
          setUnlockedCount(merged.filter(a => a.awarded_at !== null).length);
        }
      } else {
        setError(`Failed to fetch milestones (HTTP ${achievementsRes.status})`);
      }
      
      if (statusRes.ok) {
        const statusData = await statusRes.json();
        setStreakDays(statusData.streak_days || 0);
        setLongestStreakDays(statusData.longest_streak_days || 0);
      }
    } catch (e) {
      console.error("Failed to fetch achievements or status:", e);
      setError("Network error loading achievements");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAchievements();
  }, [fetchAchievements]);

  return { achievements, unlockedCount, totalCount, loading, error, streakDays, longestStreakDays, refetch: fetchAchievements };
}
