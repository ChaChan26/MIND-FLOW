/*
Companion messaging and cognitive forecast service for MIND-FLOW.
Generates dynamic CBT mental health interventions and battery depletion/recharge forecasts.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
*/

using System;

namespace MindFlow.Core.Companion
{
    public static class CompanionService
    {
        public static string GenerateCompanionMessage(
            bool trackingActive,
            int todayBypasses,
            bool highStressAlert,
            string? latestMood,
            double currentEnergy,
            string curMode,
            bool isLegacyScale = false)
        {
            if (isLegacyScale)
            {
                currentEnergy = Math.Clamp(currentEnergy * 20.0, 0.0, 100.0);
            }

            if (!trackingActive)
            {
                return "Companion is paused. Take care of yourself out there!";
            }

            if (todayBypasses > 1)
            {
                return $"🚨 That's {todayBypasses} breaks skipped today! Your health comes first: Rest more, step away from the keyboard, and take a physical break.";
            }

            if (todayBypasses == 1)
            {
                return "⚠️ I noticed you skipped a break earlier. Rest more during the next cycle: stretch your arms and rest your eyes.";
            }

            if (highStressAlert)
            {
                return "🚨 Persistent high stress detected! MIND-FLOW has scheduled a deep recovery break. Step away, close your eyes, and take a long rest.";
            }

            if (!string.IsNullOrWhiteSpace(latestMood))
            {
                string moodLower = latestMood.ToLowerInvariant().Trim();
                switch (moodLower)
                {
                    case "anxious":
                        return "😟 Anxious mood logged. Breathe slowly. Remember, your worth is not defined by today's output.";
                    case "overwhelmed":
                        return "🤯 Feeling overwhelmed? Focus on a single micro-goal. You have the right to close your tabs and rest.";
                    case "frustrated":
                        return "😤 Frustration is just a signal to pause. A short walk or water break often unlocks the solution.";
                    case "exhausted":
                        return "😴 Exhaustion detected. Give yourself permission to log off early or start a rest block.";
                }
            }

            if (currentEnergy <= 40.0)
            {
                return "🔋 Battery critical! Focus blocks are blocked. Rest more, start your rest cycle, and let your mind drift in Zen Space.";
            }

            if (currentEnergy <= 60.0)
            {
                return "🌿 Medium energy. Rest more before you reach exhaustion. Pace yourself and take a deep, mindful breath.";
            }

            string modeLower = (curMode ?? string.Empty).ToLowerInvariant().Trim();
            return modeLower switch
            {
                "work" => "💻 Focus session active. Remember: to sustain this, plan to rest more during upcoming recharge blocks!",
                "recharge" => "🎮 Recharging active. Rest more by looking away from all screens, stretching, or drinking water.",
                "rest" => "💤 Rest block. Close your eyes, rest more, and follow the 20-20-20 rule to relax your eyes.",
                _ => "🌳 Energy optimal. Maintain your stamina by remembering to stretch, hydrate, and rest more periodically."
            };
        }

        public static string CalculateBatteryForecast(
            string curMode,
            double batteryCap,
            int adaptiveRestLimitSeconds,
            string baseAlertMessage = "")
        {
            string modeLower = (curMode ?? string.Empty).ToLowerInvariant().Trim();
            string baseForecast;

            if (modeLower == "work" && batteryCap > 0)
            {
                int minutesLeft = (int)(batteryCap / 0.5);
                baseForecast = $"Forecast: Battery will deplete in ~{minutesLeft} minutes of focus.";
            }
            else if (modeLower is "recharge" or "rest" && batteryCap < 100)
            {
                int minutesLeft = (int)((100.0 - batteryCap) / 2.5);
                baseForecast = $"Forecast: Fully charged battery expected in ~{minutesLeft} minutes.";
            }
            else if (batteryCap <= 0)
            {
                baseForecast = $"Warning: Cognitive stamina depleted. Recommend a rest cycle of {adaptiveRestLimitSeconds} seconds.";
            }
            else
            {
                baseForecast = "Forecast: Stamina optimal. Pace your sprints to sustain focus.";
            }

            return !string.IsNullOrWhiteSpace(baseAlertMessage)
                ? $"{baseForecast} {baseAlertMessage}".Trim()
                : baseForecast;
        }
    }
}
