/**
 * Onboarding walkthrough guide introducing cognitive stamina tracking and pacing.
 *
 * Author: ChaChan26 <minhharry2006@gmail.com>
 * Copyright (c) 2026 ChaChan26. All rights reserved.
 */

import { useState } from "react";
import { ShieldCheck, BatteryCharging, Leaf, ArrowRight } from "lucide-react";

interface OnboardingProps {
  onComplete: () => void;
}

export function Onboarding({ onComplete }: OnboardingProps) {
  const [step, setStep] = useState(0);

  const steps = [
    {
      title: "Welcome to MIND-FLOW",
      description: "Your digital sanctuary for cognitive productivity. We protect your mental energy from burnout.",
      Icon: Leaf,
      color: "var(--primary)"
    },
    {
      title: "The Shield & Battery",
      description: "The app silently tracks your active window to measure your mental fatigue. When you work, your battery drains. When you recharge, it recovers.",
      Icon: BatteryCharging,
      color: "var(--accent-4)"
    },
    {
      title: "Restorative Breaks",
      description: "When your mental battery runs low, the shield will gently prompt you to step away and take a restorative break. Let's begin.",
      Icon: ShieldCheck,
      color: "var(--secondary)"
    }
  ];

  const current = steps[step];
  const CurrentIcon = current.Icon;

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center p-6"
      style={{
        background: "var(--background)",
        fontFamily: "'Nunito', sans-serif"
      }}
    >
      <div 
        className="w-full max-w-md p-8 flex flex-col items-center text-center transition-all duration-500"
        style={{
          background: "var(--card)",
          borderRadius: "var(--radii-xl, 1.5rem)",
          boxShadow: "var(--shadow-lg, 0 8px 24px rgba(0,0,0,0.08))",
          border: "1px solid var(--border)"
        }}
      >
        <div 
          className="mb-8 w-24 h-24 flex items-center justify-center transition-all duration-500"
          style={{
            background: `${current.color}1A`, // 10% opacity
            borderRadius: "var(--radii-full, 9999px)",
            color: current.color
          }}
        >
          <CurrentIcon size={48} strokeWidth={1.5} />
        </div>

        <h1 
          className="text-2xl font-bold mb-4 transition-all duration-500"
          style={{ color: "var(--foreground)" }}
        >
          {current.title}
        </h1>
        
        <p 
          className="text-lg leading-relaxed mb-10 transition-all duration-500 min-h-[5rem]"
          style={{ color: "var(--muted-foreground)" }}
        >
          {current.description}
        </p>

        <div className="flex items-center gap-3 mb-8">
          {steps.map((_, i) => (
            <div 
              key={i}
              className="h-2 rounded-full transition-all duration-300"
              style={{
                width: i === step ? "2rem" : "0.5rem",
                background: i === step ? current.color : "var(--border)"
              }}
            />
          ))}
        </div>

        <button
          onClick={() => {
            if (step < steps.length - 1) setStep(step + 1);
            else onComplete();
          }}
          className="w-full py-4 flex items-center justify-center gap-2 text-lg font-bold transition-transform active:scale-95"
          style={{
            background: "var(--primary)",
            color: "var(--on-primary, white)",
            borderRadius: "var(--radii-full, 9999px)",
            border: "none",
            cursor: "pointer"
          }}
        >
          {step < steps.length - 1 ? "Next" : "Start MIND-FLOW"}
          <ArrowRight size={20} />
        </button>
      </div>
    </div>
  );
}
