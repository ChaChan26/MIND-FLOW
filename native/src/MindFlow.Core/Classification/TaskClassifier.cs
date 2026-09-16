/*
3-Tier Hybrid Task Classifier with LRU caching, ReDoS-safe regex evaluation, and keyword matching.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
*/

using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Linq;
using System.Text.RegularExpressions;

namespace MindFlow.Core.Classification
{
    public class TaskClassifier
    {
        private readonly ConcurrentDictionary<string, ActivityMode> _lruCache = new();
        private const int MaxCacheSize = 1000;

        private readonly Regex _workPattern;
        private readonly Regex _rechargePattern;
        private readonly Regex _neutralPattern;

        private readonly ConcurrentDictionary<string, Regex?> _compiledRegexCache = new();
        private readonly List<(Regex Pattern, ActivityMode Mode)> _userRules = new();
        private readonly object _rulesLock = new();

        public TaskClassifier()
        {
            // Pre-compile unified keyword patterns for O(1) matching on hot path
            var workKeywords = new[]
            {
                "code", "visual studio", "cursor", "pycharm", "intellij", "terminal",
                "powershell", "cmd.exe", "github", "gitlab", "stackoverflow", "jira",
                "notion", "slack", "teams", "word", "excel", "docs.google", "sheets.google",
                "sublime", "neovim", "docker", "postman", "figma"
            };
            var rechargeKeywords = new[]
            {
                "youtube", "netflix", "spotify", "reddit", "twitter", "x.com", "twitch",
                "facebook", "instagram", "tiktok", "steam", "discord", "prime video", "disney"
            };
            var neutralKeywords = new[]
            {
                "explorer", "settings", "calculator", "taskmgr", "searchapp", "picker", "shellexperiencehost"
            };

            _workPattern = new Regex(
                string.Join("|", workKeywords.Select(Regex.Escape)),
                RegexOptions.IgnoreCase | RegexOptions.Compiled, TimeSpan.FromMilliseconds(50));
            _rechargePattern = new Regex(
                string.Join("|", rechargeKeywords.Select(Regex.Escape)),
                RegexOptions.IgnoreCase | RegexOptions.Compiled, TimeSpan.FromMilliseconds(50));
            _neutralPattern = new Regex(
                string.Join("|", neutralKeywords.Select(Regex.Escape)),
                RegexOptions.IgnoreCase | RegexOptions.Compiled, TimeSpan.FromMilliseconds(50));
        }

        public void AddCustomRule(string pattern, ActivityMode mode)
        {
            if (string.IsNullOrWhiteSpace(pattern) || !IsSafeRegex(pattern))
                return;

            try
            {
                var rx = new Regex(pattern, RegexOptions.IgnoreCase | RegexOptions.Compiled, TimeSpan.FromMilliseconds(50));
                lock (_rulesLock)
                {
                    _userRules.Add((rx, mode));
                    _lruCache.Clear();
                }
            }
            catch
            {
                // Unparseable pattern skipped
            }
        }

        public void ClearCustomRules()
        {
            lock (_rulesLock)
            {
                _userRules.Clear();
                _lruCache.Clear();
            }
        }

        public ActivityMode Classify(string processName, string windowTitle)
        {
            string cleanProcess = (processName ?? string.Empty).ToLowerInvariant().Trim();
            string cleanTitle = (windowTitle ?? string.Empty).ToLowerInvariant().Trim();
            string cacheKey = $"{cleanProcess}|{cleanTitle}";
            string combined = $"{cleanProcess} {cleanTitle}";

            // Tier 1: O(1) LRU Exact Cache
            if (_lruCache.TryGetValue(cacheKey, out var cachedMode))
                return cachedMode;

            // Tier 2A: Custom User Rules
            lock (_rulesLock)
            {
                foreach (var (pattern, mode) in _userRules)
                {
                    try
                    {
                        if (pattern.IsMatch(combined))
                        {
                            CacheResult(cacheKey, mode);
                            return mode;
                        }
                    }
                    catch (RegexMatchTimeoutException)
                    {
                        // Safe timeout fallback
                    }
                }
            }

            // Tier 2B: Compiled Neutral Regex
            try
            {
                if (_neutralPattern.IsMatch(combined))
                {
                    CacheResult(cacheKey, ActivityMode.Neutral);
                    return ActivityMode.Neutral;
                }
            }
            catch (RegexMatchTimeoutException) { }

            // Tier 2C: Compiled Recharge Regex
            try
            {
                if (_rechargePattern.IsMatch(combined))
                {
                    CacheResult(cacheKey, ActivityMode.Recharge);
                    return ActivityMode.Recharge;
                }
            }
            catch (RegexMatchTimeoutException) { }

            // Tier 2D: Compiled Work Regex
            try
            {
                if (_workPattern.IsMatch(combined))
                {
                    CacheResult(cacheKey, ActivityMode.Work);
                    return ActivityMode.Work;
                }
            }
            catch (RegexMatchTimeoutException) { }

            // Tier 3: Default fallback
            var defaultMode = ActivityMode.Neutral;
            CacheResult(cacheKey, defaultMode);
            return defaultMode;
        }

        private void CacheResult(string key, ActivityMode mode)
        {
            if (_lruCache.Count >= MaxCacheSize)
                _lruCache.Clear();

            _lruCache[key] = mode;
        }

        public static bool IsSafeRegex(string pattern)
        {
            if (string.IsNullOrWhiteSpace(pattern)) return false;
            // Prevent catastrophic backtracking patterns: nested quantifiers like (a+)+ or (x*)*
            var dangerousPatterns = new[]
            {
                @"\([^\)]*[\+\*]\)[\+\*]",
                @"\([^\)]*[\+\*]\{[0-9]+,\}\)[\+\*]",
                @"(\.\*){2,}",
                @"(\.\+){2,}"
            };

            return !dangerousPatterns.Any(p => Regex.IsMatch(pattern, p));
        }
    }
}
