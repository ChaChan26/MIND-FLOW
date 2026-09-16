/**
 * Daily Cognitive Digest modal presenting focus hours, AI recommendations, and gratitude journaling.
 *
 * Author: ChaChan26 <minhharry2006@gmail.com>
 * Copyright (c) 2026 ChaChan26. All rights reserved.
 */

import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Sparkles, X, Heart, CheckCircle2, Trophy, Clock, Zap, Loader2 } from "lucide-react";
import { getAuthHeaders } from "../hooks/useStaminaEngine";

interface DigestReport {
  title: string;
  range: string;
  period: string;
  total_focus_hours: number;
  total_recovery_hours: number;
  bypasses_count: number;
  avg_energy: number;
  avg_friction: number;
  accomplishments: string[];
  recommendations: string[];
  unlocked_achievements_count: number;
}

interface DailyDigestProps {
  isOpen: boolean;
  onClose: () => void;
  todayWorkSeconds: number;
  todayRechargeSeconds: number;
  focusScore: number;
  streakDays: number;
}

export function DailyDigest({
  isOpen,
  onClose,
  todayWorkSeconds = 0,
  todayRechargeSeconds = 0,
  focusScore = 85,
  streakDays = 1,
}: DailyDigestProps) {
  const [gratitude1, setGratitude1] = useState("");
  const [gratitude2, setGratitude2] = useState("");
  const [gratitude3, setGratitude3] = useState("");
  const [savedGratitude, setSavedGratitude] = useState(false);
  const [digest, setDigest] = useState<DigestReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setLoading(true);
      setErrorMessage(null);
      // Fetch daily digest report from API
      fetch("/api/analytics/digest?range=daily", { headers: getAuthHeaders() })
        .then(res => {
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          return res.json();
        })
        .then(data => {
          if (data && data.status !== "error") {
            setDigest(data);
          }
        })
        .catch(err => {
          console.error("Failed to fetch digest", err);
          setErrorMessage("Could not load AI recommendations");
        })
        .finally(() => setLoading(false));

      // Fetch today's gratitude
      fetch("/api/gratitude", { headers: getAuthHeaders() })
        .then(res => res.ok ? res.json() : null)
        .then(data => {
          if (data) {
            setGratitude1(data.entry_1 || "");
            setGratitude2(data.entry_2 || "");
            setGratitude3(data.entry_3 || "");
          }
        })
        .catch(err => console.error("Failed to fetch gratitude", err));
    }
  }, [isOpen]);

  const handleSaveGratitude = async () => {
    try {
      const res = await fetch("/api/gratitude", {
        method: "POST",
        headers: { ...getAuthHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({
          entry_1: gratitude1,
          entry_2: gratitude2,
          entry_3: gratitude3,
        }),
      });
      if (res.ok) {
        setSavedGratitude(true);
        setTimeout(() => setSavedGratitude(false), 3000);
      } else {
        setErrorMessage("Failed to save reflections");
      }
    } catch (e) {
      console.error("Failed to save gratitude", e);
      setErrorMessage("Network error saving reflections");
    }
  };

  const workHours = (todayWorkSeconds / 3600).toFixed(1);
  const rechargeHours = (todayRechargeSeconds / 3600).toFixed(1);

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          key="daily-digest-backdrop"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 9999,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: "rgba(0, 0, 0, 0.75)",
            backdropFilter: "blur(12px)",
            WebkitBackdropFilter: "blur(12px)",
            padding: "var(--spacing-lg)",
          }}
          onClick={onClose}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 10 }}
            transition={{ duration: 0.18 }}
            onClick={(e) => e.stopPropagation()}
            style={{
              width: "100%",
              maxWidth: 640,
              background: "var(--card)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radii-lg)",
              padding: "var(--spacing-xl)",
              boxShadow: "var(--shadow-dark-lg, 0 24px 48px rgba(0, 0, 0, 0.3))",
              display: "flex",
              flexDirection: "column",
              gap: "var(--spacing-lg)",
              maxHeight: "90vh",
              overflowY: "auto",
            }}
          >
            {/* Header */}
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                  <Sparkles size={20} style={{ color: "var(--primary)" }} />
                  <h2 style={{ fontFamily: "var(--font-sans)", fontSize: "1.3rem", fontWeight: 700, margin: 0, color: "var(--foreground)" }}>
                    Daily Cognitive Digest
                  </h2>
                </div>
                <p style={{ fontSize: "0.8rem", color: "var(--muted-foreground)", margin: 0 }}>
                  End-of-day summary, accomplishments & gratitude reflection
                </p>
              </div>
              <button
                onClick={onClose}
                style={{
                  background: "transparent",
                  border: "none",
                  color: "var(--muted-foreground)",
                  cursor: "pointer",
                  padding: 4,
                }}
              >
                <X size={18} />
              </button>
            </div>

            {/* Key Stat Cards */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10 }}>
              <div style={{ background: "color-mix(in srgb, var(--foreground) 3%, transparent)", padding: 12, borderRadius: "var(--radii-md)", border: "1px solid var(--border)", textAlign: "center" }}>
                <div style={{ fontSize: "0.65rem", color: "var(--muted-foreground)", textTransform: "uppercase" }}>Focus Hours</div>
                <div style={{ fontSize: "1.2rem", fontWeight: 700, color: "var(--primary)", fontFamily: "var(--font-mono)" }}>{workHours}h</div>
              </div>
              <div style={{ background: "color-mix(in srgb, var(--foreground) 3%, transparent)", padding: 12, borderRadius: "var(--radii-md)", border: "1px solid var(--border)", textAlign: "center" }}>
                <div style={{ fontSize: "0.65rem", color: "var(--muted-foreground)", textTransform: "uppercase" }}>Recovery</div>
                <div style={{ fontSize: "1.2rem", fontWeight: 700, color: "var(--secondary)", fontFamily: "var(--font-mono)" }}>{rechargeHours}h</div>
              </div>
              <div style={{ background: "color-mix(in srgb, var(--foreground) 3%, transparent)", padding: 12, borderRadius: "var(--radii-md)", border: "1px solid var(--border)", textAlign: "center" }}>
                <div style={{ fontSize: "0.65rem", color: "var(--muted-foreground)", textTransform: "uppercase" }}>Focus Score</div>
                <div style={{ fontSize: "1.2rem", fontWeight: 700, color: "var(--accent-4)", fontFamily: "var(--font-mono)" }}>{focusScore}</div>
              </div>
              <div style={{ background: "color-mix(in srgb, var(--foreground) 3%, transparent)", padding: 12, borderRadius: "var(--radii-md)", border: "1px solid var(--border)", textAlign: "center" }}>
                <div style={{ fontSize: "0.65rem", color: "var(--muted-foreground)", textTransform: "uppercase" }}>Streak</div>
                <div style={{ fontSize: "1.2rem", fontWeight: 700, color: "var(--accent-1)", fontFamily: "var(--font-mono)" }}>{streakDays}d</div>
              </div>
            </div>

            {/* Recommendations / Insights */}
            {loading ? (
              <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8, padding: 16, color: "var(--muted-foreground)", fontSize: "0.85rem" }}>
                <Loader2 size={16} className="animate-spin" style={{ color: "var(--primary)" }} />
                <span>Synthesizing daily cognitive insights...</span>
              </div>
            ) : digest?.recommendations && digest.recommendations.length > 0 ? (
              <div style={{ background: "color-mix(in srgb, var(--primary) 8%, transparent)", border: "1px solid color-mix(in srgb, var(--primary) 20%, transparent)", borderRadius: "var(--radii-md)", padding: 14 }}>
                <div style={{ fontSize: "0.72rem", color: "var(--primary)", fontWeight: 700, textTransform: "uppercase", marginBottom: 6 }}>
                  AI Guidance & Takeaways
                </div>
                <ul style={{ margin: 0, paddingLeft: 18, fontSize: "0.82rem", color: "var(--foreground)", display: "flex", flexDirection: "column", gap: 4 }}>
                  {digest.recommendations.map((rec: string, i: number) => (
                    <li key={i}>{rec}</li>
                  ))}
                </ul>
              </div>
            ) : null}

            {/* Gratitude Journal Section */}
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <Heart size={16} style={{ color: "var(--accent-1)" }} />
                <h4 style={{ fontSize: "0.9rem", fontWeight: 700, color: "var(--foreground)", margin: 0 }}>
                  Daily Gratitude Journal (3 Wins)
                </h4>
              </div>

              <input
                type="text"
                placeholder="1. What went well today?"
                value={gratitude1}
                onChange={(e) => setGratitude1(e.target.value)}
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  borderRadius: "var(--radii-sm)",
                  border: "1px solid var(--border)",
                  background: "color-mix(in srgb, var(--foreground) 3%, transparent)",
                  color: "var(--foreground)",
                  fontSize: "0.82rem",
                }}
              />
              <input
                type="text"
                placeholder="2. A moment of clarity or progress..."
                value={gratitude2}
                onChange={(e) => setGratitude2(e.target.value)}
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  borderRadius: "var(--radii-sm)",
                  border: "1px solid var(--border)",
                  background: "color-mix(in srgb, var(--foreground) 3%, transparent)",
                  color: "var(--foreground)",
                  fontSize: "0.82rem",
                }}
              />
              <input
                type="text"
                placeholder="3. Someone or something you appreciated..."
                value={gratitude3}
                onChange={(e) => setGratitude3(e.target.value)}
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  borderRadius: "var(--radii-sm)",
                  border: "1px solid var(--border)",
                  background: "color-mix(in srgb, var(--foreground) 3%, transparent)",
                  color: "var(--foreground)",
                  fontSize: "0.82rem",
                }}
              />

              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 4 }}>
                <span style={{ fontSize: "0.75rem", color: savedGratitude ? "var(--accent-4)" : errorMessage ? "var(--accent-1)" : "transparent" }}>
                  {savedGratitude ? "✓ Gratitude saved for today!" : errorMessage || ""}
                </span>
                <button
                  onClick={handleSaveGratitude}
                  style={{
                    background: "var(--primary)",
                    color: "var(--primary-foreground)",
                    border: "none",
                    borderRadius: "var(--radii-sm)",
                    padding: "8px 16px",
                    fontSize: "0.8rem",
                    fontWeight: 600,
                    cursor: "pointer",
                  }}
                >
                  Save Reflections
                </button>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
