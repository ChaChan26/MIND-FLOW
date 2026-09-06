/**
 * Morning Briefing component providing readiness score, optimal sprint advice, and circadian energy forecast.
 *
 * Author: ChaChan26 <minhharry2006@gmail.com>
 * Copyright (c) 2026 ChaChan26. All rights reserved.
 */

import React, { useState } from "react";
import { Sparkles, Sun, Battery, ChevronUp, ChevronDown, Play, Moon, Droplets } from "lucide-react";
import { useLocalStorage } from "../hooks/useLocalStorage";

interface MorningBriefingProps {
  recoveryScore: number;
  suggestedWorkMinutes: number;
  circadianForecastMessage?: string;
  streakDays: number;
  hydrationCups: number;
  hydrationTarget: number;
  onStartSprint?: () => void;
}

export function MorningBriefing({
  recoveryScore = 85,
  suggestedWorkMinutes = 45,
  circadianForecastMessage = "Peak energy window anticipated between 9 AM and 11:30 AM.",
  streakDays = 1,
  hydrationCups = 0,
  hydrationTarget = 8,
  onStartSprint,
}: MorningBriefingProps) {
  // Local timezone-safe ISO date string (YYYY-MM-DD)
  const todayStr = new Date().toLocaleDateString("sv-SE");
  const [briefingDate, setBriefingDate] = useLocalStorage("mindflow_briefing_date", "");
  const [collapsed, setCollapsed] = useState(briefingDate === todayStr);

  const handleCollapse = () => {
    setBriefingDate(todayStr);
    setCollapsed(!collapsed);
  };

  const getGreeting = () => {
    const hr = new Date().getHours();
    if (hr < 12) return "Good morning";
    if (hr < 18) return "Good afternoon";
    return "Good evening";
  };

  // Readiness level styling with design tokens
  let readinessColor = "var(--accent-4)"; // green / mint
  let readinessLabel = "High Focus Readiness";
  if (recoveryScore < 50) {
    readinessColor = "var(--destructive)";
    readinessLabel = "Fatigue Shield Advisory";
  } else if (recoveryScore < 75) {
    readinessColor = "var(--secondary)";
    readinessLabel = "Moderate Energy Capacity";
  }

  if (collapsed) {
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "var(--spacing-xs) var(--spacing-md)",
          borderRadius: "var(--radii-md)",
          background: "var(--card)",
          border: "1px solid var(--border)",
          marginBottom: "var(--spacing-md)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "0.82rem", color: "var(--foreground)" }}>
          <Sun size={15} style={{ color: readinessColor }} />
          <strong>{getGreeting()}!</strong>
          <span style={{ color: "var(--muted-foreground)" }}>
            Readiness: {recoveryScore}% · Suggested Sprint: {suggestedWorkMinutes}m
          </span>
        </div>
        <button
          onClick={handleCollapse}
          style={{
            background: "transparent",
            border: "none",
            color: "var(--primary)",
            cursor: "pointer",
            fontSize: "0.75rem",
            fontWeight: 600,
            display: "flex",
            alignItems: "center",
            gap: 4,
          }}
        >
          Expand Briefing <ChevronDown size={14} />
        </button>
      </div>
    );
  }

  return (
    <div
      style={{
        background: "linear-gradient(135deg, color-mix(in srgb, var(--primary) 12%, var(--card)) 0%, var(--card) 100%)",
        border: "1px solid color-mix(in srgb, var(--primary) 25%, var(--border))",
        borderRadius: "var(--radii-lg)",
        padding: "var(--spacing-lg)",
        marginBottom: "var(--spacing-md)",
        boxShadow: "var(--shadow-md, 0 8px 32px rgba(0,0,0,0.06))",
        position: "relative",
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 14 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 2 }}>
            <Sun size={18} style={{ color: readinessColor }} />
            <h3 style={{ fontFamily: "var(--font-sans)", fontSize: "1.1rem", fontWeight: 700, color: "var(--foreground)", margin: 0 }}>
              {getGreeting()}! Daily Cognitive Briefing
            </h3>
          </div>
          <p style={{ fontSize: "0.78rem", color: "var(--muted-foreground)", margin: 0 }}>
            🔥 Day {streakDays} Streak · Morning Readiness & Circadian Energy Forecast
          </p>
        </div>

        <button
          onClick={handleCollapse}
          style={{
            background: "transparent",
            border: "none",
            color: "var(--muted-foreground)",
            cursor: "pointer",
            padding: 4,
          }}
        >
          <ChevronUp size={16} />
        </button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, marginBottom: 16 }}>
        {/* Readiness Gauge */}
        <div style={{ background: "color-mix(in srgb, var(--foreground) 4%, transparent)", borderRadius: "var(--radii-md)", padding: 12, border: "1px solid var(--border)" }}>
          <div style={{ fontSize: "0.68rem", color: "var(--muted-foreground)", textTransform: "uppercase", marginBottom: 4 }}>
            Readiness Score
          </div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: "1.4rem", fontWeight: 700, color: readinessColor }}>
              {recoveryScore}%
            </span>
            <span style={{ fontSize: "0.7rem", color: readinessColor, fontWeight: 600 }}>
              {readinessLabel}
            </span>
          </div>
        </div>

        {/* Suggested Sprint */}
        <div style={{ background: "color-mix(in srgb, var(--foreground) 4%, transparent)", borderRadius: "var(--radii-md)", padding: 12, border: "1px solid var(--border)" }}>
          <div style={{ fontSize: "0.68rem", color: "var(--muted-foreground)", textTransform: "uppercase", marginBottom: 4 }}>
            Optimal Focus Sprint
          </div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: "1.4rem", fontWeight: 700, color: "var(--primary)" }}>
              {suggestedWorkMinutes} min
            </span>
            <span style={{ fontSize: "0.7rem", color: "var(--muted-foreground)" }}>
              Calibrated limit
            </span>
          </div>
        </div>

        {/* Hydration Status */}
        <div style={{ background: "color-mix(in srgb, var(--foreground) 4%, transparent)", borderRadius: "var(--radii-md)", padding: 12, border: "1px solid var(--border)" }}>
          <div style={{ fontSize: "0.68rem", color: "var(--muted-foreground)", textTransform: "uppercase", marginBottom: 4 }}>
            Hydration Starting Point
          </div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: "1.4rem", fontWeight: 700, color: "var(--primary)" }}>
              {hydrationCups}/{hydrationTarget}
            </span>
            <span style={{ fontSize: "0.7rem", color: "var(--muted-foreground)" }}>
              cups
            </span>
          </div>
        </div>
      </div>

      {/* Circadian Forecast Banner */}
      <div
        style={{
          background: "color-mix(in srgb, var(--primary) 8%, transparent)",
          border: "1px solid color-mix(in srgb, var(--primary) 20%, transparent)",
          borderRadius: "var(--radii-md)",
          padding: "10px 14px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "0.8rem", color: "var(--foreground)" }}>
          <Sparkles size={14} style={{ color: "var(--primary)" }} />
          <span>{circadianForecastMessage}</span>
        </div>

        {onStartSprint && (
          <button
            onClick={onStartSprint}
            style={{
              background: "var(--primary)",
              color: "var(--primary-foreground)",
              border: "none",
              borderRadius: "var(--radii-sm)",
              padding: "6px 14px",
              fontSize: "0.75rem",
              fontWeight: 700,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 4,
              flexShrink: 0,
            }}
          >
            <Play size={12} fill="currentColor" /> Start First Sprint
          </button>
        )}
      </div>
    </div>
  );
}
