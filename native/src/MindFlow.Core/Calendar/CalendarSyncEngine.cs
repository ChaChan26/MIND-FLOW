/*
Calendar synchronization engine providing RFC-5545 iCal parsing and SSRF mitigation.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
*/

using System;
using System.Collections.Generic;
using System.Globalization;
using System.Net;
using System.Net.Http;
using System.Net.Sockets;
using System.Threading.Tasks;

namespace MindFlow.Core.Calendar
{
    public record CalendarEvent(
        string Title,
        DateTime StartTime,
        DateTime EndTime,
        string Uid,
        string Description = "");

    public static class CalendarSyncEngine
    {
        private static readonly HttpClient _httpClient = new(new SocketsHttpHandler
        {
            ConnectTimeout = TimeSpan.FromSeconds(5)
        })
        {
            Timeout = TimeSpan.FromSeconds(10)
        };

        public static bool IsSafeUrl(string url)
        {
            if (string.IsNullOrWhiteSpace(url)) return false;

            if (!Uri.TryCreate(url, UriKind.Absolute, out var uri))
                return false;

            if (!uri.Scheme.Equals("http", StringComparison.OrdinalIgnoreCase) &&
                !uri.Scheme.Equals("https", StringComparison.OrdinalIgnoreCase))
            {
                return false;
            }

            string host = uri.Host.Trim('[', ']').ToLowerInvariant();
            if (host is "localhost" or "127.0.0.1" or "::1")
                return false;

            try
            {
                var addresses = Dns.GetHostAddresses(uri.Host);
                if (addresses.Length == 0) return false;

                foreach (var ip in addresses)
                {
                    if (IsPrivateOrReserved(ip))
                        return false;
                }

                return true;
            }
            catch
            {
                return false;
            }
        }

        public static bool IsPrivateOrReserved(IPAddress ip)
        {
            if (IPAddress.IsLoopback(ip)) return true;

            if (ip.AddressFamily == AddressFamily.InterNetwork)
            {
                byte[] bytes = ip.GetAddressBytes();

                // 10.0.0.0/8
                if (bytes[0] == 10) return true;

                // 172.16.0.0/12 (172.16.0.0 - 172.31.255.255)
                if (bytes[0] == 172 && bytes[1] >= 16 && bytes[1] <= 31) return true;

                // 192.168.0.0/16
                if (bytes[0] == 192 && bytes[1] == 168) return true;

                // 169.254.0.0/16 (Link-local & Cloud Metadata)
                if (bytes[0] == 169 && bytes[1] == 254) return true;

                // 0.0.0.0/8
                if (bytes[0] == 0) return true;

                // 127.0.0.0/8
                if (bytes[0] == 127) return true;

                // 224.0.0.0/4 (Multicast) or 240.0.0.0/4 (Reserved)
                if (bytes[0] >= 224) return true;
            }
            else if (ip.AddressFamily == AddressFamily.InterNetworkV6)
            {
                if (ip.IsIPv6LinkLocal || ip.IsIPv6Multicast || ip.IsIPv6SiteLocal)
                    return true;

                byte[] bytes = ip.GetAddressBytes();
                // Unique Local Addresses (fc00::/7)
                if ((bytes[0] & 0xFE) == 0xFC) return true;
            }

            return false;
        }

        public static List<CalendarEvent> ParseIcsContent(string icsText)
        {
            var events = new List<CalendarEvent>();
            if (string.IsNullOrWhiteSpace(icsText)) return events;

            var lines = icsText.Replace("\r\n", "\n").Split('\n');
            bool inEvent = false;

            string title = "Focus Block";
            string description = string.Empty;
            string uid = string.Empty;
            DateTime? start = null;
            DateTime? end = null;

            foreach (string rawLine in lines)
            {
                string line = rawLine.Trim();
                if (string.IsNullOrEmpty(line)) continue;

                if (line.Equals("BEGIN:VEVENT", StringComparison.OrdinalIgnoreCase))
                {
                    inEvent = true;
                    title = "Focus Block";
                    description = string.Empty;
                    uid = Guid.NewGuid().ToString("N");
                    start = null;
                    end = null;
                }
                else if (line.Equals("END:VEVENT", StringComparison.OrdinalIgnoreCase) && inEvent)
                {
                    inEvent = false;
                    DateTime finalStart = start ?? DateTime.UtcNow;
                    DateTime finalEnd = end ?? finalStart.AddHours(1);
                    events.Add(new CalendarEvent(title, finalStart, finalEnd, uid, description));
                }
                else if (inEvent)
                {
                    if (line.StartsWith("SUMMARY:", StringComparison.OrdinalIgnoreCase))
                    {
                        title = line[8..].Trim();
                    }
                    else if (line.StartsWith("DESCRIPTION:", StringComparison.OrdinalIgnoreCase))
                    {
                        description = line[12..].Trim();
                    }
                    else if (line.StartsWith("UID:", StringComparison.OrdinalIgnoreCase))
                    {
                        uid = line[4..].Trim();
                    }
                    else if (line.StartsWith("DTSTART", StringComparison.OrdinalIgnoreCase))
                    {
                        int colon = line.IndexOf(':');
                        if (colon >= 0)
                        {
                            start = ParseIcsDateTime(line[(colon + 1)..].Trim());
                        }
                    }
                    else if (line.StartsWith("DTEND", StringComparison.OrdinalIgnoreCase))
                    {
                        int colon = line.IndexOf(':');
                        if (colon >= 0)
                        {
                            end = ParseIcsDateTime(line[(colon + 1)..].Trim());
                        }
                    }
                }
            }

            return events;
        }

        public static DateTime? ParseIcsDateTime(string dateStr)
        {
            if (string.IsNullOrWhiteSpace(dateStr)) return null;

            string[] formats =
            {
                "yyyyMMdd'T'HHmmss'Z'",
                "yyyyMMdd'T'HHmmss",
                "yyyyMMdd"
            };

            foreach (var fmt in formats)
            {
                if (DateTime.TryParseExact(dateStr, fmt, CultureInfo.InvariantCulture,
                        DateTimeStyles.AdjustToUniversal | DateTimeStyles.AssumeUniversal, out var dt))
                {
                    return dt;
                }
            }

            if (DateTime.TryParse(dateStr, out var fallback))
                return fallback.ToUniversalTime();

            return null;
        }

        public static async Task<List<CalendarEvent>> FetchAndParseCalendarAsync(string icalUrl)
        {
            if (string.IsNullOrWhiteSpace(icalUrl))
                return new List<CalendarEvent>();

            if (!IsSafeUrl(icalUrl))
                throw new InvalidOperationException($"SSRF blocked: URL '{icalUrl}' is invalid or resolves to a private/loopback network.");

            string content = await _httpClient.GetStringAsync(icalUrl);
            return ParseIcsContent(content);
        }
    }
}
