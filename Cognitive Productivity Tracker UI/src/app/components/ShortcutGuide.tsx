/**
 * Keyboard shortcuts cheat sheet modal overlay.
 *
 * Author: ChaChan26 <minhharry2006@gmail.com>
 * Copyright (c) 2026 ChaChan26. All rights reserved.
 */

import React from "react";
import { motion, AnimatePresence } from "motion/react";
import { Keyboard, X } from "lucide-react";

interface ShortcutGuideProps {
  isOpen: boolean;
  onClose: () => void;
}

export function ShortcutGuide({ isOpen, onClose }: ShortcutGuideProps) {
  const shortcuts = [
    { key: "Ctrl + K / ⌘K", desc: "Open Command Palette & Global Search" },
    { key: "1", desc: "Navigate to Home / Dashboard" },
    { key: "2", desc: "Navigate to Meditate / Zen Space" },
    { key: "3", desc: "Navigate to Analytics & Energy" },
    { key: "4", desc: "Navigate to Achievements" },
    { key: "5", desc: "Navigate to Settings & Config" },
    { key: "H", desc: "Toggle Companion Mini-HUD" },
    { key: "[", desc: "Collapse / Expand Sidebar" },
    { key: "B", desc: "Trigger Rest Break / Recovery Shield" },
    { key: "?", desc: "Toggle Keyboard Shortcuts Cheat Sheet" },
    { key: "Esc", desc: "Close Modals and Overlays" },
  ];

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          key="shortcut-guide-backdrop"
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
            background: "rgba(0, 0, 0, 0.6)",
            backdropFilter: "blur(8px)",
            WebkitBackdropFilter: "blur(8px)",
          }}
          onClick={onClose}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.92, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.92, y: 10 }}
            transition={{ duration: 0.16 }}
            onClick={(e) => e.stopPropagation()}
            style={{
              width: "100%",
              maxWidth: 520,
              background: "var(--card, #232336)",
              border: "1px solid var(--border, rgba(255,255,255,0.1))",
              borderRadius: "var(--radii-xl, 1.5rem)",
              padding: "24px 28px",
              boxShadow: "var(--shadow-lg, 0 25px 50px -12px rgba(0, 0, 0, 0.5))",
            }}
          >
            {/* Header */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                marginBottom: 20,
                paddingBottom: 14,
                borderBottom: "1px solid var(--border, rgba(255,255,255,0.08))",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <div
                  style={{
                    width: 34,
                    height: 34,
                    borderRadius: "var(--radii-md, 0.75rem)",
                    background: "color-mix(in srgb, var(--primary, #8E97FD) 20%, transparent)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "var(--primary, #8E97FD)",
                  }}
                >
                  <Keyboard size={18} />
                </div>
                <div>
                  <h3
                    style={{
                      margin: 0,
                      fontSize: "1.1rem",
                      fontWeight: 700,
                      color: "var(--foreground, #F6F1FB)",
                      fontFamily: "var(--font-sans)",
                    }}
                  >
                    Keyboard Shortcuts
                  </h3>
                  <span style={{ fontSize: "0.78rem", color: "var(--muted-foreground, #A1A4B2)" }}>
                    Quick navigation & actions
                  </span>
                </div>
              </div>
              <button
                onClick={onClose}
                style={{
                  background: "transparent",
                  border: "none",
                  color: "var(--muted-foreground, #A1A4B2)",
                  cursor: "pointer",
                  padding: 4,
                  display: "flex",
                  alignItems: "center",
                  borderRadius: "var(--radii-sm, 0.5rem)",
                }}
              >
                <X size={18} />
              </button>
            </div>

            {/* List */}
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {shortcuts.map((s, idx) => (
                <div
                  key={idx}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "8px 12px",
                    borderRadius: "var(--radii-md, 0.75rem)",
                    background: "var(--muted, rgba(255,255,255,0.04))",
                  }}
                >
                  <span style={{ fontSize: "0.88rem", color: "var(--foreground, #F6F1FB)" }}>
                    {s.desc}
                  </span>
                  <kbd
                    style={{
                      fontFamily: "var(--font-mono, 'DM Mono', monospace)",
                      fontSize: "0.75rem",
                      padding: "3px 8px",
                      background: "color-mix(in srgb, var(--primary, #8E97FD) 15%, transparent)",
                      border: "1px solid color-mix(in srgb, var(--primary, #8E97FD) 35%, transparent)",
                      color: "var(--primary, #8E97FD)",
                      borderRadius: "0.4rem",
                    }}
                  >
                    {s.key}
                  </kbd>
                </div>
              ))}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
