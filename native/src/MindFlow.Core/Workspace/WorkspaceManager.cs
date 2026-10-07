/*
Workspace Profile Manager handling isolated profile swapping (Work vs Recharge),
atomic file movements, crash recovery manifests, and automated backup retention.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
*/

using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Threading.Tasks;

namespace MindFlow.Core.Workspace
{
    public record FileMove(string Src, string Dst);

    public class WorkspaceManager
    {
        private static readonly object _globalLock = new();

        public string DataDir { get; }
        public string ProfilesDir { get; }
        public string RegistryPath { get; }
        public string ManifestPath { get; }
        public string DesktopDir { get; }
        public bool IsCloudSync { get; }

        public WorkspaceManager(string dataDir, string? desktopDir = null)
        {
            DataDir = dataDir ?? throw new ArgumentNullException(nameof(dataDir));
            ProfilesDir = Path.Combine(DataDir, "Workspace_Profiles");
            RegistryPath = Path.Combine(ProfilesDir, "swapped_files.json");
            ManifestPath = Path.Combine(ProfilesDir, "workspace_recovery_manifest.json");

            DesktopDir = string.IsNullOrWhiteSpace(desktopDir)
                ? Environment.GetFolderPath(Environment.SpecialFolder.Desktop)
                : desktopDir;

            Directory.CreateDirectory(ProfilesDir);
            Directory.CreateDirectory(Path.Combine(ProfilesDir, "Work"));
            Directory.CreateDirectory(Path.Combine(ProfilesDir, "Recharge"));

            IsCloudSync = DetectCloudSync(DesktopDir);

            try
            {
                CleanupOldBackups(maxAgeDays: 7);
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[WorkspaceManager] Error running automated backup cleanup: {ex.Message}");
            }

            RecoverStrandedFiles();
        }

        public static bool DetectCloudSync(string desktopDir)
        {
            if (string.IsNullOrWhiteSpace(desktopDir)) return false;

            string normalized = desktopDir.Replace('/', '\\').ToLowerInvariant();
            string[] cloudKeywords = { "onedrive", "dropbox", "google drive", "google_drive", "icloud", "creative cloud" };

            return cloudKeywords.Any(k => normalized.Contains(k));
        }

        public string SafePath(string parentDir, string filename)
        {
            if (string.IsNullOrWhiteSpace(filename) || filename == "." || filename == "..")
                throw new ArgumentException($"Invalid filename: {filename}", nameof(filename));

            if (filename.Contains('/') || filename.Contains('\\') || filename.Contains(".."))
                throw new ArgumentException($"Directory traversal attempt detected: {filename}", nameof(filename));

            string targetPath = Path.GetFullPath(Path.Combine(parentDir, filename));
            string parentAbs = Path.GetFullPath(parentDir);

            string normTarget = targetPath.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
            string normParent = parentAbs.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);

            if (!normTarget.StartsWith(normParent + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase) &&
                !normTarget.Equals(normParent, StringComparison.OrdinalIgnoreCase))
            {
                throw new ArgumentException($"Directory traversal attempt detected: {filename}", nameof(filename));
            }

            return targetPath;
        }

        public void SafeMove(string src, string dst)
        {
            string? backupPath = null;
            if (File.Exists(dst) || Directory.Exists(dst))
            {
                long timestamp = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
                string uid = Guid.NewGuid().ToString("N")[..8];
                backupPath = $"{dst}.bak.{timestamp}_{uid}";

                if (File.Exists(backupPath)) File.Delete(backupPath);
                else if (Directory.Exists(backupPath)) Directory.Delete(backupPath, true);

                if (Directory.Exists(dst)) Directory.Move(dst, backupPath);
                else File.Move(dst, backupPath);
            }

            try
            {
                string? destDir = Path.GetDirectoryName(dst);
                if (!string.IsNullOrEmpty(destDir)) Directory.CreateDirectory(destDir);

                if (Directory.Exists(src)) Directory.Move(src, dst);
                else File.Move(src, dst);
            }
            catch (Exception ex)
            {
                // Rollback if backup exists and dst is free
                if (!string.IsNullOrEmpty(backupPath) &&
                    (File.Exists(backupPath) || Directory.Exists(backupPath)) &&
                    !File.Exists(dst) && !Directory.Exists(dst))
                {
                    try
                    {
                        if (Directory.Exists(backupPath)) Directory.Move(backupPath, dst);
                        else File.Move(backupPath, dst);
                    }
                    catch { }
                }
                throw new IOException($"Failed to move '{src}' to '{dst}': {ex.Message}", ex);
            }
        }

        public (bool Success, List<string> SuccessfulFiles) ExecuteMoves(
            IReadOnlyList<FileMove> moves,
            Action<FileMove>? logCallback = null)
        {
            if (moves == null || moves.Count == 0)
                return (true, new List<string>());

            WriteManifest(moves);
            var failedMoves = new List<FileMove>();
            var successfulFiles = new List<string>();

            foreach (var move in moves)
            {
                try
                {
                    SafeMove(move.Src, move.Dst);
                    successfulFiles.Add(Path.GetFileName(move.Src));
                    logCallback?.Invoke(move);
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"[WorkspaceManager] Error moving file {move.Src} to {move.Dst}: {ex.Message}");
                    failedMoves.Add(move);
                }
            }

            if (failedMoves.Count > 0)
            {
                WriteManifest(failedMoves);
                return (false, successfulFiles);
            }

            ClearManifest();
            return (true, successfulFiles);
        }

        public void RecoverStrandedFiles()
        {
            if (IsCloudSync) return;

            lock (_globalLock)
            {
                if (!File.Exists(ManifestPath)) return;

                var failedMoves = new List<FileMove>();
                try
                {
                    string json = File.ReadAllText(ManifestPath);
                    var moves = JsonSerializer.Deserialize<List<FileMove>>(json);
                    if (moves != null)
                    {
                        string fullProfiles = Path.GetFullPath(ProfilesDir);
                        string fullDesktop = Path.GetFullPath(DesktopDir);
                        string fullData = Path.GetFullPath(DataDir);

                        foreach (var move in moves)
                        {
                            if (!string.IsNullOrWhiteSpace(move.Src) &&
                                !string.IsNullOrWhiteSpace(move.Dst) &&
                                (File.Exists(move.Src) || Directory.Exists(move.Src)))
                            {
                                string realSrc = Path.GetFullPath(move.Src);
                                string realDst = Path.GetFullPath(move.Dst);

                                bool srcSafe = IsSubdirectory(realSrc, fullProfiles) ||
                                               IsSubdirectory(realSrc, fullDesktop) ||
                                               IsSubdirectory(realSrc, fullData);

                                bool dstSafe = IsSubdirectory(realDst, fullProfiles) ||
                                               IsSubdirectory(realDst, fullDesktop) ||
                                               IsSubdirectory(realDst, fullData);

                                if (!srcSafe || !dstSafe)
                                {
                                    Console.WriteLine($"[WorkspaceManager] Security: Skipping unsafe manifest move: {move.Src} -> {move.Dst}");
                                    continue;
                                }

                                try
                                {
                                    SafeMove(move.Src, move.Dst);
                                }
                                catch
                                {
                                    failedMoves.Add(move);
                                }
                            }
                        }
                    }
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"[WorkspaceManager] Error during recovery process: {ex.Message}");
                }

                if (failedMoves.Count > 0)
                {
                    WriteManifest(failedMoves);
                }
                else
                {
                    ClearManifest();
                }
            }
        }

        public Dictionary<string, List<string>> LoadRegistry()
        {
            if (File.Exists(RegistryPath))
            {
                try
                {
                    string json = File.ReadAllText(RegistryPath);
                    var dict = JsonSerializer.Deserialize<Dictionary<string, List<string>>>(json);
                    if (dict != null)
                    {
                        if (!dict.ContainsKey("work")) dict["work"] = new List<string>();
                        if (!dict.ContainsKey("recharge")) dict["recharge"] = new List<string>();
                        return dict;
                    }
                }
                catch { }
            }

            return new Dictionary<string, List<string>>(StringComparer.OrdinalIgnoreCase)
            {
                ["work"] = new List<string>(),
                ["recharge"] = new List<string>()
            };
        }

        public void SaveRegistry(Dictionary<string, List<string>> reg)
        {
            string tmp = RegistryPath + ".tmp";
            try
            {
                string json = JsonSerializer.Serialize(reg, new JsonSerializerOptions { WriteIndented = true });
                File.WriteAllText(tmp, json);
                File.Move(tmp, RegistryPath, overwrite: true);
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[WorkspaceManager] Error saving swapped files registry: {ex.Message}");
                if (File.Exists(tmp))
                {
                    try { File.Delete(tmp); } catch { }
                }
            }
        }

        public void SweepBackAll()
        {
            lock (_globalLock)
            {
                if (IsCloudSync) return;

                var reg = LoadRegistry();
                var allMoves = new List<FileMove>();
                var modeByFile = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
                var filesToPrune = new List<(string Mode, string File)>();

                foreach (string mode in new[] { "work", "recharge" })
                {
                    if (!reg.TryGetValue(mode, out var filenames)) continue;

                    string profileFolder = Path.Combine(ProfilesDir, char.ToUpper(mode[0]) + mode[1..]);
                    foreach (string fname in filenames)
                    {
                        try
                        {
                            string desktopFile = SafePath(DesktopDir, fname);
                            string dstFile = SafePath(profileFolder, fname);

                            if (File.Exists(desktopFile) || Directory.Exists(desktopFile))
                            {
                                allMoves.Add(new FileMove(desktopFile, dstFile));
                                modeByFile[Path.GetFileName(desktopFile)] = mode;
                            }
                            else
                            {
                                filesToPrune.Add((mode, fname));
                            }
                        }
                        catch { }
                    }
                }

                if (allMoves.Count > 0)
                {
                    var (_, successful) = ExecuteMoves(allMoves);
                    foreach (string fname in successful)
                    {
                        if (modeByFile.TryGetValue(fname, out string? m) && reg.TryGetValue(m, out var list))
                        {
                            list.Remove(fname);
                        }
                    }
                }

                foreach (var (m, f) in filesToPrune)
                {
                    if (reg.TryGetValue(m, out var list)) list.Remove(f);
                }

                SaveRegistry(reg);
            }
        }

        public Task SweepBackAllAsync()
        {
            return Task.Run(() =>
            {
                try
                {
                    SweepBackAll();
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"[WorkspaceManager] Error in asynchronous sweep: {ex.Message}");
                }
            });
        }

        public void TransitionWorkspace(string? fromMode, string? toMode)
        {
            lock (_globalLock)
            {
                if (IsCloudSync) return;

                string cleanFrom = (fromMode ?? string.Empty).ToLowerInvariant().Trim();
                string cleanTo = (toMode ?? string.Empty).ToLowerInvariant().Trim();

                // 1. Sweep back previous profile files if fromMode was work or recharge
                if (cleanFrom is "work" or "recharge")
                {
                    var reg = LoadRegistry();
                    if (reg.TryGetValue(cleanFrom, out var filenames) && filenames.Count > 0)
                    {
                        string profileFolder = Path.Combine(ProfilesDir, char.ToUpper(cleanFrom[0]) + cleanFrom[1..]);
                        var moves = new List<FileMove>();
                        var filesToPrune = new List<string>();

                        foreach (string fname in filenames)
                        {
                            try
                            {
                                string desktopFile = SafePath(DesktopDir, fname);
                                string dstFile = SafePath(profileFolder, fname);

                                if (File.Exists(desktopFile) || Directory.Exists(desktopFile))
                                {
                                    moves.Add(new FileMove(desktopFile, dstFile));
                                }
                                else
                                {
                                    filesToPrune.Add(fname);
                                }
                            }
                            catch { }
                        }

                        if (moves.Count > 0)
                        {
                            var (_, successful) = ExecuteMoves(moves);
                            foreach (string fname in successful)
                            {
                                filenames.Remove(fname);
                            }
                        }

                        foreach (string fname in filesToPrune)
                        {
                            filenames.Remove(fname);
                        }

                        SaveRegistry(reg);
                    }
                }

                // 2. Swap in target profile files if toMode is work or recharge
                if (cleanTo is "work" or "recharge")
                {
                    string profileFolder = Path.Combine(ProfilesDir, char.ToUpper(cleanTo[0]) + cleanTo[1..]);
                    var moves = new List<FileMove>();

                    if (Directory.Exists(profileFolder))
                    {
                        foreach (string entry in Directory.GetFileSystemEntries(profileFolder))
                        {
                            string fname = Path.GetFileName(entry);
                            if (fname.Equals("work_readme.txt", StringComparison.OrdinalIgnoreCase) ||
                                fname.Equals("recharge_readme.txt", StringComparison.OrdinalIgnoreCase))
                            {
                                continue;
                            }

                            try
                            {
                                string srcPath = SafePath(profileFolder, fname);
                                string destPath = SafePath(DesktopDir, fname);
                                moves.Add(new FileMove(srcPath, destPath));
                            }
                            catch { }
                        }
                    }

                    if (moves.Count > 0)
                    {
                        var (_, successful) = ExecuteMoves(moves);
                        if (successful.Count > 0)
                        {
                            var reg = LoadRegistry();
                            if (!reg.ContainsKey(cleanTo)) reg[cleanTo] = new List<string>();

                            var set = new HashSet<string>(reg[cleanTo], StringComparer.OrdinalIgnoreCase);
                            foreach (string f in successful) set.Add(f);
                            reg[cleanTo] = set.ToList();

                            SaveRegistry(reg);
                        }
                    }
                }
            }
        }

        public List<string> EmergencyRestoreAll()
        {
            lock (_globalLock)
            {
                var restored = new List<string>();
                var moves = new List<FileMove>();

                foreach (string mode in new[] { "Work", "Recharge" })
                {
                    string profileFolder = Path.Combine(ProfilesDir, mode);
                    if (Directory.Exists(profileFolder))
                    {
                        foreach (string entry in Directory.GetFileSystemEntries(profileFolder))
                        {
                            string fname = Path.GetFileName(entry);
                            if (fname.Equals("work_readme.txt", StringComparison.OrdinalIgnoreCase) ||
                                fname.Equals("recharge_readme.txt", StringComparison.OrdinalIgnoreCase))
                            {
                                continue;
                            }

                            try
                            {
                                string src = SafePath(profileFolder, fname);
                                string dst = SafePath(DesktopDir, fname);
                                moves.Add(new FileMove(src, dst));
                            }
                            catch { }
                        }
                    }
                }

                if (moves.Count > 0)
                {
                    var (_, successful) = ExecuteMoves(moves);
                    restored.AddRange(successful);
                }

                SaveRegistry(new Dictionary<string, List<string>>
                {
                    ["work"] = new List<string>(),
                    ["recharge"] = new List<string>()
                });
                ClearManifest();
                return restored;
            }
        }

        public int CleanupOldBackups(int maxAgeDays = 7)
        {
            lock (_globalLock)
            {
                if (!Directory.Exists(ProfilesDir)) return 0;

                DateTime cutoff = DateTime.UtcNow.AddDays(-maxAgeDays);
                int deleted = 0;

                var dir = new DirectoryInfo(ProfilesDir);
                foreach (var file in dir.GetFiles("*", SearchOption.AllDirectories))
                {
                    if (file.Name.Contains(".bak.") || file.Name.EndsWith(".bak", StringComparison.OrdinalIgnoreCase))
                    {
                        if (file.LastWriteTimeUtc < cutoff)
                        {
                            try
                            {
                                file.Delete();
                                deleted++;
                            }
                            catch { }
                        }
                    }
                }

                return deleted;
            }
        }

        private void WriteManifest(IReadOnlyList<FileMove> moves)
        {
            string tmp = ManifestPath + ".tmp";
            try
            {
                string json = JsonSerializer.Serialize(moves, new JsonSerializerOptions { WriteIndented = true });
                File.WriteAllText(tmp, json);
                File.Move(tmp, ManifestPath, overwrite: true);
            }
            catch
            {
                if (File.Exists(tmp))
                {
                    try { File.Delete(tmp); } catch { }
                }
            }
        }

        private void ClearManifest()
        {
            if (File.Exists(ManifestPath))
            {
                try { File.Delete(ManifestPath); } catch { }
            }
        }

        private static bool IsSubdirectory(string candidatePath, string parentPath)
        {
            string c = candidatePath.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
            string p = parentPath.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);

            return c.StartsWith(p + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase) ||
                   c.Equals(p, StringComparison.OrdinalIgnoreCase);
        }
    }
}
