import { useState } from "react";
import { Plus, X } from "lucide-react";

const ZEN_LEVELS = ["Tranquil", "Balanced", "Sprint"] as const;
type ZenLevel = typeof ZEN_LEVELS[number];

const ZEN_META: Record<ZenLevel, { desc: string; color: string }> = {
  Tranquil: { desc: "Gentle nudges only. Long breaks, soft alerts.", color: "#8FA08D" },
  Balanced: { desc: "Standard focus blocks with mindful reminders.", color: "#7A9BAA" },
  Sprint: { desc: "Deep work maximised. Minimal interruptions.", color: "#C5A882" },
};

export function Settings() {
  const [zenLevel, setZenLevel] = useState<ZenLevel>("Balanced");
  const [focusKeywords, setFocusKeywords] = useState(["VS Code", "Figma", "Linear", "GitHub"]);
  const [recoveryKeywords, setRecoveryKeywords] = useState(["YouTube", "Twitter", "Reddit", "Slack"]);
  const [focusInput, setFocusInput] = useState("");
  const [recoveryInput, setRecoveryInput] = useState("");

  const addKeyword = (list: string[], setList: (v: string[]) => void, input: string, setInput: (v: string) => void) => {
    const v = input.trim();
    if (v && !list.includes(v)) setList([...list, v]);
    setInput("");
  };

  const remove = (list: string[], setList: (v: string[]) => void, item: string) =>
    setList(list.filter((k) => k !== item));

  return (
    <div className="flex flex-col gap-8 p-10 h-full overflow-y-auto">
      <div>
        <h2 style={{ fontFamily: "'Lora', serif", fontWeight: 500, color: "#2D312E", marginBottom: 2 }}>
          Settings & Rules
        </h2>
        <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.85rem", color: "#7D8579" }}>
          Shape how MIND-FLOW reads your day.
        </p>
      </div>

      {/* Zen Level */}
      <div className="rounded-2xl bg-card border border-border px-6 py-6 shadow-[0_4px_24px_rgba(45,49,46,0.06)]">
        <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.72rem", letterSpacing: "0.1em", color: "#7D8579", textTransform: "uppercase", marginBottom: 18 }}>
          Zen Level
        </div>
        <div className="flex gap-3 p-1.5 rounded-2xl" style={{ background: "#EDE8DF", display: "inline-flex" }}>
          {ZEN_LEVELS.map((level) => {
            const active = zenLevel === level;
            return (
              <button
                key={level}
                onClick={() => setZenLevel(level)}
                className="px-6 py-2.5 rounded-xl transition-all duration-200"
                style={{
                  fontFamily: "'DM Sans', sans-serif",
                  fontSize: "0.85rem",
                  background: active ? "#FDFCF9" : "transparent",
                  color: active ? "#2D312E" : "#7D8579",
                  boxShadow: active ? "0 2px 12px rgba(45,49,46,0.08)" : "none",
                  borderLeft: active ? `3px solid ${ZEN_META[level].color}` : "3px solid transparent",
                }}
              >
                {level}
              </button>
            );
          })}
        </div>
        <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.82rem", color: "#7D8579", marginTop: 14, paddingLeft: 2 }}>
          {ZEN_META[zenLevel].desc}
        </p>
      </div>

      {/* Keyword Management */}
      <div className="grid grid-cols-2 gap-6">
        {[
          { title: "Focus Keywords", list: focusKeywords, setList: setFocusKeywords, input: focusInput, setInput: setFocusInput, color: "#8FA08D", bg: "#E4EDE3" },
          { title: "Recovery Keywords", list: recoveryKeywords, setList: setRecoveryKeywords, input: recoveryInput, setInput: setRecoveryInput, color: "#C5A882", bg: "#EDE8DF" },
        ].map(({ title, list, setList, input, setInput, color, bg }) => (
          <div key={title} className="rounded-2xl bg-card border border-border px-6 py-6 shadow-[0_4px_24px_rgba(45,49,46,0.06)] flex flex-col gap-4">
            <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.72rem", letterSpacing: "0.1em", color: "#7D8579", textTransform: "uppercase" }}>
              {title}
            </div>
            <div className="flex gap-2">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addKeyword(list, setList, input, setInput)}
                placeholder="Add keyword…"
                className="flex-1 px-4 py-2.5 rounded-xl border border-border outline-none transition-all"
                style={{
                  fontFamily: "'DM Sans', sans-serif",
                  fontSize: "0.85rem",
                  background: "#F0EDE6",
                  color: "#2D312E",
                }}
              />
              <button
                onClick={() => addKeyword(list, setList, input, setInput)}
                className="w-10 h-10 rounded-xl flex items-center justify-center transition-all hover:opacity-80"
                style={{ background: color }}
              >
                <Plus size={16} color="#FDFCF9" />
              </button>
            </div>
            <div className="flex flex-col gap-2">
              {list.map((kw) => (
                <div
                  key={kw}
                  className="flex items-center justify-between px-4 py-2.5 rounded-xl"
                  style={{ background: bg }}
                >
                  <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.85rem", color: "#2D312E" }}>{kw}</span>
                  <button onClick={() => remove(list, setList, kw)} className="opacity-40 hover:opacity-70 transition-opacity">
                    <X size={13} />
                  </button>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
