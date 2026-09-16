# Context

Two tasks combined:
1. Fix the React duplicate-key warning in Analytics (linearGradient stops lack keys)
2. Full redesign into 5-screen "Cognitive Shield Companion" MIND-FLOW app

# Fix for Key Warning

In `src/app/components/Analytics.tsx`, add `key` props to `<linearGradient>` and `<stop>` elements inside `<defs>`.

# New App: 5 Screens

Same palette/theme as before. New screens:

1. **Dashboard (Zen Hub)** — header with mode + wisdom quote, intention input, 5-segment battery + sparkline, foreground tracking card with +Work/+Recharge, vitality drawer with rings/sliders/tags
2. **Analytics (Energy Map)** — bar charts for Energy vs Friction, daily timeline, pie chart, frosted AI insight card, narrative paragraph
3. **Zen Space (Attention Restoration Room)** — particle canvas with dropdown, box breathing pacer, sound toggles, 5-4-3-2-1 grounding, community counter
4. **Preferences (Workspace Switcher)** — profile swapper toggle, classifier text areas, system switches, bottom bar with Pause/Shutdown
5. **Break Overlay** — full-screen frosted glass, serif headline, stretch card, hold-to-bypass only

# Files

- `src/styles/theme.css` — tokens already set, no change needed
- `src/app/App.tsx` — 5-tab nav + overlay
- `src/app/components/Dashboard.tsx` — full rewrite
- `src/app/components/Analytics.tsx` — fix keys + rewrite
- `src/app/components/ZenSpace.tsx` — new
- `src/app/components/Preferences.tsx` — replaces Settings.tsx
- `src/app/components/BreakOverlay.tsx` — update copy

# Verification

Preview all 5 tabs, no console key warnings, overlay works with hold-to-bypass.
