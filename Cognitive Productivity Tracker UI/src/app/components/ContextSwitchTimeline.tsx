/**
 * Attention Switch Timeline displaying task context switches and thrashing clusters.
 *
 * Author: ChaChan26 <minhharry2006@gmail.com>
 * Copyright (c) 2026 ChaChan26. All rights reserved.
 */

import React, { useState, useEffect } from "react";
import { Zap, AlertTriangle, ArrowRight, RefreshCw, Activity, AlertCircle } from "lucide-react";
import { getAuthHeaders } from "../hooks/useStaminaEngine";

export interface ContextSwitchTrace {
  id: number;
  timestamp: string;
  from_process: string;
  to_process: string;
}

interface ContextSwitchTimelineProps {
  theme: {
    cardBg: string;
    border: string;
    fg: string;
    primary: string;
    sub: string;
  };
}

export function ContextSwitchTimeline({ theme }: ContextSwitchTimelineProps) {
  const [switches, setSwitches] = useState<ContextSwitchTrace[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [showAll, setShowAll] = useState<boolean>(false);

  const fetchSwitches = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/context-switches?limit=200", { headers: getAuthHeaders() });
      if (res.ok) {
        const data = await res.json();
        setSwitches(data.switches || []);
      } else {
        setError(`Failed to fetch traces (HTTP ${res.status})`);
      }
    } catch (e) {
      console.error("Failed to fetch context switches", e);
      setError("Network error fetching attention switches");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSwitches();
  }, []);

  // Compute thrashing clusters (3+ switches within 2 minutes)
  const thrashingEpisodes: { startIdx: number; endIdx: number; count: number; timeSpan: string }[] = [];
  for (let i = 0; i < switches.length; i++) {
    const tStart = new Date(switches[i].timestamp).getTime();
    let clusterCount = 1;
    let j = i + 1;
    while (j < switches.length) {
      const tNext = new Date(switches[j].timestamp).getTime();
      if ((tNext - tStart) <= 120000) { // 2 mins
        clusterCount++;
        j++;
      } else {
        break;
      }
    }
    if (clusterCount >= 3) {
      thrashingEpisodes.push({
        startIdx: i,
        endIdx: j - 1,
        count: clusterCount,
        timeSpan: `${new Date(switches[i].timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} - ${new Date(switches[j - 1].timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`
      });
      i = j - 1; // Skip evaluated cluster
    }
  }

  const displayed = showAll ? switches : switches.slice(0, 8);

  return (
    <div
      style={{
        background: theme.cardBg,
        border: `1px solid ${theme.border}`,
        borderRadius: "var(--radii-xl, 1.25rem)",
        padding: 20,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Zap size={18} style={{ color: "var(--secondary)" }} />
          <h3 style={{ fontSize: "1rem", fontWeight: 700, color: theme.fg, margin: 0, fontFamily: "var(--font-sans)" }}>
            Attention Switch Timeline
          </h3>
        </div>
        <button
          onClick={fetchSwitches}
          style={{
            background: "transparent",
            border: "none",
            color: theme.sub,
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: 4,
            fontSize: "0.75rem",
          }}
        >
          <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>

      {/* Thrashing Highlights Banner */}
      {thrashingEpisodes.length > 0 && (
        <div
          style={{
            background: "color-mix(in srgb, var(--destructive) 10%, transparent)",
            border: "1px solid color-mix(in srgb, var(--destructive) 30%, transparent)",
            borderRadius: "var(--radii-md, 0.75rem)",
            padding: "10px 14px",
            marginBottom: 16,
            display: "flex",
            alignItems: "center",
            gap: 10,
          }}
        >
          <AlertTriangle size={16} style={{ color: "var(--destructive)", flexShrink: 0 }} />
          <div style={{ flex: 1, fontSize: "0.8rem", color: theme.fg, fontFamily: "var(--font-sans)" }}>
            <strong>{thrashingEpisodes.length} Thrashing Clusters Detected:</strong> Rapid context switching detected. Consider taking a breather or locking single-task focus mode.
          </div>
        </div>
      )}

      {/* Error state */}
      {error && (
        <div style={{ display: "flex", alignItems: "center", gap: 8, padding: 12, borderRadius: "var(--radii-md)", background: "color-mix(in srgb, var(--destructive) 10%, transparent)", color: "var(--destructive)", fontSize: "0.8rem", marginBottom: 12 }}>
          <AlertCircle size={14} />
          <span>{error}</span>
        </div>
      )}

      {/* Timeline List */}
      {loading ? (
        <div style={{ padding: 20, textAlign: "center", color: theme.sub, fontSize: "0.85rem", fontFamily: "var(--font-sans)" }}>
          Loading context switch traces...
        </div>
      ) : switches.length === 0 ? (
        <div style={{ padding: 20, textAlign: "center", color: theme.sub, fontSize: "0.85rem", fontFamily: "var(--font-sans)" }}>
          No rapid context switches recorded today. Deep focus intact!
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {displayed.map((item) => {
            const timeStr = new Date(item.timestamp).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
              second: "2-digit",
            });

            return (
              <div
                key={item.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "8px 12px",
                  borderRadius: "var(--radii-md, 0.75rem)",
                  background: "var(--muted, rgba(255,255,255,0.03))",
                  border: `1px solid ${theme.border}`,
                  fontSize: "0.8rem",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 10, flex: 1, minWidth: 0 }}>
                  <span style={{ fontFamily: "var(--font-mono, 'DM Mono', monospace)", fontSize: "0.7rem", color: theme.sub }}>
                    {timeStr}
                  </span>
                  <div style={{ display: "flex", alignItems: "center", gap: 6, minWidth: 0, flex: 1 }}>
                    <span
                      style={{
                        fontWeight: 600,
                        color: theme.fg,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                        maxWidth: "40%",
                      }}
                      title={item.from_process}
                    >
                      {item.from_process || "Unknown"}
                    </span>
                    <ArrowRight size={12} style={{ color: theme.sub, flexShrink: 0 }} />
                    <span
                      style={{
                        fontWeight: 600,
                        color: "var(--primary)",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                        maxWidth: "40%",
                      }}
                      title={item.to_process}
                    >
                      {item.to_process}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}

          {switches.length > 8 && (
            <button
              onClick={() => setShowAll(!showAll)}
              style={{
                background: "transparent",
                border: "none",
                color: "var(--primary)",
                cursor: "pointer",
                padding: "8px 0",
                fontSize: "0.78rem",
                fontWeight: 600,
                textAlign: "center",
                marginTop: 4,
              }}
            >
              {showAll ? "Show Less" : `View All ${switches.length} Switches`}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
