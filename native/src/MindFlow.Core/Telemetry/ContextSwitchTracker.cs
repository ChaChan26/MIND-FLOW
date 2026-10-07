/*
Context switch tracker calculating rolling window switching friction and cognitive penalty.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
*/

using System;
using System.Collections.Generic;

namespace MindFlow.Core.Telemetry
{
    public enum SwitchFrictionLevel
    {
        Low,
        Moderate,
        High
    }

    public class ContextSwitchTracker
    {
        private readonly Queue<DateTime> _recentSwitches = new();
        private readonly TimeSpan _windowDuration = TimeSpan.FromMinutes(15);
        private readonly object _lock = new();

        public int TotalSwitchesToday { get; private set; } = 0;
        private DateTime _lastResetDate = DateTime.MinValue;

        public int SwitchesLast15Minutes
        {
            get
            {
                lock (_lock)
                {
                    PruneOldSwitches(DateTime.UtcNow);
                    return _recentSwitches.Count;
                }
            }
        }

        public IReadOnlyList<double> GetRecentSwitchEpochSeconds(DateTime? now = null)
        {
            DateTime current = now ?? DateTime.UtcNow;
            lock (_lock)
            {
                PruneOldSwitches(current);
                var list = new List<double>(_recentSwitches.Count);
                foreach (var dt in _recentSwitches)
                {
                    list.Add(new DateTimeOffset(dt).ToUnixTimeSeconds());
                }
                return list;
            }
        }

        public double SwitchesPerMinute
        {
            get
            {
                lock (_lock)
                {
                    PruneOldSwitches(DateTime.UtcNow);
                    return _recentSwitches.Count / 15.0;
                }
            }
        }

        public SwitchFrictionLevel FrictionLevel
        {
            get
            {
                double rate = SwitchesPerMinute;
                if (rate < 0.5) return SwitchFrictionLevel.Low;
                if (rate <= 1.5) return SwitchFrictionLevel.Moderate;
                return SwitchFrictionLevel.High;
            }
        }

        public string FrictionLevelFormatted => FrictionLevel switch
        {
            SwitchFrictionLevel.Low => "Low (Deep Focus)",
            SwitchFrictionLevel.Moderate => "Moderate (Active Multitasking)",
            SwitchFrictionLevel.High => "High (Fragmented Focus)",
            _ => "Unknown"
        };

        public bool RecordSwitch(string fromProcess, string toProcess, DateTime? timestamp = null)
        {
            if (string.IsNullOrWhiteSpace(fromProcess) ||
                string.IsNullOrWhiteSpace(toProcess) ||
                string.Equals(fromProcess, toProcess, StringComparison.OrdinalIgnoreCase))
            {
                return false;
            }

            DateTime time = timestamp ?? DateTime.UtcNow;

            lock (_lock)
            {
                if (_lastResetDate == DateTime.MinValue)
                {
                    _lastResetDate = time.Date;
                }
                else if (time.Date > _lastResetDate)
                {
                    _recentSwitches.Clear();
                    TotalSwitchesToday = 0;
                    _lastResetDate = time.Date;
                }

                PruneOldSwitches(time);
                _recentSwitches.Enqueue(time);
                TotalSwitchesToday++;
                return true;
            }
        }

        public void Reset(int totalToday = 0)
        {
            lock (_lock)
            {
                _recentSwitches.Clear();
                TotalSwitchesToday = Math.Max(0, totalToday);
                _lastResetDate = DateTime.UtcNow.Date;
            }
        }

        private void PruneOldSwitches(DateTime now)
        {
            DateTime cutoff = now - _windowDuration;
            while (_recentSwitches.Count > 0 && _recentSwitches.Peek() < cutoff)
            {
                _recentSwitches.Dequeue();
            }
        }
    }
}
