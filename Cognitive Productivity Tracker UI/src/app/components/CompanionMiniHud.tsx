/**
 * Floating companion mini-HUD widget showing active stamina, status, and alerts.
 *
 * Author: ChaChan26 <minhharry2006@gmail.com>
 * Copyright (c) 2026 ChaChan26. All rights reserved.
 */

import React, { useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  Brain, Zap, Battery, Coffee, Clock, AlertTriangle,
  Bell, ChevronUp, ChevronDown, Maximize2, Minimize2, X, Check
} from "lucide-react";
import { useStaminaStore } from "../hooks/useStaminaEngine";
import { toast } from "sonner";

interface CompanionMiniHudProps {
  onExpand?: () => void;
  isOpen: boolean;
  onToggle: () => void;
}

export function CompanionMiniHud({ isOpen, onToggle, onExpand }: CompanionMiniHudProps) {
  const {
    battery,
    mode,
    activeApp,
    classifiedApp,
    timerSeconds,
    activeNudge,
    handleNudgeAction,
    dismissNudge,
    setMode,
    companionMessage,
  } = useStaminaStore();

  const [minimized, setMinimized] = useState(false);

  const fmt = (s: number) =>
    `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;

  const modeColor =
    mode === "work" ? "var(--primary, #8E97FD)" : "var(--secondary, #FFC97E)";
  const batteryColor =
    battery > 55
      ? "var(--primary, #8E97FD)"
      : battery > 25
      ? "var(--secondary, #FFC97E)"
      : "var(--accent-1, #FF84A2)";

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          key="companion-mini-hud"
        initial={{ opacity: 0, y: 20, scale: 0.95 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 20, scale: 0.95 }}
        transition={{ duration: 0.25, ease: "easeOut" }}
        style={{
          position: "fixed",
          bottom: 24,
          right: 24,
          zIndex: 9999,
          width: minimized ? 220 : 340,
          borderRadius: 20,
          background: "var(--card)",
          border: `1.5px solid ${activeNudge ? (activeNudge.type === "critical" ? "var(--accent-1)" : "var(--secondary)") : "var(--border)"}`,
          boxShadow: `0 12px 40px rgba(0, 0, 0, 0.28), 0 0 20px ${activeNudge ? "rgba(255, 132, 162, 0.2)" : "rgba(142, 151, 253, 0.12)"}`,
          backdropFilter: "blur(16px)",
          padding: minimized ? "10px 14px" : "16px 18px",
          color: "var(--foreground)",
          fontFamily: "'Nunito', sans-serif",
          boxSizing: "border-box",
          transition: "width 0.25s ease, border-color 0.3s ease",
        }}
      >
        {/* Header Bar */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: minimized ? 0 : 12,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                background: batteryColor,
                boxShadow: `0 0 8px ${batteryColor}`,
                animation: activeNudge ? "pulse 1.5s infinite" : "none",
              }}
            />
            <span
              style={{
                fontFamily: "'DM Mono', monospace",
                fontSize: "0.68rem",
                fontWeight: 700,
                letterSpacing: "0.08em",
                textTransform: "uppercase",
                color: "var(--foreground)",
              }}
            >
              MIND-HUD · {Math.round(battery)}%
            </span>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <button
              onClick={() => setMinimized(!minimized)}
              style={{
                background: "transparent",
                border: "none",
                color: "var(--muted-foreground)",
                cursor: "pointer",
                padding: 3,
                display: "flex",
                borderRadius: 4,
              }}
              title={minimized ? "Expand" : "Collapse"}
            >
              {minimized ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
            </button>
            {onExpand && (
              <button
                onClick={onExpand}
                style={{
                  background: "transparent",
                  border: "none",
                  color: "var(--muted-foreground)",
                  cursor: "pointer",
                  padding: 3,
                  display: "flex",
                  borderRadius: 4,
                }}
                title="Full Dashboard"
              >
                <Maximize2 size={12} />
              </button>
            )}
            <button
              onClick={onToggle}
              style={{
                background: "transparent",
                border: "none",
                color: "var(--muted-foreground)",
                cursor: "pointer",
                padding: 3,
                display: "flex",
                borderRadius: 4,
              }}
              title="Close HUD"
            >
              <X size={13} />
            </button>
          </div>
        </div>

        {/* Compact View */}
        {minimized ? (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 4 }}>
            <span
              style={{
                fontFamily: "'DM Mono', monospace",
                fontSize: "0.75rem",
                color: modeColor,
                fontWeight: 700,
              }}
            >
              {fmt(timerSeconds)}
            </span>
            <span
              style={{
                fontFamily: "'Nunito', sans-serif",
                fontSize: "0.68rem",
                color: "var(--muted-foreground)",
                maxWidth: 120,
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
            >
              {activeApp}
            </span>
          </div>
        ) : (
          /* Expanded HUD View */
          <div>
            {/* Battery & Timer Hero */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                background: "var(--muted)",
                padding: "10px 14px",
                borderRadius: 14,
                border: "1px solid var(--border)",
                marginBottom: 10,
              }}
            >
              <div>
                <div
                  style={{
                    fontFamily: "'DM Mono', monospace",
                    fontSize: "1.4rem",
                    fontWeight: 700,
                    color: "var(--foreground)",
                    lineHeight: 1,
                  }}
                >
                  {fmt(timerSeconds)}
                </div>
                <div
                  style={{
                    fontFamily: "'Nunito', sans-serif",
                    fontSize: "0.65rem",
                    color: modeColor,
                    fontWeight: 700,
                    textTransform: "uppercase",
                    letterSpacing: "0.08em",
                    marginTop: 3,
                  }}
                >
                  {mode === "work" ? "Deep Work Block" : "Recharge Block"}
                </div>
              </div>

              {/* Quick Mode Toggle Buttons */}
              <div style={{ display: "flex", gap: 6 }}>
                <button
                  onClick={() => setMode(mode === "work" ? "recharge" : "work")}
                  style={{
                    padding: "6px 12px",
                    borderRadius: 10,
                    border: "none",
                    background: mode === "work" ? "var(--primary)" : "var(--card)",
                    color: mode === "work" ? "#FFF" : "var(--foreground)",
                    fontFamily: "'Nunito', sans-serif",
                    fontSize: "0.72rem",
                    fontWeight: 700,
                    cursor: "pointer",
                  }}
                >
                  {mode === "work" ? "Switch Recharge" : "Switch Focus"}
                </button>
              </div>
            </div>

            {/* Current Active Window */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                padding: "6px 10px",
                borderRadius: 10,
                background: "var(--card)",
                border: "1px solid var(--border)",
                fontSize: "0.72rem",
                color: "var(--muted-foreground)",
                marginBottom: activeNudge ? 10 : 0,
              }}
            >
              <span style={{ fontSize: "0.8rem" }}>
                {classifiedApp === "work" ? "💻" : classifiedApp === "recharge" ? "🎮" : "☕"}
              </span>
              <span
                style={{
                  fontFamily: "'DM Mono', monospace",
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  flex: 1,
                }}
                title={activeApp}
              >
                {activeApp || "Detecting..."}
              </span>
            </div>

            {/* Live Actionable Nudge Card */}
            {activeNudge && (
              <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                style={{
                  marginTop: 10,
                  padding: "10px 12px",
                  borderRadius: 12,
                  background:
                    activeNudge.type === "critical"
                      ? "rgba(255, 132, 162, 0.15)"
                      : "rgba(142, 151, 253, 0.15)",
                  border: `1px solid ${activeNudge.type === "critical" ? "var(--accent-1)" : "var(--primary)"}`,
                }}
              >
                <div
                  style={{
                    fontFamily: "'Nunito', sans-serif",
                    fontSize: "0.78rem",
                    fontWeight: 700,
                    color: "var(--foreground)",
                    marginBottom: 2,
                  }}
                >
                  {activeNudge.title}
                </div>
                <div
                  style={{
                    fontFamily: "'Nunito', sans-serif",
                    fontSize: "0.7rem",
                    color: "var(--muted-foreground)",
                    marginBottom: 8,
                    lineHeight: 1.35,
                  }}
                >
                  {activeNudge.message}
                </div>

                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  {activeNudge.actions.map((act) => (
                    <button
                      key={act.action}
                      onClick={async () => {
                        toast.info(`Executing: ${act.label}`);
                        await handleNudgeAction(act.action, activeNudge.id);
                      }}
                      style={{
                        padding: "4px 10px",
                        borderRadius: 8,
                        border: "none",
                        background:
                          act.variant === "primary" || act.action === "take_break"
                            ? "var(--primary)"
                            : "var(--card)",
                        color:
                          act.variant === "primary" || act.action === "take_break"
                            ? "#FFFFFF"
                            : "var(--foreground)",
                        fontFamily: "'Nunito', sans-serif",
                        fontSize: "0.68rem",
                        fontWeight: 700,
                        cursor: "pointer",
                      }}
                    >
                      {act.label}
                    </button>
                  ))}
                  <button
                    onClick={() => dismissNudge()}
                    style={{
                      padding: "4px 8px",
                      borderRadius: 8,
                      border: "1px solid var(--border)",
                      background: "transparent",
                      color: "var(--muted-foreground)",
                      fontFamily: "'Nunito', sans-serif",
                      fontSize: "0.68rem",
                      cursor: "pointer",
                    }}
                  >
                    Dismiss
                  </button>
                </div>
              </motion.div>
            )}
          </div>
        )}
      </motion.div>
      )}
    </AnimatePresence>
  );
}
