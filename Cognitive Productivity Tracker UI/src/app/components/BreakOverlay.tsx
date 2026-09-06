/**
 * Rest Mode and Attention Capacity Break Overlay enforcing cognitive recovery breaks.
 *
 * Author: ChaChan26 <minhharry2006@gmail.com>
 * Copyright (c) 2026 ChaChan26. All rights reserved.
 */

import { useState, useEffect, useRef } from "react";
import { Eye, Shield } from "lucide-react";
import { useStaminaStore } from "../hooks/useStaminaEngine";

interface Props {
  onDismiss: () => void;
  isRestMode?: boolean;
}

const ROUTINES = [
  {
    stretch: "Roll your shoulders backward in 5 slow circles. Then forward. Feel the tension release.",
    eyeCare: "Look at a point 20 feet away for 20 seconds. Blink slowly 5 times.",
  },
  {
    stretch: "Interlace your fingers, push palms outward and hold for 10 seconds. Breathe slowly.",
    eyeCare: "Close your eyes gently. Cup warm palms over them for 30 seconds.",
  },
  {
    stretch: "Stand if you can. Roll your neck side to side — 3 gentle passes each direction.",
    eyeCare: "Trace a slow figure-8 with your eyes. 3 cycles each direction without moving your head.",
  },
];

function fmt(s: number) {
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

export function BreakOverlay({ onDismiss, isRestMode }: Props) {
  const restSecondsRemaining = useStaminaStore(s => isRestMode ? s.timerSeconds : undefined);
  const restSecondsMax = useStaminaStore(s => isRestMode ? s.adaptedRestSecs : undefined);
  const [holdProgress, setHoldProgress] = useState(0);
  const [holding, setHolding] = useState(false);
  const holdRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const holdingRef = useRef(false);
  const routine = useRef(ROUTINES[Math.floor(Math.random() * ROUTINES.length)]).current;

  const restPct = restSecondsMax && restSecondsRemaining != null
    ? 1 - restSecondsRemaining / restSecondsMax
    : 0;
  const r = 44;
  const circ = 2 * Math.PI * r;

  const startHold = () => {
    setHolding(true);
    holdingRef.current = true;
    if (holdRef.current) clearInterval(holdRef.current);
    let p = 0;
    holdRef.current = setInterval(() => {
      p += 100 / 30;
      setHoldProgress(Math.min(p, 100));
      if (p >= 100) {
        clearInterval(holdRef.current!);
        holdingRef.current = false;
        onDismiss();
      }
    }, 100);
  };

  const stopHold = () => {
    setHolding(false);
    holdingRef.current = false;
    setHoldProgress(0);
    if (holdRef.current) {
      clearInterval(holdRef.current);
      holdRef.current = null;
    }
  };

  useEffect(() => () => { if (holdRef.current) clearInterval(holdRef.current); }, []);

  // Auto-dismiss when rest timer completes
  useEffect(() => {
    if (isRestMode && restSecondsRemaining === 0) {
      onDismiss();
    }
  }, [isRestMode, restSecondsRemaining, onDismiss]);

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col items-center justify-center"
      style={{
        background: "color-mix(in srgb, var(--background) 90%, black 10%)",
        backdropFilter: "blur(32px)",
        color: "var(--foreground)",
      }}
    >
      {/* Ambient blobs */}
      <div style={{ position: "absolute", inset: 0, overflow: "hidden", pointerEvents: "none" }}>
        <div style={{ position: "absolute", width: 600, height: 600, borderRadius: "50%", background: "radial-gradient(circle, color-mix(in srgb, var(--primary) 20%, transparent) 0%, transparent 70%)", top: "-150px", right: "-100px" }} />
        <div style={{ position: "absolute", width: 400, height: 400, borderRadius: "50%", background: "radial-gradient(circle, color-mix(in srgb, var(--accent) 18%, transparent) 0%, transparent 70%)", bottom: "-80px", left: "5%" }} />
      </div>

      <div className="flex flex-col items-center gap-7 max-w-lg w-full px-8 relative z-10">
        {/* Rest mode timer ring */}
        {isRestMode && restSecondsRemaining != null && (
          <div className="flex flex-col items-center gap-3">
            <div style={{ position: "relative", width: 100, height: 100 }}>
              <svg width={100} height={100} style={{ transform: "rotate(-90deg)" }}>
                <circle cx={50} cy={50} r={r} fill="none" stroke="var(--border)" strokeWidth={5} />
                <circle
                  cx={50} cy={50} r={r} fill="none"
                  stroke="var(--primary)" strokeWidth={5} strokeLinecap="round"
                  strokeDasharray={circ}
                  strokeDashoffset={circ * (1 - restPct)}
                  style={{ transition: "stroke-dashoffset 1s linear" }}
                />
              </svg>
              <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
                <Shield size={18} style={{ color: "var(--primary)", marginBottom: 4 }} />
                <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "1rem", color: "var(--foreground)", letterSpacing: "0.04em" }}>
                  {fmt(restSecondsRemaining)}
                </span>
              </div>
            </div>
            <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.62rem", letterSpacing: "0.1em", color: "var(--primary)", textTransform: "uppercase" }}>
              Rest Mode Active
            </div>
          </div>
        )}

        <div style={{ textAlign: "center" }}>
          <h1 style={{ fontFamily: "var(--font-sans)", fontSize: "2.4rem", fontWeight: 700, color: "var(--foreground)", lineHeight: 1.2, marginBottom: 8 }}>
            {isRestMode ? "Rest lock engaged." : "Attention capacity reached."}
          </h1>
          <p style={{ fontFamily: "var(--font-sans)", fontSize: "0.9rem", color: "var(--muted-foreground)", lineHeight: 1.6 }}>
            {isRestMode
              ? "Your cognitive shield is recharging. Step away and let your mind reset."
              : "Your mind has been working hard. This moment belongs to rest."}
          </p>
        </div>

        {/* Routine Card */}
        <div
          className="w-full rounded-2xl flex flex-col gap-5 px-7 py-6"
          style={{
            background: "var(--card)",
            border: "1px solid var(--border)",
            backdropFilter: "blur(20px)",
            boxShadow: "var(--shadow-lg)",
          }}
        >
          <div className="flex items-start gap-4">
            <div style={{ width: 32, height: 32, borderRadius: 10, background: "var(--muted)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
              <span style={{ fontSize: 16 }}>🧘</span>
            </div>
            <div>
              <div style={{ fontFamily: "var(--font-sans)", fontSize: "0.65rem", letterSpacing: "0.1em", color: "var(--primary)", textTransform: "uppercase", marginBottom: 5 }}>
                Body Reset
              </div>
              <p style={{ fontFamily: "var(--font-sans)", fontSize: "0.95rem", color: "var(--foreground)", lineHeight: 1.7, fontStyle: "italic", margin: 0 }}>
                "{routine.stretch}"
              </p>
            </div>
          </div>
          <div style={{ height: 1, background: "var(--border)" }} />
          <div className="flex items-start gap-4">
            <div style={{ width: 32, height: 32, borderRadius: 10, background: "var(--muted)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
              <Eye size={15} style={{ color: "var(--primary)" }} />
            </div>
            <div>
              <div style={{ fontFamily: "var(--font-sans)", fontSize: "0.65rem", letterSpacing: "0.1em", color: "var(--primary)", textTransform: "uppercase", marginBottom: 5 }}>
                Eye Care
              </div>
              <p style={{ fontFamily: "var(--font-sans)", fontSize: "0.95rem", color: "var(--foreground)", lineHeight: 1.7, fontStyle: "italic", margin: 0 }}>
                "{routine.eyeCare}"
              </p>
            </div>
          </div>
        </div>

        {/* Bypass — harder to dismiss in rest mode */}
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6, marginTop: 4 }}>
          <button
            onClick={isRestMode ? undefined : onDismiss}
            onMouseDown={isRestMode ? startHold : undefined}
            onMouseUp={isRestMode ? stopHold : undefined}
            onMouseLeave={isRestMode ? stopHold : undefined}
            onTouchStart={isRestMode ? startHold : undefined}
            onTouchEnd={isRestMode ? stopHold : undefined}
            onKeyDown={isRestMode ? (e) => {
              if (e.key === " " || e.key === "Enter") {
                e.preventDefault();
                if (!holdingRef.current) startHold();
              }
            } : (e) => {
              if (e.key === " " || e.key === "Enter") {
                e.preventDefault();
                onDismiss();
              }
            }}
            onKeyUp={isRestMode ? (e) => {
              if (e.key === " " || e.key === "Enter") {
                stopHold();
              }
            } : undefined}
            onBlur={isRestMode ? stopHold : undefined}
            tabIndex={0}
            className="focus:outline-none focus:ring-1 focus:ring-primary rounded px-2"
            style={{
              position: "relative", overflow: "hidden",
              fontFamily: "'Nunito', sans-serif", fontSize: "0.78rem",
              color: holding ? "var(--foreground)" : "var(--muted-foreground)",
              background: "none", border: "none", cursor: "pointer",
              padding: "4px 0", userSelect: "none",
              transition: "color 0.2s",
            }}
          >
            <span>{isRestMode ? "Override Rest (Hold 3s)" : "Resume Work"}</span>
            <div
              style={{
                position: "absolute", bottom: 0, left: 0,
                height: 1, width: `${holdProgress}%`,
                background: "var(--muted-foreground)", borderRadius: 1,
                transition: holdProgress === 0 ? "none" : undefined,
              }}
            />
          </button>
          {isRestMode && holding && (
            <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.62rem", color: "var(--muted-foreground)", letterSpacing: "0.08em" }}>
              hold…
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
