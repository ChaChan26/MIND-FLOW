/**
 * Focus session timer with stamina integration and completion logging.
 *
 * Author: ChaChan26 <minhharry2006@gmail.com>
 * Copyright (c) 2026 ChaChan26. All rights reserved.
 */

import React, { useState, useEffect, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Play, Pause, RotateCcw, CheckCircle2, ShieldAlert, Sparkles, Target, Zap } from "lucide-react";
import { useStaminaStore, getAuthHeaders } from "../hooks/useStaminaEngine";
import { toast } from "sonner";

interface FocusTimerProps {
  onSessionComplete?: (durationMinutes: number, taskLabel: string) => void;
}

const PRESETS = [
  { label: "15m", value: 15, sub: "Quick Sprint" },
  { label: "25m", value: 25, sub: "Classic Pomodoro" },
  { label: "45m", value: 45, sub: "Deep Focus" },
  { label: "60m", value: 60, sub: "Marathon" },
];

export function FocusTimer({ onSessionComplete }: FocusTimerProps) {
  const battery = useStaminaStore((s) => s.battery);
  const setMode = useStaminaStore((s) => s.setMode);

  const [targetMinutes, setTargetMinutes] = useState<number>(25);
  const [secondsRemaining, setSecondsRemaining] = useState<number>(25 * 60);
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [taskLabel, setTaskLabel] = useState<string>("");
  const [initialBattery, setInitialBattery] = useState<number>(battery);
  const [completedSessionsCount, setCompletedSessionsCount] = useState<number>(0);
  const [isCompletedModalOpen, setIsCompletedModalOpen] = useState<boolean>(false);

  // Sync initial total seconds when target minutes change and timer is stopped
  useEffect(() => {
    if (!isRunning) {
      setSecondsRemaining(targetMinutes * 60);
    }
  }, [targetMinutes, isRunning]);

  // Main countdown timer interval
  useEffect(() => {
    let intervalId: ReturnType<typeof setInterval> | null = null;
    if (isRunning && secondsRemaining > 0) {
      intervalId = setInterval(() => {
        setSecondsRemaining((prev) => prev - 1);
      }, 1000);
    } else if (secondsRemaining === 0 && isRunning) {
      handleCompleteSession();
    }
    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [isRunning, secondsRemaining]);

  const handleStart = () => {
    if (secondsRemaining <= 0) {
      setSecondsRemaining(targetMinutes * 60);
    }
    setInitialBattery(battery);
    setIsRunning(true);
    setMode("work");
    toast.success(`Focus session started (${targetMinutes}m)`, {
      description: taskLabel ? `Task: ${taskLabel}` : "Deep work mode active",
    });
  };

  const handlePause = () => {
    setIsRunning(false);
    toast("Focus session paused");
  };

  const handleReset = () => {
    setIsRunning(false);
    setSecondsRemaining(targetMinutes * 60);
  };

  const handleSelectPreset = (mins: number) => {
    if (isRunning) {
      if (!window.confirm("Timer is currently running. Change duration and reset timer?")) {
        return;
      }
    }
    setIsRunning(false);
    setTargetMinutes(mins);
    setSecondsRemaining(mins * 60);
  };

  const logSessionToBackend = async (durationMins: number, label: string, isCompleted: boolean, startStam: number, endStam: number) => {
    try {
      await fetch("/api/focus/log", {
        method: "POST",
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          duration_minutes: durationMins,
          task_label: label,
          completed: isCompleted ? 1 : 0,
          stamina_start: startStam,
          stamina_end: endStam,
        }),
      });
    } catch (e) {
      console.warn("Failed to log focus session to backend:", e);
    }
  };

  const handleCompleteSession = useCallback(() => {
    setIsRunning(false);
    setCompletedSessionsCount((c) => c + 1);
    setIsCompletedModalOpen(true);
    logSessionToBackend(targetMinutes, taskLabel, true, initialBattery, battery);
    if (onSessionComplete) {
      onSessionComplete(targetMinutes, taskLabel);
    }
    toast.success("✨ Focus session completed!", {
      description: "Great work! Time for a restorative break.",
    });
  }, [targetMinutes, taskLabel, initialBattery, battery, onSessionComplete]);

  // Calculations for visual timer ring
  const totalSeconds = targetMinutes * 60;
  const progressFraction = Math.max(0, Math.min(1, 1 - secondsRemaining / totalSeconds));
  const strokeDashoffset = 565.48 * (1 - progressFraction); // Radius = 90 (2 * pi * 90 = 565.48)

  const minutesDisplay = String(Math.floor(secondsRemaining / 60)).padStart(2, "0");
  const secondsDisplay = String(secondsRemaining % 60).padStart(2, "0");

  const isLowBattery = battery < 30;

  return (
    <div
      style={{
        background: "var(--surface)",
        borderRadius: "var(--radii-xl, 1.5rem)",
        padding: "1.5rem",
        boxShadow: "var(--shadows-md, 0 4px 12px rgba(0,0,0,0.05))",
        border: "1px solid var(--border)",
        color: "var(--on-surface)",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* Background Subtle Accent Glow */}
      <div
        style={{
          position: "absolute",
          top: "-50px",
          right: "-50px",
          width: "160px",
          height: "160px",
          borderRadius: "50%",
          background: isRunning
            ? "radial-gradient(circle, color-mix(in srgb, var(--primary) 20%, transparent) 0%, transparent 70%)"
            : "radial-gradient(circle, color-mix(in srgb, var(--secondary) 15%, transparent) 0%, transparent 70%)",
          pointerEvents: "none",
        }}
      />

      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1.25rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <div
            style={{
              width: "36px",
              height: "36px",
              borderRadius: "50%",
              background: "color-mix(in srgb, var(--primary) 15%, transparent)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "var(--primary)",
            }}
          >
            <Zap size={20} />
          </div>
          <div>
            <h3 style={{ margin: 0, fontSize: "1.125rem", fontWeight: 700, fontFamily: "var(--typography-family-sans)" }}>
              Smart Focus Timer
            </h3>
            <span style={{ fontSize: "0.75rem", color: "var(--on-surface-variant)" }}>
              Pomodoro with stamina guard
            </span>
          </div>
        </div>

        {completedSessionsCount > 0 && (
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "0.35rem",
              padding: "4px 10px",
              borderRadius: "var(--radii-full, 9999px)",
              background: "color-mix(in srgb, var(--accent-4, #82C1B8) 18%, transparent)",
              color: "var(--accent-4, #82C1B8)",
              fontSize: "0.75rem",
              fontWeight: 600,
            }}
          >
            <Sparkles size={12} /> {completedSessionsCount} Done
          </span>
        )}
      </div>

      {/* Task Input */}
      <div style={{ marginBottom: "1.25rem" }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
            background: "var(--background)",
            borderRadius: "var(--radii-md, 0.75rem)",
            padding: "0.5rem 0.85rem",
            border: "1px solid var(--border)",
          }}
        >
          <Target size={16} style={{ color: "var(--on-surface-variant)" }} />
          <input
            type="text"
            placeholder="What focus objective are you working on?"
            value={taskLabel}
            onChange={(e) => setTaskLabel(e.target.value)}
            disabled={isRunning}
            style={{
              background: "transparent",
              border: "none",
              outline: "none",
              color: "var(--on-surface)",
              fontSize: "0.875rem",
              width: "100%",
              fontFamily: "inherit",
            }}
          />
        </div>
      </div>

      {/* Preset Duration Chips */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "0.5rem", marginBottom: "1.5rem" }}>
        {PRESETS.map((p) => {
          const isSelected = targetMinutes === p.value;
          return (
            <button
              key={p.value}
              onClick={() => handleSelectPreset(p.value)}
              style={{
                background: isSelected
                  ? "var(--primary)"
                  : "var(--background)",
                color: isSelected ? "var(--on-primary)" : "var(--on-surface)",
                border: isSelected ? "none" : "1px solid var(--border)",
                borderRadius: "var(--radii-md, 0.75rem)",
                padding: "0.5rem 0.25rem",
                cursor: "pointer",
                textAlign: "center",
                transition: "all 0.2s ease",
              }}
            >
              <div style={{ fontWeight: 700, fontSize: "0.875rem" }}>{p.label}</div>
              <div style={{ fontSize: "0.65rem", opacity: isSelected ? 0.9 : 0.6, marginTop: "2px" }}>{p.sub}</div>
            </button>
          );
        })}
      </div>

      {/* Circular Timer Display */}
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", margin: "1rem 0" }}>
        <div style={{ position: "relative", width: "210px", height: "210px" }}>
          <svg width="210" height="210" viewBox="0 0 210 210" style={{ transform: "rotate(-90deg)" }}>
            {/* Track Circle */}
            <circle
              cx="105"
              cy="105"
              r="90"
              stroke="var(--background)"
              strokeWidth="12"
              fill="transparent"
            />
            {/* Progress Circle */}
            <circle
              cx="105"
              cy="105"
              r="90"
              stroke={isLowBattery ? "var(--accent-1, #FF84A2)" : "var(--primary)"}
              strokeWidth="12"
              strokeDasharray="565.48"
              strokeDashoffset={strokeDashoffset}
              strokeLinecap="round"
              fill="transparent"
              style={{ transition: "stroke-dashoffset 0.5s ease, stroke 0.3s ease" }}
            />
          </svg>

          {/* Center Digital Clock */}
          <div
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: "100%",
              height: "100%",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <span
              style={{
                fontFamily: "'DM Mono', monospace, sans-serif",
                fontSize: "2.75rem",
                fontWeight: 700,
                color: "var(--on-surface)",
                letterSpacing: "-1px",
              }}
            >
              {minutesDisplay}:{secondsDisplay}
            </span>
            <span
              style={{
                fontSize: "0.75rem",
                color: isRunning ? "var(--primary)" : "var(--on-surface-variant)",
                fontWeight: 600,
                marginTop: "0.25rem",
                textTransform: "uppercase",
                letterSpacing: "1px",
              }}
            >
              {isRunning ? "Focus Active" : "Ready"}
            </span>
          </div>
        </div>
      </div>

      {/* Adaptive Stamina Warning Alert */}
      {isLowBattery && isRunning && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          style={{
            background: "color-mix(in srgb, var(--accent-1, #FF84A2) 14%, transparent)",
            border: "1px solid color-mix(in srgb, var(--accent-1, #FF84A2) 30%, transparent)",
            borderRadius: "var(--radii-md, 0.75rem)",
            padding: "0.75rem 1rem",
            marginBottom: "1.25rem",
            display: "flex",
            alignItems: "center",
            gap: "0.75rem",
            color: "var(--accent-1, #FF84A2)",
          }}
        >
          <ShieldAlert size={20} />
          <div style={{ fontSize: "0.8rem", lineHeight: 1.3 }}>
            <strong>Stamina Low ({Math.round(battery)}%)</strong>
            <div>Your cognitive load is high. Consider wrapping up early for a quick micro-break.</div>
          </div>
        </motion.div>
      )}

      {/* Controls */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "1rem" }}>
        <button
          onClick={handleReset}
          title="Reset Timer"
          aria-label="Reset Focus Timer"
          style={{
            width: "44px",
            height: "44px",
            borderRadius: "50%",
            background: "var(--background)",
            border: "1px solid var(--border)",
            color: "var(--on-surface-variant)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
            transition: "transform 0.15s ease",
          }}
        >
          <RotateCcw size={18} />
        </button>

        <button
          onClick={isRunning ? handlePause : handleStart}
          aria-label={isRunning ? "Pause Focus Timer" : "Start Focus Timer"}
          style={{
            padding: "0.75rem 2rem",
            borderRadius: "var(--radii-full, 9999px)",
            background: "var(--primary)",
            color: "var(--on-primary)",
            border: "none",
            fontWeight: 700,
            fontSize: "1rem",
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
            cursor: "pointer",
            boxShadow: "var(--shadows-md, 0 4px 12px rgba(0,0,0,0.15))",
            transition: "transform 0.15s ease, background-color 0.2s ease",
          }}
        >
          {isRunning ? (
            <>
              <Pause size={18} /> Pause Focus
            </>
          ) : (
            <>
              <Play size={18} /> Start Focus
            </>
          )}
        </button>
      </div>

      {/* Completion Modal */}
      <AnimatePresence>
        {isCompletedModalOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            style={{
              position: "fixed",
              top: 0,
              left: 0,
              width: "100vw",
              height: "100vh",
              background: "rgba(0,0,0,0.5)",
              backdropFilter: "var(--effects-glass-blur, blur(8px))",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              zIndex: 99999,
            }}
          >
            <motion.div
              initial={{ scale: 0.8, y: 20 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.8, y: 20 }}
              style={{
                background: "var(--surface)",
                borderRadius: "var(--radii-xl, 1.5rem)",
                padding: "2rem",
                maxWidth: "400px",
                width: "90%",
                textAlign: "center",
                boxShadow: "var(--shadows-lg)",
                border: "1px solid var(--border)",
              }}
            >
              <div
                style={{
                  width: "60px",
                  height: "60px",
                  borderRadius: "50%",
                  background: "color-mix(in srgb, var(--accent-4, #82C1B8) 20%, transparent)",
                  color: "var(--accent-4, #82C1B8)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  margin: "0 auto 1rem auto",
                }}
              >
                <CheckCircle2 size={36} />
              </div>
              <h2 style={{ margin: "0 0 0.5rem 0", fontSize: "1.5rem", fontWeight: 700 }}>Focus Sprint Completed!</h2>
              <p style={{ fontSize: "0.875rem", color: "var(--on-surface-variant)", marginBottom: "1.5rem" }}>
                You completed a {targetMinutes}-minute focus block {taskLabel ? `for "${taskLabel}"` : ""}.
              </p>
              <button
                onClick={() => {
                  setIsCompletedModalOpen(false);
                  setMode("rest");
                }}
                style={{
                  width: "100%",
                  padding: "0.85rem",
                  borderRadius: "var(--radii-full, 9999px)",
                  background: "var(--primary)",
                  color: "var(--on-primary)",
                  border: "none",
                  fontWeight: 700,
                  fontSize: "1rem",
                  cursor: "pointer",
                }}
              >
                Take Restorative Break 🧘
              </button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
