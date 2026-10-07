/*
Conflict-Free Replicated Data Types (CvRDT) and Hybrid Logical Clock (HLC) Engine.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
*/

using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Linq;

namespace MindFlow.Core.Sync
{
    public readonly struct HLCTimestamp : IComparable<HLCTimestamp>, IEquatable<HLCTimestamp>
    {
        public long PhysicalTimeMs { get; }
        public int LogicalCounter { get; }
        public string ClientId { get; }

        public HLCTimestamp(long physicalTimeMs, int logicalCounter, string clientId)
        {
            PhysicalTimeMs = physicalTimeMs;
            LogicalCounter = logicalCounter;
            ClientId = clientId ?? string.Empty;
        }

        public int CompareTo(HLCTimestamp other)
        {
            int cmp = PhysicalTimeMs.CompareTo(other.PhysicalTimeMs);
            if (cmp != 0) return cmp;

            cmp = LogicalCounter.CompareTo(other.LogicalCounter);
            if (cmp != 0) return cmp;

            return string.Compare(ClientId, other.ClientId, StringComparison.Ordinal);
        }

        public bool Equals(HLCTimestamp other) =>
            PhysicalTimeMs == other.PhysicalTimeMs &&
            LogicalCounter == other.LogicalCounter &&
            ClientId == other.ClientId;

        public override bool Equals(object? obj) => obj is HLCTimestamp other && Equals(other);

        public override int GetHashCode() => HashCode.Combine(PhysicalTimeMs, LogicalCounter, ClientId);

        public override string ToString() => $"{PhysicalTimeMs}:{LogicalCounter:D4}:{ClientId}";
    }

    public class HybridLogicalClock
    {
        private readonly string _clientId;
        private long _latestPhysicalMs = 0;
        private int _counter = 0;
        private readonly object _lock = new();

        public HybridLogicalClock(string? clientId = null)
        {
            _clientId = clientId ?? Guid.NewGuid().ToString("N")[..8];
        }

        public HLCTimestamp Now()
        {
            lock (_lock)
            {
                long physicalNow = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
                if (physicalNow > _latestPhysicalMs)
                {
                    _latestPhysicalMs = physicalNow;
                    _counter = 0;
                }
                else
                {
                    _counter++;
                }

                return new HLCTimestamp(_latestPhysicalMs, _counter, _clientId);
            }
        }

        public HLCTimestamp Update(HLCTimestamp remote)
        {
            lock (_lock)
            {
                long physicalNow = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
                long maxPhysical = Math.Max(physicalNow, Math.Max(_latestPhysicalMs, remote.PhysicalTimeMs));

                if (maxPhysical == _latestPhysicalMs && maxPhysical == remote.PhysicalTimeMs)
                {
                    _counter = Math.Max(_counter, remote.LogicalCounter) + 1;
                }
                else if (maxPhysical == _latestPhysicalMs)
                {
                    _counter++;
                }
                else if (maxPhysical == remote.PhysicalTimeMs)
                {
                    _counter = remote.LogicalCounter + 1;
                }
                else
                {
                    _counter = 0;
                }

                _latestPhysicalMs = maxPhysical;
                return new HLCTimestamp(_latestPhysicalMs, _counter, _clientId);
            }
        }
    }

    public class LWWRegister<T>
    {
        public T Value { get; private set; }
        public HLCTimestamp Timestamp { get; private set; }

        public LWWRegister(T initialValue, HLCTimestamp initialTimestamp)
        {
            Value = initialValue;
            Timestamp = initialTimestamp;
        }

        public bool Set(T newValue, HLCTimestamp newTimestamp)
        {
            if (newTimestamp.CompareTo(Timestamp) > 0)
            {
                Value = newValue;
                Timestamp = newTimestamp;
                return true;
            }
            return false;
        }
    }

    public class PNCounter
    {
        private readonly ConcurrentDictionary<string, long> _positive = new();
        private readonly ConcurrentDictionary<string, long> _negative = new();

        public long Value => _positive.Values.Sum() - _negative.Values.Sum();

        public void Increment(string clientId, long amount = 1)
        {
            _positive.AddOrUpdate(clientId, amount, (_, v) => v + amount);
        }

        public void Decrement(string clientId, long amount = 1)
        {
            _negative.AddOrUpdate(clientId, amount, (_, v) => v + amount);
        }

        public void Merge(PNCounter other)
        {
            foreach (var kvp in other._positive)
            {
                _positive.AddOrUpdate(kvp.Key, kvp.Value, (_, v) => Math.Max(v, kvp.Value));
            }
            foreach (var kvp in other._negative)
            {
                _negative.AddOrUpdate(kvp.Key, kvp.Value, (_, v) => Math.Max(v, kvp.Value));
            }
        }
    }

    public class LWWElementSet<T> where T : notnull
    {
        private readonly ConcurrentDictionary<T, (T Element, HLCTimestamp Timestamp)> _addSet = new();
        private readonly ConcurrentDictionary<T, HLCTimestamp> _removeSet = new();
        private readonly object _lock = new();

        public void Add(T element, HLCTimestamp timestamp)
        {
            _addSet.AddOrUpdate(element,
                (element, timestamp),
                (_, current) => timestamp.CompareTo(current.Timestamp) > 0 ? (element, timestamp) : current);
        }

        public void Remove(T element, HLCTimestamp timestamp)
        {
            _removeSet.AddOrUpdate(element,
                timestamp,
                (_, current) => timestamp.CompareTo(current) > 0 ? timestamp : current);
        }

        public IReadOnlyCollection<T> ReadElements()
        {
            var result = new List<T>();
            foreach (var (element, addInfo) in _addSet)
            {
                if (!_removeSet.TryGetValue(element, out var removeTs) ||
                    addInfo.Timestamp.CompareTo(removeTs) > 0)
                {
                    result.Add(element);
                }
            }
            return result;
        }

        public void Merge(LWWElementSet<T> other)
        {
            lock (_lock)
            {
                foreach (var kvp in other._addSet)
                {
                    Add(kvp.Key, kvp.Value.Timestamp);
                }
                foreach (var kvp in other._removeSet)
                {
                    Remove(kvp.Key, kvp.Value);
                }
            }
        }

        public int GarbageCollectTombstones(long maxAgeMs = 86400000 /* 24 hours */)
        {
            lock (_lock)
            {
                long now = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
                int purged = 0;

                foreach (var kvp in _removeSet.ToArray())
                {
                    if (now - kvp.Value.PhysicalTimeMs >= maxAgeMs)
                    {
                        if (_removeSet.TryRemove(kvp.Key, out _))
                        {
                            _addSet.TryRemove(kvp.Key, out _);
                            purged++;
                        }
                    }
                }

                return purged;
            }
        }
    }

    public class CrdtSyncEngine
    {
        private readonly object _lock = new();

        public string ClientId { get; }
        public HybridLogicalClock Hlc { get; }
        public LWWRegister<double> StaminaBattery { get; }
        public LWWRegister<double> FatigueScore { get; }
        public LWWElementSet<string> CategoryRules { get; }
        public ConcurrentDictionary<string, PNCounter> Counters { get; }
        public LWWElementSet<string> SessionLogs { get; }

        public CrdtSyncEngine(string? clientId = null)
        {
            ClientId = clientId ?? Guid.NewGuid().ToString("N")[..8];
            Hlc = new HybridLogicalClock(ClientId);

            var now = Hlc.Now();
            StaminaBattery = new LWWRegister<double>(100.0, now);
            FatigueScore = new LWWRegister<double>(0.0, now);
            CategoryRules = new LWWElementSet<string>();
            Counters = new ConcurrentDictionary<string, PNCounter>();
            SessionLogs = new LWWElementSet<string>();
        }

        public void Merge(CrdtSyncEngine other)
        {
            lock (_lock)
            {
                Hlc.Update(other.Hlc.Now());

                if (other.StaminaBattery.Timestamp.CompareTo(StaminaBattery.Timestamp) > 0)
                {
                    StaminaBattery.Set(other.StaminaBattery.Value, other.StaminaBattery.Timestamp);
                }

                if (other.FatigueScore.Timestamp.CompareTo(FatigueScore.Timestamp) > 0)
                {
                    FatigueScore.Set(other.FatigueScore.Value, other.FatigueScore.Timestamp);
                }

                CategoryRules.Merge(other.CategoryRules);
                SessionLogs.Merge(other.SessionLogs);

                foreach (var kvp in other.Counters)
                {
                    var counter = Counters.GetOrAdd(kvp.Key, _ => new PNCounter());
                    counter.Merge(kvp.Value);
                }

                GarbageCollectTombstones();
            }
        }

        public int GarbageCollectTombstones(long maxAgeMs = 86400000)
        {
            lock (_lock)
            {
                int c1 = CategoryRules.GarbageCollectTombstones(maxAgeMs);
                int c2 = SessionLogs.GarbageCollectTombstones(maxAgeMs);
                return c1 + c2;
            }
        }
    }
}

