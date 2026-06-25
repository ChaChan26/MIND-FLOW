import { useState, useEffect, useRef } from "react";

// ─── Types ────────────────────────────────────────────────────────────────────
type Scene = "cosmic" | "ocean" | "forest";
type PatternKey = "box" | "relax" | "coherent";
type BreathPhase = "idle" | "inhale" | "hold-in" | "exhale" | "hold-out";
type ZenTab = "breathe" | "sounds" | "ground" | "community";

// ─── Constants ────────────────────────────────────────────────────────────────
interface PhaseStep { n: string; d: number; t: BreathPhase }

const PATTERNS: Record<PatternKey, { label: string; tag: string; desc: string; color: string; phases: PhaseStep[] }> = {
  box: {
    label: "Box Breathing", tag: "4-4-4-4", color: "#8FA08D",
    desc: "Steady 4-second rhythm. Calms the nervous system and sharpens focus.",
    phases: [{ n: "Inhale", d: 4, t: "inhale" }, { n: "Hold", d: 4, t: "hold-in" }, { n: "Exhale", d: 4, t: "exhale" }, { n: "Hold", d: 4, t: "hold-out" }],
  },
  relax: {
    label: "Relax Breathing", tag: "4-7-8", color: "#7A9BAA",
    desc: "Inhale 4s · Hold 7s · Exhale 8s. Quiets the fight-or-flight response.",
    phases: [{ n: "Inhale", d: 4, t: "inhale" }, { n: "Hold", d: 7, t: "hold-in" }, { n: "Exhale", d: 8, t: "exhale" }],
  },
  coherent: {
    label: "Coherent Breathing", tag: "5-5", color: "#C5A882",
    desc: "Equal inhale/exhale at 6 breaths/min. Balances heart rate variability.",
    phases: [{ n: "Inhale", d: 5, t: "inhale" }, { n: "Exhale", d: 5, t: "exhale" }],
  },
};

const SCENE_LABELS: Record<Scene, string> = { cosmic: "✦ Cosmic Flow", ocean: "〜 Ocean Waves", forest: "❋ Forest Light" };

const GROUNDING = [
  { n: 5, sense: "See",   icon: "👁",  color: "#8FA08D", prompt: "Name 5 things you can see — their shape, color, and texture." },
  { n: 4, sense: "Touch", icon: "🤲", color: "#7A9BAA", prompt: "Notice 4 textures around you — warm, cool, rough, smooth." },
  { n: 3, sense: "Hear",  icon: "👂", color: "#C5A882", prompt: "Listen for 3 distinct sounds, near and far. Just observe." },
  { n: 2, sense: "Smell", icon: "🌿", color: "#B89A8A", prompt: "Find 2 scents you can detect. Even the subtlest ones count." },
  { n: 1, sense: "Taste", icon: "🫧", color: "#A8B5A6", prompt: "Notice 1 lingering taste. Sit with it without judgment." },
];

const STRETCHES = [
  { name: "Shoulder Rolls",    dur: 30, icon: "🔄", instr: "Roll shoulders backward in 5 slow circles. Feel the tension unwinding. Reverse direction." },
  { name: "Neck Circles",      dur: 25, icon: "💫", instr: "Gently tilt your head side to side — 3 passes each way. Move slowly, never force it." },
  { name: "Wrist Rotations",   dur: 20, icon: "🙌", instr: "Extend both arms. Rotate wrists in full circles — 5 clockwise, 5 counterclockwise." },
  { name: "20-20-20 Eye Rest", dur: 20, icon: "👁",  instr: "Look at something 20 feet away for 20 seconds. Blink slowly 5 times to lubricate your eyes." },
  { name: "Deep Breath Reset", dur: 15, icon: "🫁", instr: "Inhale 4s · hold 2s · exhale 6s. Let your shoulders drop. Repeat 3 times." },
];

const CIRCLES = [
  { id: "morning", name: "Morning Calm",  emoji: "🌅", color: "#C5A882", bg: "#F5EFE5", prompt: "Begin with stillness. What are you releasing today?",         base: 47  },
  { id: "deep",    name: "Deep Focus",    emoji: "🌊", color: "#7A9BAA", bg: "#E0EBF0", prompt: "Flow state is near. What one thing matters most right now?",  base: 123 },
];

const DAILY_PROMPTS = [
  "Let the breath carry away what no longer serves you.",
  "Each exhale is a small release. Trust it.",
  "You are here. That is already enough.",
  "Stillness is not emptiness — it is clarity gathering.",
];

// ─── Sound Synthesis ──────────────────────────────────────────────────────────
function buildAlphaDrone(ctx: AudioContext, master: GainNode): () => void {
  const g = ctx.createGain(); g.gain.value = 0.2; g.connect(master);
  const freqs = [110, 165, 220, 293.66];
  const oscs = freqs.map(f => {
    const o = ctx.createOscillator(), og = ctx.createGain();
    o.type = "sine"; o.frequency.value = f; og.gain.value = 0.5 / freqs.length;
    o.connect(og); og.connect(g); o.start(); return o;
  });
  const lfo = ctx.createOscillator(), lg = ctx.createGain();
  lfo.frequency.value = 0.07; lg.gain.value = 0.05;
  lfo.connect(lg); lg.connect(g.gain); lfo.start();
  return () => { [...oscs, lfo].forEach(o => { try { o.stop(); } catch { /* already stopped */ } }); g.disconnect(); };
}

function buildForestRain(ctx: AudioContext, master: GainNode): () => void {
  const sz = ctx.sampleRate * 3;
  const buf = ctx.createBuffer(2, sz, ctx.sampleRate);
  for (let c = 0; c < 2; c++) { const d = buf.getChannelData(c); for (let i = 0; i < sz; i++) d[i] = Math.random() * 2 - 1; }
  const src = ctx.createBufferSource(); src.buffer = buf; src.loop = true;
  const lpf = ctx.createBiquadFilter(); lpf.type = "lowpass"; lpf.frequency.value = 2400;
  const hpf = ctx.createBiquadFilter(); hpf.type = "highpass"; hpf.frequency.value = 200;
  const g = ctx.createGain(); g.gain.value = 0.28;
  src.connect(hpf); hpf.connect(lpf); lpf.connect(g); g.connect(master); src.start();
  return () => { try { src.stop(); } catch { /* already stopped */ } g.disconnect(); };
}

function buildWindChimes(ctx: AudioContext, master: GainNode): () => void {
  const g = ctx.createGain(); g.gain.value = 0.4; g.connect(master);
  const freqs = [523.25, 659.25, 783.99, 880, 1046.5, 1318.5];
  let alive = true;
  const chime = () => {
    if (!alive) return;
    const f = freqs[Math.floor(Math.random() * freqs.length)];
    const osc = ctx.createOscillator(), og = ctx.createGain();
    osc.type = "sine"; osc.frequency.value = f;
    const now = ctx.currentTime;
    og.gain.setValueAtTime(0.001, now);
    og.gain.linearRampToValueAtTime(0.32, now + 0.012);
    og.gain.exponentialRampToValueAtTime(0.001, now + 4.5);
    osc.connect(og); og.connect(g); osc.start(now); osc.stop(now + 4.5);
    setTimeout(chime, Math.random() * 2800 + 900);
  };
  setTimeout(chime, 400);
  return () => { alive = false; g.disconnect(); };
}

function strikeBowl(ctx: AudioContext, master: GainNode) {
  const g = ctx.createGain(); g.gain.value = 0.6; g.connect(master);
  [[432, 0.7], [864, 0.38], [1296, 0.2], [1728, 0.09]].forEach(([f, v], i) => {
    const osc = ctx.createOscillator(), og = ctx.createGain();
    osc.type = "sine"; osc.frequency.value = f;
    const dur = 9 - i * 1.8, now = ctx.currentTime;
    og.gain.setValueAtTime(v, now); og.gain.exponentialRampToValueAtTime(0.001, now + dur);
    osc.connect(og); og.connect(g); osc.start(now); osc.stop(now + dur);
  });
  setTimeout(() => g.disconnect(), 10000);
}

// ─── Particle Canvas ──────────────────────────────────────────────────────────
interface Particle { x: number; y: number; homeX: number; homeY: number; vx: number; vy: number; r: number; a: number; phase: number; speed: number }

const SCENE_BG: Record<Scene, string> = { cosmic: "#12152B", ocean: "#0D1F2D", forest: "#0E1A0F" };
const SCENE_RGB: Record<Scene, [number, number, number]> = { cosmic: [180, 200, 255], ocean: [80, 170, 200], forest: [100, 185, 110] };

function BreathingCanvas({ scene, phaseType, phaseProgress }: { scene: Scene; phaseType: BreathPhase; phaseProgress: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const particlesRef = useRef<Particle[]>([]);
  const animRef = useRef<number>(0);
  const breathRef = useRef({ phaseType, phaseProgress });
  breathRef.current = { phaseType, phaseProgress };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const init = () => {
      canvas.width = canvas.offsetWidth;
      canvas.height = canvas.offsetHeight;
      const W = canvas.width, H = canvas.height;
      const count = scene === "cosmic" ? 140 : scene === "ocean" ? 100 : 90;
      particlesRef.current = Array.from({ length: count }, () => {
        const homeX = Math.random() * W, homeY = scene === "forest" ? H + Math.random() * H : Math.random() * H;
        return {
          x: homeX, y: homeY, homeX, homeY,
          vx: (Math.random() - 0.5) * 0.3, vy: scene === "forest" ? -Math.random() * 0.5 - 0.2 : (Math.random() - 0.5) * 0.2,
          r: Math.random() * (scene === "cosmic" ? 1.5 : 3) + 0.8,
          a: Math.random() * 0.5 + 0.3,
          phase: Math.random() * Math.PI * 2,
          speed: Math.random() * 0.4 + 0.1,
        };
      });
    };

    const ro = new ResizeObserver(init);
    ro.observe(canvas);
    init();

    let t = 0;
    const draw = () => {
      const W = canvas.width, H = canvas.height;
      const cx = W / 2, cy = H / 2;
      const { phaseType: pt, phaseProgress: pp } = breathRef.current;
      t += 0.016;

      // Background
      ctx.fillStyle = SCENE_BG[scene];
      ctx.fillRect(0, 0, W, H);

      // Radial glow that pulses with breath
      const glowRadius = pt === "inhale" ? 0.18 + pp * 0.22
        : pt === "hold-in" ? 0.4
        : pt === "exhale" ? 0.4 - pp * 0.22
        : 0.18;
      const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, Math.min(W, H) * glowRadius);
      const [r, g, b] = SCENE_RGB[scene];
      grad.addColorStop(0, `rgba(${r},${g},${b},0.12)`);
      grad.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, W, H);

      // Particles
      const particles = particlesRef.current;
      for (const p of particles) {
        // Base drift
        p.phase += 0.008;

        if (scene === "forest") {
          // Upward drift - slow on inhale, faster on exhale
          const speed = pt === "inhale" ? 0.15 : pt === "exhale" ? 0.7 : 0.4;
          p.y += p.vy * speed * p.speed;
          p.x += Math.sin(p.phase) * 0.3;
          if (p.y < -10) { p.y = H + 10; p.x = Math.random() * W; }
          // Warm glow on inhale
          const warmth = pt === "inhale" ? pp : pt === "hold-in" ? 1 : 1 - pp;
          const gr = r + Math.round((220 - r) * warmth * 0.4);
          const gg = g + Math.round((170 - g) * warmth * 0.2);
          ctx.beginPath(); ctx.arc(p.x, p.y, p.r + warmth * 1.5, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(${gr},${gg},${b},${p.a * (0.6 + warmth * 0.4)})`;
          ctx.fill();
        } else if (scene === "ocean") {
          // Wave oscillation
          const amplitude = pt === "inhale" ? 12 + pp * 20 : pt === "hold-in" ? 32 : 32 - pp * 20;
          p.y = p.homeY + Math.sin(p.phase + p.homeX * 0.01) * amplitude;
          p.x += p.vx * 0.4;
          if (p.x < -5) p.x = W + 5;
          if (p.x > W + 5) p.x = -5;
          ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(${r},${g},${b},${p.a})`;
          ctx.fill();
        } else {
          // Cosmic — flow toward/away from center
          if (pt === "inhale") {
            p.x += (cx - p.x) * 0.002 * pp;
            p.y += (cy - p.y) * 0.002 * pp;
          } else if (pt === "exhale") {
            p.x += (p.homeX - p.x) * 0.003 * pp;
            p.y += (p.homeY - p.y) * 0.003 * pp;
          } else {
            p.x += p.vx * 0.5;
            p.y += p.vy * 0.5;
            if (p.x < 0 || p.x > W) p.vx *= -1;
            if (p.y < 0 || p.y > H) p.vy *= -1;
          }
          // Twinkle
          const twinkle = 0.5 + 0.5 * Math.sin(p.phase * 3);
          ctx.beginPath(); ctx.arc(p.x, p.y, p.r * (0.8 + twinkle * 0.4), 0, Math.PI * 2);
          ctx.fillStyle = `rgba(${r},${g},${b},${p.a * (0.4 + twinkle * 0.6)})`;
          ctx.fill();
          // Connection lines for nearby stars
          if (scene === "cosmic" && p.r > 1.5) {
            for (const q of particles) {
              if (q === p || q.r <= 1.5) continue;
              const dx = q.x - p.x, dy = q.y - p.y, dist = Math.sqrt(dx * dx + dy * dy);
              if (dist < 60) {
                ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(q.x, q.y);
                ctx.strokeStyle = `rgba(${r},${g},${b},${(1 - dist / 60) * 0.06})`;
                ctx.lineWidth = 0.5; ctx.stroke();
              }
            }
          }
        }
      }

      animRef.current = requestAnimationFrame(draw);
    };
    draw();

    return () => { cancelAnimationFrame(animRef.current); ro.disconnect(); };
  }, [scene]);

  return <canvas ref={canvasRef} style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }} />;
}

// ─── Stretch Modal ────────────────────────────────────────────────────────────
function StretchModal({ onClose }: { onClose: () => void }) {
  const [step, setStep] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const stretch = STRETCHES[step];

  useEffect(() => {
    setElapsed(0);
    const id = setInterval(() => {
      setElapsed(e => {
        if (e + 1 >= stretch.dur) {
          if (step < STRETCHES.length - 1) { setStep(s => s + 1); return 0; }
          clearInterval(id); return stretch.dur;
        }
        return e + 1;
      });
    }, 1000);
    return () => clearInterval(id);
  }, [step, stretch.dur]);

  const pct = elapsed / stretch.dur;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: "rgba(10,20,15,0.88)", backdropFilter: "blur(20px)" }}>
      <div className="flex flex-col items-center gap-6 max-w-md w-full px-8">
        {/* Progress steps */}
        <div className="flex gap-2">
          {STRETCHES.map((s, i) => (
            <div key={s.name} style={{ width: 32, height: 4, borderRadius: 2, background: i < step ? "#8FA08D" : i === step ? "#8FA08D88" : "rgba(255,255,255,0.15)" }} />
          ))}
        </div>

        {/* Icon + timer ring */}
        <div style={{ position: "relative", width: 120, height: 120 }}>
          <svg width={120} height={120} style={{ transform: "rotate(-90deg)" }}>
            <circle cx={60} cy={60} r={52} fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth={5} />
            <circle cx={60} cy={60} r={52} fill="none" stroke="#8FA08D" strokeWidth={5}
              strokeLinecap="round" strokeDasharray={2 * Math.PI * 52}
              strokeDashoffset={2 * Math.PI * 52 * (1 - pct)}
              style={{ transition: "stroke-dashoffset 1s linear" }}
            />
          </svg>
          <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
            <span style={{ fontSize: 28 }}>{stretch.icon}</span>
            <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.82rem", color: "#8FA08D", marginTop: 4 }}>
              {stretch.dur - elapsed}s
            </span>
          </div>
        </div>

        <div style={{ textAlign: "center" }}>
          <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.62rem", letterSpacing: "0.12em", color: "#8FA08D", textTransform: "uppercase", marginBottom: 8 }}>
            Step {step + 1} of {STRETCHES.length}
          </div>
          <h2 style={{ fontFamily: "'Lora', serif", fontSize: "1.5rem", color: "#FDFCF9", marginBottom: 12 }}>{stretch.name}</h2>
          <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.9rem", color: "rgba(255,255,255,0.65)", lineHeight: 1.65 }}>{stretch.instr}</p>
        </div>

        <button
          onClick={onClose}
          style={{
            fontFamily: "'DM Sans', sans-serif", fontSize: "0.78rem",
            color: "rgba(255,255,255,0.4)", background: "none", border: "none",
            cursor: "pointer", marginTop: 4,
          }}
        >
          Skip stretch session
        </button>
      </div>
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────
export function ZenSpace() {
  const [scene, setScene] = useState<Scene>("cosmic");
  const [pattern, setPattern] = useState<PatternKey>("box");
  const [breathing, setBreathing] = useState(false);
  const [phaseIdx, setPhaseIdx] = useState(0);
  const [phaseSeconds, setPhaseSeconds] = useState(4);
  const [totalBreaths, setTotalBreaths] = useState(14_284);
  const [tab, setTab] = useState<ZenTab>("breathe");
  const [eyeCare, setEyeCare] = useState(false);
  const [showStretch, setShowStretch] = useState(false);

  // Grounding
  const [groundStep, setGroundStep] = useState(-1);
  const [groundDone, setGroundDone] = useState(new Set<number>());

  // Community
  const [joined, setJoined] = useState<string | null>(null);
  const [counts, setCounts] = useState<Record<string, number>>({ morning: 47, deep: 123 });
  const promptIdx = useRef(Math.floor(Math.random() * DAILY_PROMPTS.length)).current;

  // Sound engine
  const audioCtxRef = useRef<AudioContext | null>(null);
  const masterGainRef = useRef<GainNode | null>(null);
  const stoppers = useRef<Record<string, (() => void) | null>>({});
  const [activeSounds, setActiveSounds] = useState<Set<string>>(new Set());
  const [masterVol, setMasterVol] = useState(0.6);
  const [bowlRinging, setBowlRinging] = useState(false);

  const getAudio = () => {
    if (!audioCtxRef.current) {
      audioCtxRef.current = new AudioContext();
      masterGainRef.current = audioCtxRef.current.createGain();
      masterGainRef.current.gain.value = masterVol;
      masterGainRef.current.connect(audioCtxRef.current.destination);
    }
    if (audioCtxRef.current.state === "suspended") audioCtxRef.current.resume();
    return { ctx: audioCtxRef.current, master: masterGainRef.current! };
  };

  const toggleSound = (id: string, builder: (ctx: AudioContext, master: GainNode) => () => void) => {
    if (activeSounds.has(id)) {
      stoppers.current[id]?.(); stoppers.current[id] = null;
      setActiveSounds(prev => { const s = new Set(prev); s.delete(id); return s; });
    } else {
      const { ctx, master } = getAudio();
      stoppers.current[id] = builder(ctx, master);
      setActiveSounds(prev => new Set([...prev, id]));
    }
  };

  const handleStrikeBowl = () => {
    const { ctx, master } = getAudio();
    strikeBowl(ctx, master);
    setBowlRinging(true);
    setTimeout(() => setBowlRinging(false), 9000);
  };

  const handleVolumeChange = (v: number) => {
    setMasterVol(v);
    if (masterGainRef.current) masterGainRef.current.gain.value = v;
  };

  // Eye care filter on document body
  useEffect(() => {
    document.body.style.filter = eyeCare ? "sepia(0.2) brightness(0.88) saturate(0.85)" : "";
    return () => { document.body.style.filter = ""; };
  }, [eyeCare]);

  // Cleanup audio on unmount
  useEffect(() => {
    return () => {
      Object.values(stoppers.current).forEach(stop => stop?.());
      audioCtxRef.current?.close();
    };
  }, []);

  // Breathing timer
  const phases = PATTERNS[pattern].phases;
  const curPhase = phases[phaseIdx];

  useEffect(() => {
    if (!breathing) return;
    const id = setInterval(() => {
      setPhaseSeconds(s => {
        if (s <= 1) {
          setPhaseIdx(p => {
            const next = (p + 1) % phases.length;
            if (next === 0) setTotalBreaths(b => b + 1);
            return next;
          });
          return phases[(phaseIdx + 1) % phases.length].d;
        }
        return s - 1;
      });
    }, 1000);
    return () => clearInterval(id);
  }, [breathing, phaseIdx, phases]);

  const startBreathing = () => {
    setPhaseIdx(0); setPhaseSeconds(phases[0].d); setBreathing(true);
  };
  const stopBreathing = () => { setBreathing(false); setPhaseIdx(0); setPhaseSeconds(phases[0].d); };

  // Community fluctuation
  useEffect(() => {
    const id = setInterval(() => {
      setCounts(prev => ({
        morning: Math.max(30, prev.morning + Math.round((Math.random() - 0.48) * 3)),
        deep:    Math.max(80, prev.deep    + Math.round((Math.random() - 0.48) * 5)),
      }));
    }, 4000);
    return () => clearInterval(id);
  }, []);

  // Derived breath state for canvas
  const phaseType: BreathPhase = breathing ? curPhase.t : "idle";
  const phaseProgress = breathing ? 1 - phaseSeconds / curPhase.d : 0;

  // Circle scale for breathing guide
  const circleScale = phaseType === "inhale" ? 1 + phaseProgress * 0.42
    : phaseType === "hold-in" ? 1.42
    : phaseType === "exhale" ? 1.42 - phaseProgress * 0.42
    : 1;

  const patColor = PATTERNS[pattern].color;

  const TABS: { id: ZenTab; label: string }[] = [
    { id: "breathe", label: "Breathe" }, { id: "sounds", label: "Sounds" },
    { id: "ground", label: "5-4-3-2-1" }, { id: "community", label: "Community" },
  ];

  return (
    <div className="flex flex-col h-full overflow-hidden" style={{ background: "var(--background)" }}>

      {/* ── Canvas Hero ─────────────────────────────────────────────────── */}
      <div style={{ position: "relative", height: "52%", flexShrink: 0, overflow: "hidden" }}>
        <BreathingCanvas scene={scene} phaseType={phaseType} phaseProgress={phaseProgress} />

        {/* Top controls overlay */}
        <div style={{ position: "absolute", top: 14, left: 16, right: 16, display: "flex", alignItems: "center", justifyContent: "space-between", zIndex: 2 }}>
          {/* Scene pills */}
          <div className="flex gap-1.5">
            {(Object.keys(SCENE_LABELS) as Scene[]).map(s => (
              <button key={s} onClick={() => setScene(s)}
                className="px-3 py-1.5 rounded-xl transition-all duration-200"
                style={{
                  fontFamily: "'DM Mono', monospace", fontSize: "0.6rem", letterSpacing: "0.06em",
                  background: scene === s ? "rgba(255,255,255,0.18)" : "rgba(0,0,0,0.25)",
                  color: scene === s ? "#ffffff" : "rgba(255,255,255,0.45)",
                  border: `1px solid ${scene === s ? "rgba(255,255,255,0.3)" : "rgba(255,255,255,0.08)"}`,
                  backdropFilter: "blur(8px)",
                }}>
                {SCENE_LABELS[s]}
              </button>
            ))}
          </div>
          {/* Eye care + stretch buttons */}
          <div className="flex gap-2">
            <button onClick={() => setEyeCare(e => !e)}
              className="px-3 py-1.5 rounded-xl flex items-center gap-1.5 transition-all"
              style={{
                fontFamily: "'DM Mono', monospace", fontSize: "0.6rem", letterSpacing: "0.06em",
                background: eyeCare ? "rgba(220,190,140,0.35)" : "rgba(0,0,0,0.25)",
                color: eyeCare ? "#F5D9A0" : "rgba(255,255,255,0.5)",
                border: `1px solid ${eyeCare ? "rgba(220,190,140,0.4)" : "rgba(255,255,255,0.08)"}`,
                backdropFilter: "blur(8px)",
              }}>
              👁 {eyeCare ? "Eye Care ON" : "Eye Care"}
            </button>
            <button onClick={() => setShowStretch(true)}
              className="px-3 py-1.5 rounded-xl transition-all"
              style={{
                fontFamily: "'DM Mono', monospace", fontSize: "0.6rem", letterSpacing: "0.06em",
                background: "rgba(0,0,0,0.25)", color: "rgba(255,255,255,0.5)",
                border: "1px solid rgba(255,255,255,0.08)", backdropFilter: "blur(8px)",
              }}>
              🧘 Stretch Lock
            </button>
          </div>
        </div>

        {/* Breathing circle overlay */}
        <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", zIndex: 2, pointerEvents: "none" }}>
          <div style={{
            width: 120, height: 120, borderRadius: "50%",
            background: `radial-gradient(circle, ${patColor}28 0%, ${patColor}08 60%, transparent 100%)`,
            border: `2px solid ${patColor}55`,
            display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
            transform: `scale(${circleScale})`,
            transition: `transform ${curPhase?.d ?? 4}s ease-in-out`,
            boxShadow: breathing ? `0 0 40px ${patColor}44, 0 0 80px ${patColor}22` : "none",
          }}>
            <div style={{ fontFamily: "'Lora', serif", fontSize: "0.85rem", color: "#fff", opacity: 0.9 }}>
              {breathing ? curPhase.n : "·"}
            </div>
            {breathing && (
              <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "1.1rem", color: patColor, letterSpacing: "0.04em" }}>
                {phaseSeconds}
              </div>
            )}
          </div>
          {!breathing && (
            <div style={{ marginTop: 16, fontFamily: "'DM Mono', monospace", fontSize: "0.62rem", color: "rgba(255,255,255,0.35)", letterSpacing: "0.1em", textTransform: "uppercase" }}>
              Press Breathe to begin
            </div>
          )}
        </div>

        {/* Bottom canvas labels */}
        <div style={{ position: "absolute", bottom: 14, left: 0, right: 0, display: "flex", justifyContent: "center", zIndex: 2 }}>
          <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.6rem", color: "rgba(255,255,255,0.3)", letterSpacing: "0.08em" }}>
            {totalBreaths.toLocaleString()} collective breaths
          </div>
        </div>
      </div>

      {/* ── Tab Bar ─────────────────────────────────────────────────────── */}
      <div className="flex gap-0.5 px-6 pt-4 shrink-0">
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className="px-4 py-2 rounded-xl transition-all duration-200"
            style={{
              fontFamily: "'DM Sans', sans-serif", fontSize: "0.78rem",
              background: tab === t.id ? "var(--muted)" : "transparent",
              color: tab === t.id ? "var(--foreground)" : "var(--muted-foreground)",
              borderBottom: `2px solid ${tab === t.id ? "var(--primary)" : "transparent"}`,
              borderRadius: tab === t.id ? "10px 10px 0 0" : 10,
            }}>
            {t.label}
          </button>
        ))}
      </div>

      {/* ── Tab Content ─────────────────────────────────────────────────── */}
      <div className="flex-1 min-h-0 overflow-y-auto px-6 pb-6 pt-4" style={{ scrollbarWidth: "none" }}>

        {/* ── BREATHE TAB ── */}
        {tab === "breathe" && (
          <div className="flex flex-col gap-4">
            {/* Pattern selector */}
            <div className="grid grid-cols-3 gap-3">
              {(Object.keys(PATTERNS) as PatternKey[]).map(pk => {
                const p = PATTERNS[pk];
                const active = pattern === pk;
                return (
                  <button key={pk} onClick={() => { setPattern(pk); stopBreathing(); }}
                    className="rounded-2xl px-4 py-4 text-left transition-all duration-200"
                    style={{
                      background: active ? `${p.color}18` : "var(--card)",
                      border: `1.5px solid ${active ? p.color + "55" : "var(--border)"}`,
                      boxShadow: active ? `0 4px 20px ${p.color}22` : "0 2px 8px rgba(45,49,46,0.04)",
                    }}>
                    <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.62rem", color: p.color, letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 4 }}>
                      {p.tag}
                    </div>
                    <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.82rem", color: "#2D312E", marginBottom: 4 }}>{p.label}</div>
                    <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.68rem", color: "#7D8579", lineHeight: 1.5 }}>{p.desc}</div>
                    {/* Phase timeline */}
                    <div className="flex gap-1 mt-3">
                      {p.phases.map((ph, i) => (
                        <div key={i} style={{ flex: ph.d, height: 3, borderRadius: 2, background: active && breathing && phaseIdx === i ? p.color : `${p.color}44` }} />
                      ))}
                    </div>
                    <div className="flex gap-1 mt-1">
                      {p.phases.map((ph, i) => (
                        <div key={i} style={{ flex: ph.d, fontFamily: "'DM Mono', monospace", fontSize: "0.52rem", color: active && breathing && phaseIdx === i ? p.color : "#B5B0A8" }}>
                          {ph.d}s
                        </div>
                      ))}
                    </div>
                  </button>
                );
              })}
            </div>

            {/* Begin / Pause button */}
            <button
              onClick={breathing ? stopBreathing : startBreathing}
              className="w-full py-4 rounded-2xl transition-all duration-300"
              style={{
                fontFamily: "'Lora', serif", fontSize: "1.05rem", fontStyle: "italic",
                background: breathing ? "var(--muted)" : patColor,
                color: breathing ? "var(--foreground)" : "#FDFCF9",
                boxShadow: breathing ? "none" : `0 8px 24px ${patColor}44`,
              }}>
              {breathing ? "Pause Breathing" : `Begin ${PATTERNS[pattern].label}`}
            </button>

            {breathing && (
              <div className="flex justify-between items-center px-1">
                {phases.map((ph, i) => (
                  <div key={i} className="flex flex-col items-center gap-1">
                    <div style={{ width: 8, height: 8, borderRadius: "50%", background: i === phaseIdx ? patColor : "#EDE8DF", transition: "background 0.5s ease" }} />
                    <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.58rem", color: i === phaseIdx ? patColor : "#B5B0A8" }}>{ph.n}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ── SOUNDS TAB ── */}
        {tab === "sounds" && (
          <div className="flex flex-col gap-4">
            <div className="grid grid-cols-2 gap-3">
              {[
                { id: "drone",  label: "Alpha Drone",  desc: "Harmonic chord meditation", emoji: "🎵", builder: buildAlphaDrone },
                { id: "rain",   label: "Forest Rain",  desc: "Filtered white noise rain",  emoji: "🌧",  builder: buildForestRain  },
                { id: "chimes", label: "Wind Chimes",  desc: "Random zen bell tones",      emoji: "🎐", builder: buildWindChimes  },
              ].map(({ id, label, desc, emoji, builder }) => {
                const on = activeSounds.has(id);
                return (
                  <button key={id} onClick={() => toggleSound(id, builder)}
                    className="rounded-2xl px-5 py-4 text-left transition-all duration-200 flex items-start gap-3"
                    style={{
                      background: on ? "var(--muted)" : "var(--card)",
                      border: `1.5px solid ${on ? "#8FA08D55" : "rgba(45,49,46,0.1)"}`,
                      boxShadow: on ? "0 4px 20px rgba(143,160,141,0.12)" : "0 2px 8px rgba(45,49,46,0.04)",
                    }}>
                    <div style={{ width: 36, height: 36, borderRadius: 10, background: on ? "#E4EDE3" : "#EDE8DF", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, fontSize: 17 }}>
                      {emoji}
                    </div>
                    <div>
                      <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.82rem", color: "#2D312E", marginBottom: 2 }}>{label}</div>
                      <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.68rem", color: "#7D8579" }}>{desc}</div>
                      {on && (
                        <div className="flex items-center gap-1 mt-2">
                          {[0, 1, 2, 3, 4].map(b => (
                            <div key={b} style={{ width: 2, height: 6 + Math.sin(b * 1.3) * 4, borderRadius: 1, background: "#8FA08D", animation: "none", opacity: 0.5 + b * 0.1 }} />
                          ))}
                          <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.58rem", color: "#8FA08D", marginLeft: 4 }}>playing</span>
                        </div>
                      )}
                    </div>
                  </button>
                );
              })}

              {/* Singing Bowl */}
              <button onClick={handleStrikeBowl}
                className="rounded-2xl px-5 py-4 text-left transition-all duration-200 flex items-start gap-3"
                style={{
                  background: bowlRinging ? "rgba(197,168,130,0.12)" : "var(--card)",
                  border: `1.5px solid ${bowlRinging ? "#C5A88255" : "var(--border)"}`,
                  boxShadow: bowlRinging ? "0 4px 20px rgba(197,168,130,0.15)" : "0 2px 8px rgba(45,49,46,0.04)",
                }}>
                <div style={{ width: 36, height: 36, borderRadius: 10, background: bowlRinging ? "#F5EFE5" : "#EDE8DF", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, fontSize: 17 }}>
                  🥣
                </div>
                <div>
                  <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.82rem", color: "#2D312E", marginBottom: 2 }}>Singing Bowl</div>
                  <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.68rem", color: "#7D8579" }}>Strike for 432 Hz bell tone</div>
                  {bowlRinging && <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.58rem", color: "#C5A882", marginTop: 4 }}>ringing…</div>}
                </div>
              </button>
            </div>

            {/* Master Volume */}
            <div className="rounded-2xl bg-card border border-border px-5 py-4">
              <div className="flex justify-between mb-3">
                <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.75rem", color: "#7D8579" }}>Master Volume</span>
                <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.72rem", color: "#8FA08D" }}>{Math.round(masterVol * 100)}%</span>
              </div>
              <input type="range" min={0} max={1} step={0.01} value={masterVol}
                onChange={e => handleVolumeChange(Number(e.target.value))}
                className="w-full h-1.5 rounded-full appearance-none outline-none cursor-pointer"
                style={{ accentColor: "#8FA08D", background: `linear-gradient(to right, #8FA08D ${masterVol * 100}%, #EDE8DF ${masterVol * 100}%)` }}
              />
              <div className="flex justify-between mt-2">
                <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.58rem", color: "#B5B0A8" }}>Quiet</span>
                <button onClick={() => handleVolumeChange(0)} style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.58rem", color: activeSounds.size ? "#C17B6B" : "#B5B0A8", background: "none", border: "none", cursor: "pointer" }}>
                  {activeSounds.size > 0 ? "Mute all" : ""}
                </button>
                <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.58rem", color: "#B5B0A8" }}>Full</span>
              </div>
            </div>
          </div>
        )}

        {/* ── GROUNDING TAB ── */}
        {tab === "ground" && (
          <div className="flex flex-col gap-4">
            <div className="rounded-2xl px-5 py-4" style={{ background: "#F0EDE6", border: "1px solid rgba(45,49,46,0.08)" }}>
              <div style={{ fontFamily: "'Lora', serif", fontSize: "0.88rem", color: "#2D312E", lineHeight: 1.6, fontStyle: "italic" }}>
                "{DAILY_PROMPTS[promptIdx]}"
              </div>
            </div>

            <div className="flex flex-col gap-2">
              {GROUNDING.map((g, i) => {
                const active = groundStep === i;
                const done = groundDone.has(i);
                return (
                  <button key={g.sense}
                    onClick={() => {
                      setGroundStep(i);
                      setGroundDone(prev => new Set([...prev, i]));
                    }}
                    className="flex items-start gap-4 px-4 py-4 rounded-2xl text-left transition-all duration-200"
                    style={{
                      background: active ? `${g.color}14` : done ? `${g.color}08` : "var(--card)",
                      border: `1.5px solid ${active ? g.color + "44" : done ? g.color + "22" : "var(--border)"}`,
                    }}>
                    <div style={{
                      width: 40, height: 40, borderRadius: "50%",
                      background: active ? g.color : done ? `${g.color}44` : "#EDE8DF",
                      display: "flex", alignItems: "center", justifyContent: "center",
                      flexShrink: 0, fontSize: 18, transition: "background 0.3s ease",
                    }}>
                      {done && !active ? "✓" : g.icon}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span style={{
                          width: 20, height: 20, borderRadius: "50%", flexShrink: 0,
                          background: active ? g.color : "#EDE8DF",
                          color: active ? "#FDFCF9" : "#7D8579",
                          display: "inline-flex", alignItems: "center", justifyContent: "center",
                          fontFamily: "'DM Mono', monospace", fontSize: "0.65rem",
                        }}>{g.n}</span>
                        <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.88rem", color: "#2D312E" }}>Things You Can {g.sense}</span>
                      </div>
                      <div style={{
                        fontFamily: "'DM Sans', sans-serif", fontSize: "0.75rem", color: "#7D8579",
                        lineHeight: 1.6, maxHeight: active ? 80 : 0, overflow: "hidden",
                        transition: "max-height 0.3s ease",
                      }}>
                        {g.prompt}
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>

            {groundDone.size === 5 && (
              <div className="rounded-2xl px-5 py-4 flex items-center gap-3" style={{ background: "#E4EDE3", border: "1px solid #8FA08D44" }}>
                <span style={{ fontSize: 20 }}>✦</span>
                <div>
                  <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.82rem", color: "#2D312E" }}>Grounding complete</div>
                  <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.72rem", color: "#7D8579" }}>Your nervous system is anchored. Well done.</div>
                </div>
                <button onClick={() => { setGroundStep(-1); setGroundDone(new Set()); }} style={{ marginLeft: "auto", fontFamily: "'DM Mono', monospace", fontSize: "0.6rem", color: "#8FA08D", background: "none", border: "none", cursor: "pointer" }}>
                  Reset
                </button>
              </div>
            )}
          </div>
        )}

        {/* ── COMMUNITY TAB ── */}
        {tab === "community" && (
          <div className="flex flex-col gap-4">
            <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.75rem", color: "#7D8579", lineHeight: 1.6 }}>
              Breathe alongside others in a shared virtual space. Your participation adds to the collective.
            </div>

            {CIRCLES.map(circle => {
              const isJoined = joined === circle.id;
              const count = counts[circle.id];
              return (
                <div key={circle.id} className="rounded-2xl px-5 py-5" style={{ background: isJoined ? circle.bg : "var(--card)", border: `1.5px solid ${isJoined ? circle.color + "55" : "var(--border)"}`, boxShadow: isJoined ? `0 4px 20px ${circle.color}22` : "none", transition: "all 0.3s ease" }}>
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <span style={{ fontSize: 20 }}>{circle.emoji}</span>
                      <div>
                        <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.88rem", color: "#2D312E" }}>{circle.name}</div>
                        <div className="flex items-center gap-1.5">
                          <span style={{ width: 6, height: 6, borderRadius: "50%", background: circle.color, display: "inline-block", boxShadow: `0 0 6px ${circle.color}` }} />
                          <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.62rem", color: circle.color }}>{count} breathing now</span>
                        </div>
                      </div>
                    </div>
                    <button
                      onClick={() => setJoined(isJoined ? null : circle.id)}
                      className="px-4 py-2 rounded-xl transition-all duration-200"
                      style={{
                        fontFamily: "'DM Sans', sans-serif", fontSize: "0.78rem",
                        background: isJoined ? circle.color : "transparent",
                        color: isJoined ? "#FDFCF9" : circle.color,
                        border: `1px solid ${circle.color}55`,
                      }}>
                      {isJoined ? "Breathing Together" : "Join Circle"}
                    </button>
                  </div>

                  <div className="rounded-xl px-4 py-3 mb-3" style={{ background: "rgba(255,255,255,0.55)" }}>
                    <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.58rem", color: circle.color, letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 4 }}>
                      Today's Prompt
                    </div>
                    <div style={{ fontFamily: "'Lora', serif", fontSize: "0.85rem", color: "#2D312E", lineHeight: 1.6, fontStyle: "italic" }}>
                      "{circle.prompt}"
                    </div>
                  </div>

                  {/* Participant dots */}
                  <div className="flex items-center gap-1 flex-wrap">
                    {Array.from({ length: Math.min(count, 24) }).map((_, i) => (
                      <div key={i} style={{
                        width: 8, height: 8, borderRadius: "50%",
                        background: i < 3 ? circle.color : `${circle.color}55`,
                        boxShadow: i < 3 ? `0 0 6px ${circle.color}88` : "none",
                      }} />
                    ))}
                    {count > 24 && <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.58rem", color: "#B5B0A8" }}>+{count - 24}</span>}
                  </div>

                  {isJoined && (
                    <div className="mt-3 pt-3" style={{ borderTop: `1px solid ${circle.color}22` }}>
                      <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.65rem", color: circle.color, letterSpacing: "0.08em" }}>
                        You are breathing with this circle. {count} participants · Collective milestone: {(count * 1440).toLocaleString()} breaths today
                      </div>
                    </div>
                  )}
                </div>
              );
            })}

            {/* Milestone */}
            <div className="rounded-2xl px-5 py-4 flex items-center gap-3" style={{ background: "#F0EDE6", border: "1px solid rgba(45,49,46,0.08)" }}>
              <span style={{ fontSize: 20 }}>✦</span>
              <div>
                <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "0.82rem", color: "#2D312E" }}>Daily Collective</div>
                <div style={{ fontFamily: "'DM Mono', monospace", fontSize: "0.68rem", color: "#7D8579" }}>
                  {totalBreaths.toLocaleString()} breaths shared today across all circles
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── Stretch Modal ─────────────────────────────────────────────── */}
      {showStretch && <StretchModal onClose={() => setShowStretch(false)} />}
    </div>
  );
}
