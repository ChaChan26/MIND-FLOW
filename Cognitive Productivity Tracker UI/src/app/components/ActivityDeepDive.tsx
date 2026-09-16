/**
 * Activity Deep-Dive breakdown component displaying per-application and per-window duration analytics.
 *
 * Author: ChaChan26 <minhharry2006@gmail.com>
 * Copyright (c) 2026 ChaChan26. All rights reserved.
 */

import React, { useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { ChevronDown, ChevronRight, Clock, Layers } from "lucide-react";

export interface AppUsageItem {
  process: string;
  category: "work" | "recharge" | "neutral";
  duration: number;
  titles?: Record<string, number>;
}

interface ActivityDeepDiveProps {
  appUsage: AppUsageItem[];
  theme: {
    cardBg: string;
    border: string;
    fg: string;
    primary: string;
    sub: string;
  };
}

function fmtSec(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  if (m === 0) return `${s}s`;
  if (m < 60) return `${m}m ${s}s`;
  const h = Math.floor(m / 60);
  const remM = m % 60;
  return `${h}h ${remM}m`;
}

export function ActivityDeepDive({ appUsage, theme }: ActivityDeepDiveProps) {
  const [expandedProc, setExpandedProc] = useState<string | null>(null);

  const sortedUsage = [...appUsage].sort((a, b) => b.duration - a.duration);
  const totalDuration = sortedUsage.reduce((acc, curr) => acc + curr.duration, 0) || 1;

  const categoryColors: Record<string, string> = {
    work: "var(--primary)",
    recharge: "var(--secondary)",
    neutral: "var(--muted-foreground)",
  };

  return (
    <div
      style={{
        background: theme.cardBg || "var(--card)",
        border: `1px solid ${theme.border || "var(--border)"}`,
        borderRadius: "var(--radii-lg)",
        padding: "var(--spacing-lg)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Layers size={18} style={{ color: theme.primary || "var(--primary)" }} />
          <h3 style={{ fontSize: "1rem", fontWeight: 700, color: theme.fg || "var(--foreground)", margin: 0 }}>
            Activity Deep-Dive
          </h3>
        </div>
        <span style={{ fontSize: "0.75rem", color: theme.sub || "var(--muted-foreground)" }}>
          Total active: {fmtSec(totalDuration)}
        </span>
      </div>

      {sortedUsage.length === 0 ? (
        <div style={{ padding: 24, textAlign: "center", color: theme.sub || "var(--muted-foreground)", fontSize: "0.85rem" }}>
          No application activity recorded for this period.
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {sortedUsage.map((item) => {
            const pct = Math.round((item.duration / totalDuration) * 100);
            const isExpanded = expandedProc === item.process;
            const hasSubTitles = item.titles && Object.keys(item.titles).length > 0;
            const titleEntries = hasSubTitles ? Object.entries(item.titles!).sort((a, b) => b[1] - a[1]) : [];
            const catColor = categoryColors[item.category] || "var(--muted-foreground)";

            return (
              <div
                key={item.process}
                style={{
                  background: isExpanded ? `color-mix(in srgb, ${theme.fg || "var(--foreground)"} 3%, transparent)` : "transparent",
                  border: `1px solid ${isExpanded ? (theme.border || "var(--border)") : "transparent"}`,
                  borderRadius: "var(--radii-md)",
                  overflow: "hidden",
                  transition: "all 0.2s ease",
                }}
              >
                {/* Main Process Row */}
                <div
                  onClick={() => hasSubTitles && setExpandedProc(isExpanded ? null : item.process)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "10px 14px",
                    cursor: hasSubTitles ? "pointer" : "default",
                    userSelect: "none",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 10, flex: 1, minWidth: 0 }}>
                    {hasSubTitles ? (
                      isExpanded ? (
                        <ChevronDown size={16} style={{ color: theme.sub || "var(--muted-foreground)", flexShrink: 0 }} />
                      ) : (
                        <ChevronRight size={16} style={{ color: theme.sub || "var(--muted-foreground)", flexShrink: 0 }} />
                      )
                    ) : (
                      <div style={{ width: 16 }} />
                    )}
                    <span
                      style={{
                        fontSize: "0.88rem",
                        fontWeight: 600,
                        color: theme.fg || "var(--foreground)",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {item.process}
                    </span>
                    <span
                      style={{
                        fontSize: "0.65rem",
                        fontWeight: 700,
                        padding: "2px 6px",
                        borderRadius: "var(--radii-sm)",
                        textTransform: "uppercase",
                        letterSpacing: "0.05em",
                        background: `color-mix(in srgb, ${catColor} 15%, transparent)`,
                        color: catColor,
                      }}
                    >
                      {item.category}
                    </span>
                  </div>

                  <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <div style={{ width: 80, height: 6, borderRadius: "var(--radii-sm)", background: `color-mix(in srgb, ${theme.fg || "var(--foreground)"} 10%, transparent)`, overflow: "hidden" }}>
                      <div style={{ width: `${pct}%`, height: "100%", background: catColor, borderRadius: "var(--radii-sm)" }} />
                    </div>
                    <span style={{ fontSize: "0.8rem", fontFamily: "var(--font-mono)", fontWeight: 600, color: theme.fg || "var(--foreground)", minWidth: 60, textAlign: "right" }}>
                      {fmtSec(item.duration)}
                    </span>
                  </div>
                </div>

                {/* Expanded Sub-Title Breakdown */}
                <AnimatePresence>
                  {isExpanded && hasSubTitles && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.2 }}
                      style={{ overflow: "hidden" }}
                    >
                      <div style={{ padding: "8px 14px 12px 40px", display: "flex", flexDirection: "column", gap: 6, borderTop: `1px solid color-mix(in srgb, ${theme.border || "var(--border)"} 50%, transparent)` }}>
                        {titleEntries.map(([title, subSec]) => {
                          const subPct = Math.round((subSec / item.duration) * 100);
                          return (
                            <div
                              key={title}
                              style={{
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "space-between",
                                fontSize: "0.78rem",
                                color: theme.sub || "var(--muted-foreground)",
                              }}
                            >
                              <div style={{ display: "flex", alignItems: "center", gap: 6, flex: 1, minWidth: 0, paddingRight: 12 }}>
                                <Clock size={12} style={{ color: theme.sub || "var(--muted-foreground)", flexShrink: 0 }} />
                                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: theme.fg || "var(--foreground)" }}>
                                  {title}
                                </span>
                              </div>
                              <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
                                <span style={{ fontSize: "0.7rem", fontFamily: "var(--font-mono)", color: theme.sub || "var(--muted-foreground)" }}>
                                  {subPct}%
                                </span>
                                <span style={{ fontSize: "0.75rem", fontFamily: "var(--font-mono)", fontWeight: 500, color: theme.fg || "var(--foreground)" }}>
                                  {fmtSec(subSec)}
                                </span>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
