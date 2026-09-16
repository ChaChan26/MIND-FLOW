/**
 * Command Palette global quick-launcher and action shortcut modal.
 *
 * Author: ChaChan26 <minhharry2006@gmail.com>
 * Copyright (c) 2026 ChaChan26. All rights reserved.
 */

import React, { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  Search, LayoutDashboard, Leaf, BarChart2, Settings2,
  Palette, Eye, Coffee, X, CornerDownLeft, Trophy
} from "lucide-react";
import { ThemeId, THEMES } from "../types/themes";

type CommandItem = {
  id: string;
  category: "Navigation" | "Actions" | "Themes";
  label: string;
  sub?: string;
  icon: React.ElementType;
  action: () => void;
  keywords?: string[];
};

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  onNavigate: (screen: "dashboard" | "analytics" | "zen" | "achievements" | "preferences") => void;
  onToggleEyeCare: () => void;
  eyeCareEnabled: boolean;
  onTriggerBreak: () => void;
  onSetTheme: (themeId: ThemeId) => void;
  activeTheme: ThemeId;
}

export function CommandPalette({
  isOpen,
  onClose,
  onNavigate,
  onToggleEyeCare,
  eyeCareEnabled,
  onTriggerBreak,
  onSetTheme,
  activeTheme,
}: CommandPaletteProps) {
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 50);
    } else {
      setQuery("");
      setSelectedIndex(0);
    }
  }, [isOpen]);

  const items: CommandItem[] = [
    // Navigation
    {
      id: "nav-dashboard",
      category: "Navigation",
      label: "Go to Home / Dashboard",
      sub: "Cognitive stamina battery & focus orb",
      icon: LayoutDashboard,
      keywords: ["home", "focus", "dashboard", "battery", "orb", "timer"],
      action: () => { onNavigate("dashboard"); onClose(); },
    },
    {
      id: "nav-zen",
      category: "Navigation",
      label: "Go to Meditate / Zen Space",
      sub: "Binaural audio & box breathing exercises",
      icon: Leaf,
      keywords: ["zen", "meditate", "breathing", "audio", "calm", "relax"],
      action: () => { onNavigate("zen"); onClose(); },
    },
    {
      id: "nav-analytics",
      category: "Navigation",
      label: "Go to Analytics & Energy",
      sub: "Circadian rhythm & productivity heatmap",
      icon: BarChart2,
      keywords: ["analytics", "charts", "stats", "history", "trends", "circadian"],
      action: () => { onNavigate("analytics"); onClose(); },
    },
    {
      id: "nav-achievements",
      category: "Navigation",
      label: "Go to Milestones & Badges",
      sub: "Cognitive streak progress & trophy room",
      icon: Trophy,
      keywords: ["trophy", "achievements", "badges", "streaks", "milestones"],
      action: () => { onNavigate("achievements"); onClose(); },
    },
    {
      id: "nav-preferences",
      category: "Navigation",
      label: "Go to Settings & Config",
      sub: "App classification rules & parameters",
      icon: Settings2,
      keywords: ["settings", "preferences", "config", "rules", "keywords"],
      action: () => { onNavigate("preferences"); onClose(); },
    },

    // Actions
    {
      id: "act-break",
      category: "Actions",
      label: "Start Rest Break Now",
      sub: "Trigger manual recovery shield overlay",
      icon: Coffee,
      keywords: ["break", "rest", "pause", "recharge", "stop"],
      action: () => { onTriggerBreak(); onClose(); },
    },
    {
      id: "act-eyecare",
      category: "Actions",
      label: eyeCareEnabled ? "Disable Eye Care Warm Filter" : "Enable Eye Care Warm Filter",
      sub: "Reduce blue light screen fatigue",
      icon: Eye,
      keywords: ["eye", "care", "filter", "warm", "blue", "light", "sepia"],
      action: () => { onToggleEyeCare(); onClose(); },
    },

    // Themes
    ...Object.entries(THEMES).map(([id, t]) => ({
      id: `theme-${id}`,
      category: "Themes" as const,
      label: `Switch Theme to ${t.name}`,
      sub: t.sub,
      icon: Palette,
      keywords: ["theme", id, t.name.toLowerCase()],
      action: () => { onSetTheme(id as ThemeId); onClose(); },
    })),
  ];

  const filtered = items.filter((item) => {
    if (!query.trim()) return true;
    const q = query.toLowerCase();
    const matchLabel = item.label.toLowerCase().includes(q);
    const matchSub = item.sub?.toLowerCase().includes(q);
    const matchKw = item.keywords?.some((k) => k.toLowerCase().includes(q));
    return matchLabel || matchSub || matchKw;
  });

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev + 1) % (filtered.length || 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev - 1 + (filtered.length || 1)) % (filtered.length || 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (filtered[selectedIndex]) {
        filtered[selectedIndex].action();
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      onClose();
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          key="command-palette-backdrop"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 9999,
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "center",
            paddingTop: "12vh",
            background: "rgba(0, 0, 0, 0.55)",
            backdropFilter: "blur(8px)",
            WebkitBackdropFilter: "blur(8px)",
          }}
          onClick={onClose}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: -20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -20 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
            onClick={(e) => e.stopPropagation()}
            style={{
              width: "100%",
              maxWidth: 620,
              background: "var(--card, #232336)",
              border: "1px solid var(--border, rgba(255,255,255,0.1))",
              borderRadius: "var(--radii-xl, 1.5rem)",
              overflow: "hidden",
              boxShadow: "var(--shadow-lg, 0 25px 50px -12px rgba(0, 0, 0, 0.5))",
            }}
          >
          {/* Header Input */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              padding: "16px 20px",
              borderBottom: "1px solid var(--border, rgba(255,255,255,0.08))",
            }}
          >
            <Search size={18} style={{ color: "var(--primary, #8E97FD)" }} />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type a command or search (e.g. Meditate, Nord, Rest)..."
              style={{
                flex: 1,
                background: "transparent",
                border: "none",
                outline: "none",
                color: "var(--foreground, #F6F1FB)",
                fontSize: "1rem",
                fontFamily: "'Nunito', sans-serif",
              }}
            />
            <button
              onClick={onClose}
              style={{
                background: "var(--muted, rgba(255,255,255,0.05))",
                border: "none",
                borderRadius: "var(--radii-sm, 0.5rem)",
                padding: 6,
                color: "var(--muted-foreground, #A1A4B2)",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <X size={16} />
            </button>
          </div>

          {/* Results List */}
          <div
            style={{
              maxHeight: 380,
              overflowY: "auto",
              padding: "8px 12px",
            }}
          >
            {filtered.length === 0 ? (
              <div
                style={{
                  padding: "32px 16px",
                  textAlign: "center",
                  color: "var(--muted-foreground, #A1A4B2)",
                  fontSize: "0.9rem",
                }}
              >
                No matching commands found.
              </div>
            ) : (
              filtered.map((item, idx) => {
                const isSelected = idx === selectedIndex;
                const ItemIcon = item.icon;
                return (
                  <div
                    key={item.id}
                    onClick={() => item.action()}
                    onMouseEnter={() => setSelectedIndex(idx)}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      padding: "10px 14px",
                      borderRadius: "var(--radii-md, 0.75rem)",
                      marginBottom: 4,
                      cursor: "pointer",
                      background: isSelected
                        ? "color-mix(in srgb, var(--primary, #8E97FD) 15%, transparent)"
                        : "transparent",
                      border: isSelected
                        ? "1px solid color-mix(in srgb, var(--primary, #8E97FD) 30%, transparent)"
                        : "1px solid transparent",
                      transition: "background 0.12s ease, border 0.12s ease",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                      <div
                        style={{
                          width: 32,
                          height: 32,
                          borderRadius: "var(--radii-sm, 0.5rem)",
                          background: isSelected
                            ? "var(--primary, #8E97FD)"
                            : "var(--muted, rgba(255,255,255,0.06))",
                          color: isSelected ? "#FFFFFF" : "var(--primary, #8E97FD)",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          transition: "all 0.12s ease",
                        }}
                      >
                        <ItemIcon size={16} />
                      </div>
                      <div>
                        <div
                          style={{
                            fontSize: "0.9rem",
                            fontWeight: 600,
                            color: "var(--foreground, #F6F1FB)",
                          }}
                        >
                          {item.label}
                        </div>
                        {item.sub && (
                          <div
                            style={{
                              fontSize: "0.75rem",
                              color: "var(--muted-foreground, #A1A4B2)",
                            }}
                          >
                            {item.sub}
                          </div>
                        )}
                      </div>
                    </div>

                    {isSelected && (
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 4,
                          fontSize: "0.7rem",
                          color: "var(--primary, #8E97FD)",
                          fontFamily: "'DM Mono', monospace",
                        }}
                      >
                        <span>Select</span>
                        <CornerDownLeft size={12} />
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>

          {/* Footer Shortcuts */}
          <div
            style={{
              padding: "10px 20px",
              borderTop: "1px solid var(--border, rgba(255,255,255,0.08))",
              background: "var(--muted, rgba(0,0,0,0.15))",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              fontSize: "0.72rem",
              color: "var(--muted-foreground, #A1A4B2)",
              fontFamily: "'DM Mono', monospace",
            }}
          >
            <div style={{ display: "flex", gap: 14 }}>
              <span>↑↓ Navigate</span>
              <span>↵ Execute</span>
              <span>Esc Exit</span>
            </div>
            <div>MIND-FLOW Palette</div>
          </div>
        </motion.div>
      </motion.div>
    )}
  </AnimatePresence>
);
}
