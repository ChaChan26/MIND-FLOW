/*
Nudge domain models and parameters for behavioral interventions and flow preservation.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
*/

using System;
using System.Collections.Generic;

namespace MindFlow.Core.Nudges
{
    public enum NudgeSeverity
    {
        Info,
        Warning,
        Critical
    }

    public record NudgeAction(string Label, string Action, string Variant = "primary");

    public record NudgeNotification(
        string Id,
        NudgeSeverity Severity,
        string Title,
        string Message,
        string SoundType,
        IReadOnlyList<NudgeAction> Actions,
        DateTime CreatedAt);

    public class NudgeSettings
    {
        public string ProactivityLevel { get; set; } = "balanced"; // "strict", "balanced", "gentle", "disabled"
        public bool EnableDistractionNudges { get; set; } = true;
        public bool EnableThrashingNudges { get; set; } = true;
        public bool EnableEyeCareNudges { get; set; } = true;
        public bool EnableHydrationNudges { get; set; } = true;
    }
}
