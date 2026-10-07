/*
Database entity models matching existing MIND-FLOW schema.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
*/

using System;

namespace MindFlow.Data.Models
{
    public class BatteryStateRecord
    {
        public double Capacity { get; set; } = 100.0;
        public double ConsecutiveWorkMinutes { get; set; } = 0.0;
        public DateTime LastUpdated { get; set; } = DateTime.UtcNow;
    }

    public class SessionRecord
    {
        public long Id { get; set; }
        public string Mode { get; set; } = string.Empty;
        public string Start { get; set; } = string.Empty;
        public string End { get; set; } = string.Empty;
        public double Duration { get; set; }
        public string BrainDump { get; set; } = string.Empty;
        public int Bypassed { get; set; }
        public int IsFlow { get; set; }
        public double FlowDuration { get; set; }
    }

    public class AppUsageRecord
    {
        public string Date { get; set; } = string.Empty;
        public string Process { get; set; } = string.Empty;
        public string Title { get; set; } = string.Empty;
        public double Duration { get; set; }
    }

    public class ContextSwitchRecord
    {
        public long Id { get; set; }
        public string Timestamp { get; set; } = string.Empty;
        public string FromProcess { get; set; } = string.Empty;
        public string ToProcess { get; set; } = string.Empty;
    }

    public class HourlyProductivityRecord
    {
        public int Hour { get; set; }
        public double WorkMinutes { get; set; }
        public double RechargeMinutes { get; set; }
        public double FlowMinutes { get; set; }
    }

    public class FocusSessionRecord
    {
        public long Id { get; set; }
        public string Timestamp { get; set; } = string.Empty;
        public int DurationMinutes { get; set; }
        public string TaskLabel { get; set; } = "Focus Sprint";
        public int Completed { get; set; } = 1;
        public double StaminaStart { get; set; } = 100.0;
        public double StaminaEnd { get; set; } = 100.0;
    }

    public class DailyProductivityTrendRecord
    {
        public string Date { get; set; } = string.Empty;
        public double WorkMinutes { get; set; }
        public double RechargeMinutes { get; set; }
        public double RestMinutes { get; set; }
        public double FlowMinutes { get; set; }
    }

    public class CategoryBreakdownRecord
    {
        public double WorkSeconds { get; set; }
        public double RestSeconds { get; set; }
        public double RechargeSeconds { get; set; }
        public double NeutralSeconds { get; set; }
    }

    public class FatigueDurationAnalytics
    {
        public double TotalWorkSeconds { get; set; }
        public double TotalRestSeconds { get; set; }
        public double AvgDailyWorkSeconds { get; set; }
        public double LongestContinuousWorkSeconds { get; set; }
        public double FatigueRiskScore { get; set; }
        public List<double> HourlyDistribution { get; set; } = new();
        public int AnalysisPeriodDays { get; set; }
    }

    public class CalendarEventRecord
    {
        public long Id { get; set; }
        public string Title { get; set; } = string.Empty;
        public string StartTime { get; set; } = string.Empty;
        public string EndTime { get; set; } = string.Empty;
    }
}

