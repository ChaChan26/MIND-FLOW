import { useState, useEffect } from "react";
import { Plus, Minus, Droplets, Footprints, Moon, Check } from "lucide-react";

// ─── Constants ────────────────────────────────────────────────────────────────
const HYDRATION_GOAL = 2000; // ml
const STEP_GOAL = 10_000;
const SLEEP_GOAL_HOURS = 8;

// ─── Helpers ──────────────────────────────────────────────────────────────────
export function computeHydrationScore(totalMl: number): number {
  return Math.round(Math.min(totalMl / HYDRATION_GOAL, 1) * 100);
}
export function computeSleepScore(hours: number, quality: number): number {
  return Math.round(Math.min(hours / 9, 1) * 70 + ((quality - 1) / 4) * 30);
}

function calcSleepHours(bed: string, wake: string): number {
  const [bh, bm] = bed.split(":").map(Number);
  const [wh, wm] = wake.split(":").map(Number);
  let mins = (wh * 60 + wm) - (bh * 60 + bm);
  if (mins < 0) mins += 1440;
  return parseFloat((mins / 60).toFixed(1));
}

function fmtTime(d: Date) {
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

// ─── Sub-components ───────────────────────────────────────────────────────────
function VitalityRing({ label, value, color, raw }: { label: string; value: number; color: string; raw: string }) {
  const r = 30, circ = 2 * Math.PI * r;
  return (
    <div className="flex flex-col items-center gap-1.5">
      <svg width={72} height={72}>
        <circle cx={36} cy={36} r={r} fill="none" stroke="#EDE8DF" strokeWidth={5} />
        <circle cx={36} cy={36} r={r} fill="none" stroke={color} strokeWidth={5}
          strokeLinecap="round" strokeDasharray={circ}
          strokeDashoffset={circ - (Math.min(value, 100) / 100) * circ}
          style={{ transform: "rotate(-90deg)", transformOrigin: "50% 50%", transition: "stroke-dashoffset 0.8s ease" }}
        />
        <text x={36} y={39} textAnchor="middle" style={{ fontFamily: "'DM Mono', monospace", fontSize: 10.5, fill: "#2D312E", fontWeight: 500 }}>
          {Math.round(value)}%
        </text>
      </svg>
      <div style={{ textAlign: "center" }}>
        <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.72rem", color: "#7D8579" }}>{label}</div>
        <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.62rem", color }}>{raw}</div>
      </div>
    </div>
  );
}

function HydrationBeaker({ totalMl, goalMl }: { totalMl: number; goalMl: number }) {
  const level = Math.min(totalMl / goalMl, 1);
  const bx = 14, bw = 62, bodyTop = 26, bodyBottom = 188, bodyH = bodyBottom - bodyTop;
  const fillH = level * bodyH;
  const fillY = bodyBottom - fillH;

  return (
    <svg width={90} height={210} viewBox="0 0 90 210">
      <defs key="hydrationDefs">
        <clipPath key="hydBeakerClip" id="hydBeakerClip">
          <rect x={bx} y={bodyTop} width={bw} height={bodyH} rx={5} />
        </clipPath>
        <linearGradient key="waterGrad" id="waterGrad" x1="0" y1="0" x2="0" y2="1">
          <stop key="waterGrad0" offset="0%" stopColor="#7A9BAA" stopOpacity={0.6} />
          <stop key="waterGrad100" offset="100%" stopColor="#7A9BAA" stopOpacity={0.38} />
        </linearGradient>
      </defs>

      {/* Beaker body */}
      <rect x={bx} y={bodyTop} width={bw} height={bodyH} rx={5} fill="#F5F3EE" stroke="rgba(45,49,46,0.14)" strokeWidth={1.5} />

      {/* Lip/rim */}
      <rect x={bx - 4} y={bodyTop - 10} width={bw + 8} height={12} rx={4} fill="#EDE8DF" stroke="rgba(45,49,46,0.12)" strokeWidth={1} />

      {/* Spout notch on right */}
      <rect x={bx + bw - 2} y={bodyTop - 8} width={10} height={6} rx={2} fill="#EDE8DF" stroke="rgba(45,49,46,0.1)" strokeWidth={1} />

      {/* Water fill */}
      <rect x={bx} y={fillY} width={bw} height={fillH} fill="url(#waterGrad)" clipPath="url(#hydBeakerClip)" style={{ transition: "y 0.8s ease, height 0.8s ease" }} />

      {/* Water top shimmer wave */}
      {level > 0.02 && (
        <path
          d={`M ${bx} ${fillY} C ${bx + 16} ${fillY - 4} ${bx + 32} ${fillY + 4} ${bx + bw} ${fillY}`}
          fill="none" stroke="rgba(255,255,255,0.5)" strokeWidth={1.5} clipPath="url(#hydBeakerClip)"
        />
      )}

      {/* Measurement markers */}
      {[0.25, 0.5, 0.75].map((pct) => {
        const my = bodyBottom - pct * bodyH;
        return (
          <g key={pct}>
            <line x1={bx + 2} y1={my} x2={bx + 14} y2={my} stroke="rgba(45,49,46,0.22)" strokeWidth={0.8} />
            <text x={bx + 16} y={my + 3.5} fill="rgba(45,49,46,0.35)" style={{ fontSize: 7.5, fontFamily: "'DM Mono', monospace" }}>
              {Math.round(goalMl * pct)}
            </text>
          </g>
        );
      })}

      {/* Goal line */}
      <line x1={bx} y1={bodyTop + 2} x2={bx + bw} y2={bodyTop + 2} stroke="#7A9BAA" strokeWidth={1} strokeDasharray="3 2" opacity={0.4} />

      {/* Volume label */}
      <text x={45} y={202} textAnchor="middle" fill="#7A9BAA" style={{ fontSize: 11.5, fontFamily: "'DM Mono', monospace", fontWeight: "bold" }}>
        {totalMl}ml
      </text>
    </svg>
  );
}

// ─── Hydration Log Type ───────────────────────────────────────────────────────
interface HydLog { id: string; amount: number; label: string; time: Date }

const QUICK_ADD: { label: string; amount: number; emoji: string }[] = [
  { label: "Glass",  amount: 250,  emoji: "🥛" },
  { label: "Bottle", amount: 500,  emoji: "💧" },
  { label: "Large",  amount: 750,  emoji: "🫙" },
  { label: "Coffee", amount: 150,  emoji: "☕" },
];

// ─── Main Component ───────────────────────────────────────────────────────────
interface Props {
  sleep: number;
  hydration: number;
  onSetSleep: (v: number) => void;
  onSetHydration: (v: number) => void;
}

type VTab = "hydration" | "steps" | "sleep";

export function VitalityTracker({ sleep, hydration, onSetSleep, onSetHydration }: Props) {
  const [vTab, setVTab] = useState<VTab>("hydration");

  // ── Hydration state ─────────────────────────────────────────────────────
  const [hydLogs, setHydLogs] = useState<HydLog[]>([
    { id: "h1", amount: 500, label: "Water",  time: new Date(Date.now() - 7_200_000) },
    { id: "h2", amount: 150, label: "Coffee", time: new Date(Date.now() - 3_600_000) },
    { id: "h3", amount: 500, label: "Water",  time: new Date(Date.now() - 1_800_000) },
  ]);
  const [customMl, setCustomMl] = useState("");
  const [customLabel, setCustomLabel] = useState("Water");

  const totalHydMl = hydLogs.reduce((s, l) => s + l.amount, 0);
  const hydPct = computeHydrationScore(totalHydMl);

  const addHydration = (amount: number, label: string) => {
    setHydLogs(prev => [
      ...prev,
      { id: Date.now().toString(), amount, label, time: new Date() },
    ]);
  };

  const removeHydLog = (id: string) => setHydLogs(prev => prev.filter(l => l.id !== id));

  // ── Steps state ──────────────────────────────────────────────────────────
  const [stepCount, setStepCount] = useState(6_200);
  const [stepInput, setStepInput] = useState("");
  const [stepLogs, setStepLogs] = useState<{ id: string; amount: number; time: Date }[]>([
    { id: "s1", amount: 3200, time: new Date(Date.now() - 10_800_000) },
    { id: "s2", amount: 3000, time: new Date(Date.now() - 3_600_000) },
  ]);

  const stepPct = Math.round(Math.min(stepCount / STEP_GOAL, 1) * 100);

  const addSteps = (n: number) => {
    setStepCount(prev => prev + n);
    setStepLogs(prev => [...prev, { id: Date.now().toString(), amount: n, time: new Date() }]);
  };

  const logManualSteps = () => {
    const n = parseInt(stepInput);
    if (!n || n <= 0) return;
    setStepCount(n);
    setStepLogs(prev => [...prev, { id: Date.now().toString(), amount: n, time: new Date() }]);
    setStepInput("");
  };

  // ── Sleep state ──────────────────────────────────────────────────────────
  const [bedtime, setBedtime] = useState("23:30");
  const [waketime, setWaketime] = useState("07:18");
  const [sleepQuality, setSleepQuality] = useState(4);
  const [sleepNote, setSleepNote] = useState("");

  const sleepHours = calcSleepHours(bedtime, waketime);
  const sleepScore = computeSleepScore(sleepHours, sleepQuality);
  const sleepPct = Math.round((sleepHours / SLEEP_GOAL_HOURS) * 100);

  const sleepLabel =
    sleepHours >= 8 ? "Optimal" :
    sleepHours >= 6.5 ? "Adequate" :
    sleepHours >= 5 ? "Borderline" : "Insufficient";
  const sleepLabelColor =
    sleepHours >= 8 ? "#8FA08D" : sleepHours >= 6.5 ? "#C5A882" : "#C17B6B";

  // ── Sync engine ─────────────────────────────────────────────────────────
  useEffect(() => { onSetHydration(hydPct); }, [hydPct, onSetHydration]);
  useEffect(() => { onSetSleep(sleepScore); }, [sleepScore, onSetSleep]);

  // ── Tab buttons ──────────────────────────────────────────────────────────
  const VTABS: { id: VTab; label: string; Icon: typeof Droplets; color: string }[] = [
    { id: "hydration", label: "Hydration", Icon: Droplets,   color: "#7A9BAA" },
    { id: "steps",     label: "Steps",     Icon: Footprints, color: "#C5A882" },
    { id: "sleep",     label: "Sleep",     Icon: Moon,       color: "#8FA08D" },
  ];

  return (
    <div className="rounded-2xl bg-card border border-border shadow-[0_4px_20px_rgba(45,49,46,0.05)] overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4" style={{ borderBottom: "1px solid rgba(45,49,46,0.06)" }}>
        <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.68rem", letterSpacing: "0.1em", color: "#7D8579", textTransform: "uppercase" }}>
          Daily Vitality Tracker
        </div>
        <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.62rem", color: "#B5B0A8", letterSpacing: "0.04em" }}>
          {new Date().toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" })}
        </div>
      </div>

      {/* Vitality Rings Overview */}
      <div className="flex items-start justify-around px-6 py-5" style={{ background: "#FDFCF9" }}>
        <VitalityRing
          label="Steps"
          value={stepPct}
          color="#C5A882"
          raw={`${stepCount.toLocaleString()} / ${STEP_GOAL.toLocaleString()}`}
        />
        <div style={{ width: 1, background: "rgba(45,49,46,0.07)", alignSelf: "stretch" }} />
        <VitalityRing
          label="Sleep"
          value={Math.min(sleepPct, 100)}
          color="#8FA08D"
          raw={`${sleepHours}h · Q${sleepQuality}/5`}
        />
        <div style={{ width: 1, background: "rgba(45,49,46,0.07)", alignSelf: "stretch" }} />
        <VitalityRing
          label="Hydration"
          value={hydPct}
          color="#7A9BAA"
          raw={`${totalHydMl}ml / ${HYDRATION_GOAL}ml`}
        />
      </div>

      {/* Tab buttons */}
      <div className="flex gap-1 px-5 pb-3" style={{ borderTop: "1px solid rgba(45,49,46,0.06)" }}>
        {VTABS.map(({ id, label, Icon, color }) => (
          <button
            key={id}
            onClick={() => setVTab(id)}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl flex-1 justify-center transition-all duration-200 mt-3"
            style={{
              fontFamily: "'DM Sans', sans-serif", fontSize: "0.78rem",
              background: vTab === id ? `${color}18` : "transparent",
              color: vTab === id ? color : "#7D8579",
              border: `1.5px solid ${vTab === id ? color + "44" : "rgba(45,49,46,0.1)"}`,
            }}
          >
            <Icon size={13} />
            {label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="px-5 pb-5">

        {/* ── HYDRATION TAB ── */}
        {vTab === "hydration" && (
          <div className="flex gap-5">
            {/* Beaker */}
            <div className="flex flex-col items-center gap-2">
              <HydrationBeaker totalMl={totalHydMl} goalMl={HYDRATION_GOAL} />
              <div className="flex flex-col items-center gap-0.5">
                <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.65rem", color: "#7A9BAA", letterSpacing: "0.04em" }}>
                  {hydPct}% of daily goal
                </div>
                <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.62rem", color: "#B5B0A8" }}>
                  {Math.max(0, HYDRATION_GOAL - totalHydMl)}ml remaining
                </div>
              </div>
            </div>

            {/* Right side */}
            <div className="flex-1 flex flex-col gap-4">
              {/* Quick-add presets */}
              <div>
                <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.65rem", letterSpacing: "0.08em", color: "#7D8579", textTransform: "uppercase", marginBottom: 8 }}>
                  Quick Add
                </div>
                <div className="grid grid-cols-2 gap-2">
                  {QUICK_ADD.map(({ label, amount, emoji }) => (
                    <button
                      key={label}
                      onClick={() => addHydration(amount, label)}
                      className="flex items-center gap-2 px-3 py-2.5 rounded-xl border border-border transition-all duration-150 hover:opacity-80 active:scale-95"
                      style={{ background: "#F0EDE6", textAlign: "left" }}
                    >
                      <span style={{ fontSize: 16 }}>{emoji}</span>
                      <div>
                        <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.75rem", color: "#2D312E" }}>{label}</div>
                        <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.62rem", color: "#7A9BAA" }}>{amount}ml</div>
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Custom add */}
              <div>
                <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.65rem", letterSpacing: "0.08em", color: "#7D8579", textTransform: "uppercase", marginBottom: 8 }}>
                  Custom Log
                </div>
                <div className="flex gap-2">
                  <input
                    value={customLabel}
                    onChange={e => setCustomLabel(e.target.value)}
                    placeholder="Label"
                    className="flex-1 min-w-0 px-3 py-2 rounded-xl border border-border outline-none"
                    style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.78rem", background: "#F0EDE6", color: "#2D312E", width: "40%" }}
                  />
                  <input
                    value={customMl}
                    onChange={e => setCustomMl(e.target.value)}
                    placeholder="ml"
                    type="number"
                    className="px-3 py-2 rounded-xl border border-border outline-none"
                    style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.78rem", background: "#F0EDE6", color: "#2D312E", width: 64 }}
                  />
                  <button
                    onClick={() => {
                      const amt = parseInt(customMl);
                      if (amt > 0) { addHydration(amt, customLabel || "Water"); setCustomMl(""); }
                    }}
                    className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0 transition-all hover:opacity-80 active:scale-90"
                    style={{ background: "#7A9BAA" }}
                  >
                    <Plus size={15} style={{ color: "#FDFCF9" }} />
                  </button>
                </div>
              </div>

              {/* Log history */}
              <div>
                <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.65rem", letterSpacing: "0.08em", color: "#7D8579", textTransform: "uppercase", marginBottom: 8 }}>
                  Today's Log
                </div>
                <div className="flex flex-col gap-1.5 max-h-36 overflow-y-auto" style={{ scrollbarWidth: "none" }}>
                  {[...hydLogs].reverse().map(log => (
                    <div key={log.id} className="flex items-center gap-2 px-3 py-2 rounded-xl" style={{ background: "#F7F5F0" }}>
                      <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.6rem", color: "#B5B0A8", flexShrink: 0 }}>{fmtTime(log.time)}</span>
                      <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.75rem", color: "#2D312E", flex: 1 }}>{log.label}</span>
                      <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.68rem", color: "#7A9BAA", flexShrink: 0 }}>+{log.amount}ml</span>
                      <button onClick={() => removeHydLog(log.id)} className="shrink-0 hover:opacity-60 transition-opacity" style={{ background: "none", border: "none", cursor: "pointer", padding: 0 }}>
                        <Minus size={11} style={{ color: "#B5B0A8" }} />
                      </button>
                    </div>
                  ))}
                  {hydLogs.length === 0 && (
                    <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.75rem", color: "#B5B0A8", textAlign: "center", padding: "8px 0" }}>
                      No logs yet today
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── STEPS TAB ── */}
        {vTab === "steps" && (
          <div className="flex flex-col gap-4">
            {/* Big step count display */}
            <div className="flex items-center gap-4 rounded-2xl px-5 py-4" style={{ background: "#F7F5F0" }}>
              <div className="flex flex-col">
                <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "2rem", color: "#2D312E", letterSpacing: "-0.02em", lineHeight: 1 }}>
                  {stepCount.toLocaleString()}
                </div>
                <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.72rem", color: "#7D8579", marginTop: 4 }}>
                  of {STEP_GOAL.toLocaleString()} step goal
                </div>
              </div>
              <div className="flex-1">
                {/* Progress bar */}
                <div className="relative h-3 rounded-full overflow-hidden mb-2" style={{ background: "#EDE8DF" }}>
                  <div
                    className="absolute inset-y-0 left-0 rounded-full"
                    style={{
                      width: `${Math.min(stepPct, 100)}%`,
                      background: "linear-gradient(90deg, #C5A882, #D4BC9A)",
                      transition: "width 0.8s ease",
                      boxShadow: "0 0 8px rgba(197,168,130,0.4)",
                    }}
                  />
                </div>
                <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.65rem", color: stepPct >= 100 ? "#C5A882" : "#B5B0A8" }}>
                  {stepPct >= 100 ? "✓ Goal reached!" : `${stepPct}% · ${(STEP_GOAL - stepCount).toLocaleString()} to go`}
                </div>
              </div>
            </div>

            {/* Quick-add buttons */}
            <div>
              <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.65rem", letterSpacing: "0.08em", color: "#7D8579", textTransform: "uppercase", marginBottom: 8 }}>
                Quick Add Steps
              </div>
              <div className="flex gap-2">
                {[1000, 2500, 5000].map(n => (
                  <button
                    key={n}
                    onClick={() => addSteps(n)}
                    className="flex-1 py-2.5 rounded-xl border border-border transition-all hover:opacity-80 active:scale-95"
                    style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.75rem", background: "#F0EDE6", color: "#C5A882" }}
                  >
                    +{n.toLocaleString()}
                  </button>
                ))}
              </div>
            </div>

            {/* Manual entry */}
            <div>
              <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.65rem", letterSpacing: "0.08em", color: "#7D8579", textTransform: "uppercase", marginBottom: 8 }}>
                Set Total Steps
              </div>
              <div className="flex gap-2">
                <input
                  value={stepInput}
                  onChange={e => setStepInput(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && logManualSteps()}
                  placeholder="e.g. 8500"
                  type="number"
                  className="flex-1 px-4 py-2.5 rounded-xl border border-border outline-none"
                  style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.85rem", background: "#F0EDE6", color: "#2D312E" }}
                />
                <button
                  onClick={logManualSteps}
                  className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0 transition-all hover:opacity-80 active:scale-90"
                  style={{ background: "#C5A882" }}
                >
                  <Check size={15} style={{ color: "#FDFCF9" }} />
                </button>
              </div>
            </div>

            {/* Step log */}
            <div>
              <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.65rem", letterSpacing: "0.08em", color: "#7D8579", textTransform: "uppercase", marginBottom: 8 }}>
                Activity Log
              </div>
              <div className="flex flex-col gap-1.5">
                {[...stepLogs].reverse().map(log => (
                  <div key={log.id} className="flex items-center gap-3 px-3 py-2 rounded-xl" style={{ background: "#F7F5F0" }}>
                    <Footprints size={13} style={{ color: "#C5A882", flexShrink: 0 }} />
                    <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.6rem", color: "#B5B0A8" }}>{fmtTime(log.time)}</span>
                    <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.75rem", color: "#2D312E", flex: 1 }}>+{log.amount.toLocaleString()} steps</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ── SLEEP TAB ── */}
        {vTab === "sleep" && (
          <div className="flex flex-col gap-4">
            {/* Sleep duration block */}
            <div className="flex gap-4">
              {/* Big hours display */}
              <div className="flex-1 rounded-2xl px-5 py-4 flex flex-col items-center justify-center" style={{ background: "#F7F5F0" }}>
                <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "2.4rem", color: "#2D312E", letterSpacing: "-0.02em", lineHeight: 1 }}>
                  {sleepHours}
                </div>
                <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.72rem", color: "#7D8579", marginTop: 4 }}>hours slept</div>
                <div className="mt-2 px-3 py-1 rounded-full" style={{ background: `${sleepLabelColor}18`, border: `1px solid ${sleepLabelColor}33` }}>
                  <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.62rem", color: sleepLabelColor, letterSpacing: "0.06em" }}>
                    {sleepLabel}
                  </span>
                </div>
              </div>

              {/* Sleep score ring */}
              <div className="flex flex-col items-center justify-center gap-2">
                <svg width={80} height={80}>
                  {(() => {
                    const r = 34, circ = 2 * Math.PI * r;
                    return (
                      <>
                        <circle cx={40} cy={40} r={r} fill="none" stroke="#EDE8DF" strokeWidth={5} />
                        <circle cx={40} cy={40} r={r} fill="none" stroke="#8FA08D" strokeWidth={5}
                          strokeLinecap="round" strokeDasharray={circ}
                          strokeDashoffset={circ - (sleepScore / 100) * circ}
                          style={{ transform: "rotate(-90deg)", transformOrigin: "50% 50%", transition: "stroke-dashoffset 0.8s ease" }}
                        />
                        <text x={40} y={44} textAnchor="middle" style={{ fontFamily: "'DM Mono', monospace", fontSize: 12, fill: "#2D312E" }}>
                          {sleepScore}
                        </text>
                      </>
                    );
                  })()}
                </svg>
                <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.65rem", color: "#7D8579", textAlign: "center" }}>
                  Sleep<br />Score
                </div>
              </div>
            </div>

            {/* Bedtime / Wake time */}
            <div className="grid grid-cols-2 gap-3">
              {[
                { label: "Bedtime", icon: "🌙", val: bedtime, set: setBedtime },
                { label: "Wake Time", icon: "🌅", val: waketime, set: setWaketime },
              ].map(({ label, icon, val, set }) => (
                <div key={label} className="rounded-xl px-4 py-3" style={{ background: "#F7F5F0", border: "1px solid rgba(45,49,46,0.08)" }}>
                  <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.62rem", color: "#7D8579", marginBottom: 6 }}>
                    {icon} {label}
                  </div>
                  <input
                    type="time"
                    value={val}
                    onChange={e => set(e.target.value)}
                    className="w-full outline-none bg-transparent"
                    style={{ fontFamily: "'DM Mono', monospace", fontSize: "1.05rem", color: "#2D312E", border: "none" }}
                  />
                </div>
              ))}
            </div>

            {/* Sleep quality stars */}
            <div>
              <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.65rem", letterSpacing: "0.08em", color: "#7D8579", textTransform: "uppercase", marginBottom: 10 }}>
                Sleep Quality
              </div>
              <div className="flex gap-2 items-center">
                {[1, 2, 3, 4, 5].map(star => (
                  <button
                    key={star}
                    onClick={() => setSleepQuality(star)}
                    className="transition-all duration-150 hover:scale-110 active:scale-95"
                    style={{ background: "none", border: "none", cursor: "pointer", padding: 2, fontSize: star <= sleepQuality ? "1.6rem" : "1.4rem", opacity: star <= sleepQuality ? 1 : 0.3 }}
                  >
                    ⭐
                  </button>
                ))}
                <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.75rem", color: "#7D8579", marginLeft: 6 }}>
                  {["", "Very Poor", "Poor", "Fair", "Good", "Excellent"][sleepQuality]}
                </span>
              </div>
            </div>

            {/* Sleep notes */}
            <div>
              <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.65rem", letterSpacing: "0.08em", color: "#7D8579", textTransform: "uppercase", marginBottom: 8 }}>
                Notes
              </div>
              <input
                value={sleepNote}
                onChange={e => setSleepNote(e.target.value)}
                placeholder="Vivid dreams, restless, woke at 3am…"
                className="w-full px-4 py-2.5 rounded-xl border border-border outline-none"
                style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.82rem", background: "#F0EDE6", color: "#2D312E" }}
              />
            </div>

            {/* Sleep tip */}
            {sleepHours < 7 && (
              <div className="flex items-center gap-2 px-4 py-3 rounded-xl" style={{ background: "rgba(197,168,130,0.08)", border: "1px solid rgba(197,168,130,0.2)" }}>
                <Moon size={13} style={{ color: "#C5A882", flexShrink: 0 }} />
                <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.75rem", color: "#7D8579", lineHeight: 1.5 }}>
                  Less than 7h logged. Autopilot will apply additional fatigue scaling to protect your focus sessions.
                </span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
