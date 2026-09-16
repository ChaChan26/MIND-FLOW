/**
 * Session Timeline component displaying chronologically logged work/recharge blocks, visual 24h Gantt ribbon, and flow states.
 *
 * Author: ChaChan26 <minhharry2006@gmail.com>
 * Copyright (c) 2026 ChaChan26. All rights reserved.
 */

import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  Clock, Sparkles, ChevronLeft, ChevronRight, AlertCircle,
  FileText, CheckCircle2, RefreshCw, Calendar, Flame, Coffee, Laptop, ShieldCheck
} from "lucide-react";
import { getAuthHeaders } from "../hooks/useStaminaEngine";

export interface SessionRecord {
  mode: "work" | "recharge" | "rest" | "neutral";
  start: string;
  end: string;
  duration: number;
  brain_dump?: string | null;
  bypassed: boolean;
  is_flow: boolean;
  flow_duration: number;
}

interface SessionTimelineProps {
  theme: {
    cardBg: string;
    border: string;
    fg: string;
    primary: string;
    sub: string;
  };
}

function fmtLocalDate(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function fmtDur(sec: number): string {
  const rounded = Math.round(sec);
  if (rounded <= 0) return "0s";
  if (rounded < 60) return `${rounded}s`;
  const m = Math.floor(rounded / 60);
  const s = rounded % 60;
  if (m < 60) return s > 0 ? `${m}m ${s}s` : `${m}m`;
  const h = Math.floor(m / 60);
  const remM = m % 60;
  return remM > 0 ? `${h}h ${remM}m` : `${h}h`;
}

function fmtTime(isoStr: string): string {
  if (!isoStr) return "--:--:--";
  try {
    const d = new Date(isoStr);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
  } catch {
    return isoStr.slice(11, 19) || "--:--:--";
  }
}

function getMinutesFromMidnight(isoStr: string): number {
  try {
    const d = new Date(isoStr);
    return d.getHours() * 60 + d.getMinutes() + d.getSeconds() / 60;
  } catch {
    return 0;
  }
}

export function SessionTimeline({ theme }: SessionTimelineProps) {
  const todayStr = fmtLocalDate(new Date());
  const [selectedDate, setSelectedDate] = useState<string>(todayStr);
  const [sessions, setSessions] = useState<SessionRecord[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [hoveredSession, setHoveredSession] = useState<SessionRecord | null>(null);

  const fetchSessions = async (dateStr: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/sessions/history?date=${dateStr}`, { headers: getAuthHeaders() });
      if (res.ok) {
        const data = await res.json();
        setSessions(data.sessions || []);
      } else {
        setError(`Failed to fetch session logs (HTTP ${res.status})`);
      }
    } catch (e) {
      console.error("Failed to fetch session history", e);
      setError("Network error fetching session timeline");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSessions(selectedDate);
  }, [selectedDate]);

  const handlePrevDay = () => {
    const [y, m, day] = selectedDate.split("-").map(Number);
    const d = new Date(y, m - 1, day);
    d.setDate(d.getDate() - 1);
    setSelectedDate(fmtLocalDate(d));
  };

  const handleNextDay = () => {
    const [y, m, day] = selectedDate.split("-").map(Number);
    const d = new Date(y, m - 1, day);
    d.setDate(d.getDate() + 1);
    setSelectedDate(fmtLocalDate(d));
  };

  const handleToday = () => {
    setSelectedDate(todayStr);
  };

  // Totals calculation
  const totalWork = sessions.filter(s => s.mode === "work").reduce((a, b) => a + b.duration, 0);
  const totalRecharge = sessions.filter(s => s.mode === "recharge").reduce((a, b) => a + b.duration, 0);
  const totalRest = sessions.filter(s => s.mode === "rest").reduce((a, b) => a + b.duration, 0);
  const totalRecovery = totalRecharge + totalRest;
  const totalFlow = sessions.reduce((a, b) => a + (b.flow_duration || 0), 0);
  const totalTracked = totalWork + totalRecovery + sessions.filter(s => s.mode === "neutral").reduce((a, b) => a + b.duration, 0);

  const modeMeta: Record<string, { label: string; icon: React.ReactNode; color: string; bg: string; border: string }> = {
    work: {
      label: "Deep Work",
      icon: <Laptop size={14} />,
      color: "var(--primary, #8E97FD)",
      bg: "rgba(142, 151, 253, 0.12)",
      border: "rgba(142, 151, 253, 0.35)",
    },
    recharge: {
      label: "Recharge",
      icon: <Flame size={14} />,
      color: "var(--secondary, #FFC97E)",
      bg: "rgba(255, 201, 126, 0.12)",
      border: "rgba(255, 201, 126, 0.35)",
    },
    rest: {
      label: "Rest Block",
      icon: <ShieldCheck size={14} />,
      color: "var(--accent-4, #82C1B8)",
      bg: "rgba(130, 193, 184, 0.12)",
      border: "rgba(130, 193, 184, 0.35)",
    },
    neutral: {
      label: "Neutral",
      icon: <Coffee size={14} />,
      color: "var(--muted-foreground, #94A3B8)",
      bg: "rgba(148, 163, 184, 0.10)",
      border: "rgba(148, 163, 184, 0.25)",
    },
  };

  const isToday = selectedDate === todayStr;

  return (
    <div
      style={{
        background: theme.cardBg || "var(--card)",
        border: `1px solid ${theme.border || "var(--border)"}`,
        borderRadius: "var(--radii-xl, 1.25rem)",
        padding: "24px 28px",
        display: "flex",
        flexDirection: "column",
        gap: 20,
        boxShadow: "var(--shadow-md)",
      }}
    >
      {/* ══ HEADER & DATE NAVIGATOR ══ */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 14 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div
            style={{
              width: 36,
              height: 36,
              borderRadius: 10,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              background: "rgba(142, 151, 253, 0.15)",
              color: "var(--primary)",
            }}
          >
            <Clock size={20} />
          </div>
          <div>
            <h3 style={{ fontSize: "1.15rem", fontWeight: 800, color: theme.fg || "var(--foreground)", margin: 0, fontFamily: "var(--font-sans)" }}>
              Session History & Day Timeline
            </h3>
            <span style={{ fontSize: "0.75rem", color: theme.sub || "var(--muted-foreground)" }}>
              Chronological log of work sprints, recovery periods, and flow blocks
            </span>
          </div>
        </div>

        {/* Date picker buttons */}
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <button
            onClick={handlePrevDay}
            title="Previous Day"
            style={{
              background: "var(--muted)",
              border: `1px solid ${theme.border || "var(--border)"}`,
              borderRadius: "var(--radii-md)",
              padding: "6px 10px",
              color: theme.fg || "var(--foreground)",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              transition: "all 0.15s",
            }}
          >
            <ChevronLeft size={16} />
          </button>

          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              background: "var(--muted)",
              border: `1px solid ${theme.border || "var(--border)"}`,
              borderRadius: "var(--radii-md)",
              padding: "6px 14px",
            }}
          >
            <Calendar size={13} style={{ color: "var(--primary)" }} />
            <span style={{ fontFamily: "var(--font-mono)", fontWeight: 700, fontSize: "0.85rem", color: theme.fg || "var(--foreground)" }}>
              {selectedDate}
            </span>
            {isToday && (
              <span
                style={{
                  fontSize: "0.6rem",
                  fontWeight: 800,
                  textTransform: "uppercase",
                  padding: "1px 6px",
                  borderRadius: 6,
                  background: "var(--primary)",
                  color: "#FFFFFF",
                  marginLeft: 4,
                }}
              >
                Today
              </span>
            )}
          </div>

          <button
            onClick={handleNextDay}
            title="Next Day"
            disabled={isToday}
            style={{
              background: "var(--muted)",
              border: `1px solid ${theme.border || "var(--border)"}`,
              borderRadius: "var(--radii-md)",
              padding: "6px 10px",
              color: isToday ? "var(--muted-foreground)" : (theme.fg || "var(--foreground)"),
              cursor: isToday ? "not-allowed" : "pointer",
              opacity: isToday ? 0.4 : 1,
              display: "flex",
              alignItems: "center",
              transition: "all 0.15s",
            }}
          >
            <ChevronRight size={16} />
          </button>

          {!isToday && (
            <button
              onClick={handleToday}
              style={{
                background: "var(--primary)",
                color: "#FFFFFF",
                border: "none",
                borderRadius: "var(--radii-md)",
                padding: "6px 12px",
                fontSize: "0.75rem",
                fontWeight: 700,
                cursor: "pointer",
              }}
            >
              Jump to Today
            </button>
          )}

          <button
            onClick={() => fetchSessions(selectedDate)}
            title="Refresh"
            style={{
              background: "transparent",
              border: `1px solid ${theme.border || "var(--border)"}`,
              borderRadius: "var(--radii-md)",
              padding: "6px 10px",
              color: theme.sub || "var(--muted-foreground)",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
            }}
          >
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
          </button>
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div style={{ display: "flex", alignItems: "center", gap: 8, padding: 12, borderRadius: "var(--radii-md)", background: "rgba(255, 132, 162, 0.15)", color: "var(--accent-1, #FF84A2)", fontSize: "0.82rem", border: "1px solid rgba(255, 132, 162, 0.3)" }}>
          <AlertCircle size={15} />
          <span>{error}</span>
        </div>
      )}

      {/* ══ SUMMARY STAT TILES ══ */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 12 }}>
        {/* Total Work */}
        <div style={{ background: "rgba(142, 151, 253, 0.08)", padding: "14px 18px", borderRadius: "var(--radii-lg)", border: "1px solid rgba(142, 151, 253, 0.25)" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
            <span style={{ fontSize: "0.72rem", color: "var(--primary)", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em" }}>Work Time</span>
            <Laptop size={14} style={{ color: "var(--primary)" }} />
          </div>
          <div style={{ fontSize: "1.35rem", fontWeight: 800, color: "var(--primary)", fontFamily: "var(--font-mono)" }}>
            {fmtDur(totalWork)}
          </div>
          <div style={{ fontSize: "0.68rem", color: "var(--muted-foreground)", marginTop: 2 }}>
            {sessions.filter(s => s.mode === "work").length} work sprints
          </div>
        </div>

        {/* Total Recovery */}
        <div style={{ background: "rgba(255, 201, 126, 0.08)", padding: "14px 18px", borderRadius: "var(--radii-lg)", border: "1px solid rgba(255, 201, 126, 0.25)" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
            <span style={{ fontSize: "0.72rem", color: "var(--secondary)", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em" }}>Recovery Time</span>
            <Flame size={14} style={{ color: "var(--secondary)" }} />
          </div>
          <div style={{ fontSize: "1.35rem", fontWeight: 800, color: "var(--secondary)", fontFamily: "var(--font-mono)" }}>
            {fmtDur(totalRecovery)}
          </div>
          <div style={{ fontSize: "0.68rem", color: "var(--muted-foreground)", marginTop: 2 }}>
            {sessions.filter(s => s.mode === "recharge" || s.mode === "rest").length} recharge blocks
          </div>
        </div>

        {/* Flow State Duration */}
        <div style={{ background: "rgba(130, 193, 184, 0.08)", padding: "14px 18px", borderRadius: "var(--radii-lg)", border: "1px solid rgba(130, 193, 184, 0.25)" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
            <span style={{ fontSize: "0.72rem", color: "var(--accent-4)", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em" }}>Flow Duration</span>
            <Sparkles size={14} style={{ color: "var(--accent-4)" }} />
          </div>
          <div style={{ fontSize: "1.35rem", fontWeight: 800, color: "var(--accent-4)", fontFamily: "var(--font-mono)" }}>
            {fmtDur(totalFlow)}
          </div>
          <div style={{ fontSize: "0.68rem", color: "var(--muted-foreground)", marginTop: 2 }}>
            {sessions.filter(s => s.is_flow).length} deep flow states
          </div>
        </div>

        {/* Total Sessions Recorded */}
        <div style={{ background: "var(--muted)", padding: "14px 18px", borderRadius: "var(--radii-lg)", border: `1px solid ${theme.border || "var(--border)"}` }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
            <span style={{ fontSize: "0.72rem", color: theme.sub || "var(--muted-foreground)", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em" }}>Total Blocks</span>
            <Clock size={14} style={{ color: theme.sub || "var(--muted-foreground)" }} />
          </div>
          <div style={{ fontSize: "1.35rem", fontWeight: 800, color: theme.fg || "var(--foreground)", fontFamily: "var(--font-mono)" }}>
            {sessions.length}
          </div>
          <div style={{ fontSize: "0.68rem", color: "var(--muted-foreground)", marginTop: 2 }}>
            {fmtDur(totalTracked)} active logged
          </div>
        </div>
      </div>

      {/* ══ 24-HOUR VISUAL DAY GANTT RIBBON ══ */}
      <div
        style={{
          background: "var(--muted)",
          border: `1px solid ${theme.border || "var(--border)"}`,
          borderRadius: "var(--radii-lg)",
          padding: "16px 20px",
          display: "flex",
          flexDirection: "column",
          gap: 10,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span style={{ fontSize: "0.72rem", fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.08em", color: theme.fg || "var(--foreground)" }}>
            24-Hour Day Distribution Ribbon
          </span>
          <div style={{ display: "flex", alignItems: "center", gap: 12, fontSize: "0.68rem" }}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
              <span style={{ width: 8, height: 8, borderRadius: 2, background: "var(--primary)" }} /> Work
            </span>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
              <span style={{ width: 8, height: 8, borderRadius: 2, background: "var(--secondary)" }} /> Recharge
            </span>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
              <span style={{ width: 8, height: 8, borderRadius: 2, background: "var(--accent-4)" }} /> Rest
            </span>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
              <span style={{ width: 8, height: 8, borderRadius: 2, background: "var(--muted-foreground)" }} /> Neutral
            </span>
          </div>
        </div>

        {/* The 24h Bar */}
        <div
          style={{
            position: "relative",
            height: 28,
            borderRadius: "var(--radii-md)",
            background: "rgba(0, 0, 0, 0.25)",
            border: `1px solid ${theme.border || "var(--border)"}`,
            overflow: "hidden",
          }}
        >
          {sessions.map((s, idx) => {
            const startMin = getMinutesFromMidnight(s.start);
            const durMin = Math.max(0.5, s.duration / 60);
            const leftPct = (startMin / 1440) * 100;
            const widthPct = Math.max(0.6, (durMin / 1440) * 100);
            const meta = modeMeta[s.mode] || modeMeta.neutral;

            return (
              <div
                key={idx}
                onMouseEnter={() => setHoveredSession(s)}
                onMouseLeave={() => setHoveredSession(null)}
                style={{
                  position: "absolute",
                  left: `${leftPct}%`,
                  width: `${widthPct}%`,
                  top: 0,
                  bottom: 0,
                  background: meta.color,
                  opacity: hoveredSession === s ? 1 : 0.85,
                  boxShadow: hoveredSession === s ? `0 0 10px ${meta.color}` : "none",
                  cursor: "pointer",
                  transition: "all 0.15s ease",
                  borderRight: "1px solid rgba(0,0,0,0.3)",
                }}
                title={`${meta.label}: ${fmtTime(s.start)} - ${fmtTime(s.end)} (${fmtDur(s.duration)})`}
              />
            );
          })}
        </div>

        {/* 24-Hour Tick Marks */}
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.62rem", fontFamily: "var(--font-mono)", color: theme.sub || "var(--muted-foreground)", padding: "0 2px" }}>
          <span>00:00</span>
          <span>04:00</span>
          <span>08:00</span>
          <span>12:00</span>
          <span>16:00</span>
          <span>20:00</span>
          <span>24:00</span>
        </div>
      </div>

      {/* ══ SESSION CARDS CHRONOLOGICAL LIST ══ */}
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span style={{ fontSize: "0.78rem", fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.08em", color: theme.fg || "var(--foreground)" }}>
            Recorded Session Log ({sessions.length})
          </span>
          <span style={{ fontSize: "0.72rem", color: theme.sub || "var(--muted-foreground)" }}>
            Reverse chronological
          </span>
        </div>

        {loading ? (
          <div style={{ padding: 36, textAlign: "center", color: theme.sub || "var(--muted-foreground)", fontSize: "0.88rem" }}>
            <RefreshCw size={20} className="animate-spin" style={{ margin: "0 auto 8px" }} />
            Loading sessions for {selectedDate}...
          </div>
        ) : sessions.length === 0 ? (
          <div
            style={{
              padding: 40,
              textAlign: "center",
              color: theme.sub || "var(--muted-foreground)",
              fontSize: "0.88rem",
              background: "var(--muted)",
              borderRadius: "var(--radii-lg)",
              border: `1px dashed ${theme.border || "var(--border)"}`,
            }}
          >
            No session blocks logged for this date.
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <AnimatePresence>
              {[...sessions].reverse().map((s, idx) => {
                const meta = modeMeta[s.mode] || modeMeta.neutral;
                const startStr = fmtTime(s.start);
                const endStr = fmtTime(s.end);
                const isHovered = hoveredSession === s;

                return (
                  <motion.div
                    key={idx}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -6 }}
                    transition={{ duration: 0.2, delay: idx * 0.02 }}
                    style={{
                      background: isHovered ? meta.bg : "var(--muted)",
                      border: `1.5px solid ${isHovered ? meta.border : (s.is_flow ? "rgba(130, 193, 184, 0.45)" : (theme.border || "var(--border)"))}`,
                      borderRadius: "var(--radii-lg)",
                      padding: "14px 18px",
                      display: "flex",
                      flexDirection: "column",
                      gap: 8,
                      transition: "all 0.15s ease",
                      boxShadow: isHovered ? `0 4px 18px ${meta.bg}` : "none",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 10 }}>
                      {/* Left: Mode Badge & Exact Timestamps */}
                      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                        <span
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 5,
                            padding: "4px 10px",
                            borderRadius: "var(--radii-md)",
                            fontSize: "0.75rem",
                            fontWeight: 800,
                            textTransform: "uppercase",
                            letterSpacing: "0.04em",
                            background: meta.bg,
                            color: meta.color,
                            border: `1px solid ${meta.border}`,
                          }}
                        >
                          {meta.icon}
                          {meta.label}
                        </span>

                        <span style={{ fontSize: "0.88rem", fontFamily: "var(--font-mono)", fontWeight: 700, color: theme.fg || "var(--foreground)" }}>
                          {startStr} <span style={{ opacity: 0.4, margin: "0 2px" }}>→</span> {endStr}
                        </span>

                        <span
                          style={{
                            fontSize: "0.82rem",
                            fontFamily: "var(--font-mono)",
                            fontWeight: 600,
                            color: meta.color,
                            padding: "2px 8px",
                            borderRadius: 6,
                            background: "rgba(0,0,0,0.18)",
                          }}
                        >
                          {fmtDur(s.duration)}
                        </span>
                      </div>

                      {/* Right: Flow & Status Badges */}
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        {s.is_flow && (
                          <span
                            style={{
                              display: "inline-flex",
                              alignItems: "center",
                              gap: 4,
                              fontSize: "0.72rem",
                              fontWeight: 800,
                              padding: "3px 10px",
                              borderRadius: "var(--radii-full)",
                              background: "rgba(130, 193, 184, 0.18)",
                              color: "var(--accent-4, #82C1B8)",
                              border: "1px solid rgba(130, 193, 184, 0.4)",
                            }}
                          >
                            <Sparkles size={12} />
                            Flow State ({fmtDur(s.flow_duration)})
                          </span>
                        )}

                        {s.bypassed && (
                          <span
                            style={{
                              color: "var(--accent-1, #FF84A2)",
                              fontSize: "0.72rem",
                              fontWeight: 700,
                              display: "inline-flex",
                              alignItems: "center",
                              gap: 4,
                              background: "rgba(255, 132, 162, 0.12)",
                              padding: "3px 8px",
                              borderRadius: "var(--radii-md)",
                              border: "1px solid rgba(255, 132, 162, 0.3)",
                            }}
                          >
                            <AlertCircle size={12} /> Break Bypassed
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Brain Dump Reflection if present */}
                    {s.brain_dump && (
                      <div
                        style={{
                          fontSize: "0.82rem",
                          color: theme.fg || "var(--foreground)",
                          fontStyle: "italic",
                          background: "rgba(0, 0, 0, 0.2)",
                          padding: "8px 12px",
                          borderRadius: "var(--radii-md)",
                          display: "flex",
                          alignItems: "center",
                          gap: 8,
                          borderLeft: `3px solid ${meta.color}`,
                        }}
                      >
                        <FileText size={14} style={{ color: meta.color, flexShrink: 0 }} />
                        <span>"{s.brain_dump}"</span>
                      </div>
                    )}
                  </motion.div>
                );
              })}
            </AnimatePresence>
          </div>
        )}
      </div>
    </div>
  );
}
