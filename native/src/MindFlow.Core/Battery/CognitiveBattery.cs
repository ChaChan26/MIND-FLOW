/*
Cognitive Battery Model with exponential fatigue penalty and context switch sensitivity.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
*/

using System;
using MindFlow.Core.Classification;

namespace MindFlow.Core.Battery
{
    public class CognitiveBattery
    {
        public double Capacity { get; private set; }
        public double ConsecutiveWorkMinutes { get; private set; }

        public double BaseDrainPerMinute { get; set; } = 0.5;
        public double FatigueMultiplier { get; set; } = 0.035;
        public double RestRecoveryPerMinute { get; set; } = 2.5;
        public double DecayRate { get; set; } = 3.0;

        public CognitiveBattery(double initialCapacity = 100.0, double initialConsecutiveWork = 0.0)
        {
            Capacity = Math.Clamp(initialCapacity, 0.0, 100.0);
            ConsecutiveWorkMinutes = Math.Max(0.0, initialConsecutiveWork);
        }

        public (double Capacity, double ConsecutiveWork) ProcessTick(
            ActivityMode mode,
            double elapsedMinutes,
            double contextSwitchesPerMin = 0.0)
        {
            if (elapsedMinutes <= 0)
                return (Capacity, ConsecutiveWorkMinutes);

            switch (mode)
            {
                case ActivityMode.Work:
                    ConsecutiveWorkMinutes += elapsedMinutes;
                    double penalty = 1.0 + (ConsecutiveWorkMinutes * FatigueMultiplier);
                    double switchPenalty = 1.0 + (0.15 * Math.Max(0.0, contextSwitchesPerMin));
                    double drain = BaseDrainPerMinute * penalty * switchPenalty * elapsedMinutes;
                    Capacity = Math.Max(0.0, Capacity - drain);
                    break;

                case ActivityMode.Neutral:
                    // Neutral mode: preserve capacity and consecutive work minutes without drain
                    break;

                case ActivityMode.Recharge:
                case ActivityMode.Rest:
                    ConsecutiveWorkMinutes = Math.Max(0.0, ConsecutiveWorkMinutes - (elapsedMinutes * DecayRate));
                    double recovery = RestRecoveryPerMinute * elapsedMinutes;
                    Capacity = Math.Min(100.0, Capacity + recovery);
                    break;
            }

            return (Capacity, ConsecutiveWorkMinutes);
        }

        public void Reset(double capacity = 100.0, double consecutiveWork = 0.0)
        {
            Capacity = Math.Clamp(capacity, 0.0, 100.0);
            ConsecutiveWorkMinutes = Math.Max(0.0, consecutiveWork);
        }
    }
}
