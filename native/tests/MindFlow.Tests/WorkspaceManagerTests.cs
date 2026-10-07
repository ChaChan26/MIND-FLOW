/*
Unit tests validating WorkspaceManager profile swapping, path security, and backup retention.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
*/

using System;
using System.Collections.Generic;
using System.IO;
using System.Threading.Tasks;
using Xunit;
using MindFlow.Core.Workspace;

namespace MindFlow.Tests
{
    public class WorkspaceManagerTests : IDisposable
    {
        private readonly string _tempRoot;
        private readonly string _dataDir;
        private readonly string _desktopDir;

        public WorkspaceManagerTests()
        {
            _tempRoot = Path.Combine(Path.GetTempPath(), "MindFlow_WM_Tests_" + Guid.NewGuid().ToString("N"));
            _dataDir = Path.Combine(_tempRoot, "Data");
            _desktopDir = Path.Combine(_tempRoot, "Desktop");

            Directory.CreateDirectory(_dataDir);
            Directory.CreateDirectory(_desktopDir);
        }

        public void Dispose()
        {
            try
            {
                if (Directory.Exists(_tempRoot))
                {
                    Directory.Delete(_tempRoot, true);
                }
            }
            catch { }
        }

        [Fact]
        public void WorkspaceManager_Initialization_CreatesProfilesDirectories()
        {
            var mgr = new WorkspaceManager(_dataDir, _desktopDir);

            Assert.True(Directory.Exists(mgr.ProfilesDir));
            Assert.True(Directory.Exists(Path.Combine(mgr.ProfilesDir, "Work")));
            Assert.True(Directory.Exists(Path.Combine(mgr.ProfilesDir, "Recharge")));
        }

        [Fact]
        public void WorkspaceManager_SafePath_RejectsTraversalAttempts()
        {
            var mgr = new WorkspaceManager(_dataDir, _desktopDir);

            Assert.Throws<ArgumentException>(() => mgr.SafePath(_desktopDir, "../secret.txt"));
            Assert.Throws<ArgumentException>(() => mgr.SafePath(_desktopDir, "folder/sub.txt"));
            Assert.Throws<ArgumentException>(() => mgr.SafePath(_desktopDir, ".."));
            Assert.Throws<ArgumentException>(() => mgr.SafePath(_desktopDir, ""));

            string valid = mgr.SafePath(_desktopDir, "valid_shortcut.lnk");
            Assert.Equal(Path.Combine(_desktopDir, "valid_shortcut.lnk"), valid);
        }

        [Fact]
        public void WorkspaceManager_SafeMove_CreatesBackupOnCollision()
        {
            var mgr = new WorkspaceManager(_dataDir, _desktopDir);

            string src = Path.Combine(_dataDir, "file_src.txt");
            string dst = Path.Combine(_desktopDir, "file_dst.txt");

            File.WriteAllText(src, "New Content");
            File.WriteAllText(dst, "Original Content");

            mgr.SafeMove(src, dst);

            Assert.True(File.Exists(dst));
            Assert.Equal("New Content", File.ReadAllText(dst));

            // Check that a backup file was created
            string[] backups = Directory.GetFiles(_desktopDir, "file_dst.txt.bak.*");
            Assert.Single(backups);
            Assert.Equal("Original Content", File.ReadAllText(backups[0]));
        }

        [Fact]
        public void WorkspaceManager_Transition_SwapsFilesBetweenProfilesAndDesktop()
        {
            var mgr = new WorkspaceManager(_dataDir, _desktopDir);

            // Populate Work profile
            string workFile = Path.Combine(mgr.ProfilesDir, "Work", "project.sln");
            File.WriteAllText(workFile, "Solution Content");

            // Populate Recharge profile
            string rechargeFile = Path.Combine(mgr.ProfilesDir, "Recharge", "game.lnk");
            File.WriteAllText(rechargeFile, "Game Content");

            // Transition from neutral to Work
            mgr.TransitionWorkspace("", "work");

            Assert.True(File.Exists(Path.Combine(_desktopDir, "project.sln")));
            Assert.False(File.Exists(workFile));

            // Transition from Work to Recharge
            mgr.TransitionWorkspace("work", "recharge");

            Assert.False(File.Exists(Path.Combine(_desktopDir, "project.sln")));
            Assert.True(File.Exists(Path.Combine(mgr.ProfilesDir, "Work", "project.sln")));

            Assert.True(File.Exists(Path.Combine(_desktopDir, "game.lnk")));
            Assert.False(File.Exists(rechargeFile));
        }

        [Fact]
        public void WorkspaceManager_SweepBackAll_ReturnsFilesToProfile()
        {
            var mgr = new WorkspaceManager(_dataDir, _desktopDir);

            string workFile = Path.Combine(mgr.ProfilesDir, "Work", "work_app.lnk");
            File.WriteAllText(workFile, "Work App");

            mgr.TransitionWorkspace("", "work");
            Assert.True(File.Exists(Path.Combine(_desktopDir, "work_app.lnk")));

            // Sweep back all
            mgr.SweepBackAll();

            Assert.False(File.Exists(Path.Combine(_desktopDir, "work_app.lnk")));
            Assert.True(File.Exists(Path.Combine(mgr.ProfilesDir, "Work", "work_app.lnk")));

            var reg = mgr.LoadRegistry();
            Assert.Empty(reg["work"]);
        }

        [Fact]
        public async Task WorkspaceManager_SweepBackAllAsync_RunsNonBlocking()
        {
            var mgr = new WorkspaceManager(_dataDir, _desktopDir);

            string rechargeFile = Path.Combine(mgr.ProfilesDir, "Recharge", "stream.lnk");
            File.WriteAllText(rechargeFile, "Stream App");

            mgr.TransitionWorkspace("", "recharge");
            Assert.True(File.Exists(Path.Combine(_desktopDir, "stream.lnk")));

            await mgr.SweepBackAllAsync();

            Assert.False(File.Exists(Path.Combine(_desktopDir, "stream.lnk")));
            Assert.True(File.Exists(Path.Combine(mgr.ProfilesDir, "Recharge", "stream.lnk")));
        }

        [Fact]
        public void WorkspaceManager_EmergencyRestoreAll_RestoresAllFiles()
        {
            var mgr = new WorkspaceManager(_dataDir, _desktopDir);

            string workFile = Path.Combine(mgr.ProfilesDir, "Work", "doc.txt");
            string rechargeFile = Path.Combine(mgr.ProfilesDir, "Recharge", "music.mp3");
            File.WriteAllText(workFile, "Work Doc");
            File.WriteAllText(rechargeFile, "Music Track");

            var restored = mgr.EmergencyRestoreAll();

            Assert.Contains("doc.txt", restored);
            Assert.Contains("music.mp3", restored);
            Assert.True(File.Exists(Path.Combine(_desktopDir, "doc.txt")));
            Assert.True(File.Exists(Path.Combine(_desktopDir, "music.mp3")));
        }

        [Fact]
        public void WorkspaceManager_CleanupOldBackups_RemovesExpiredBackups()
        {
            var mgr = new WorkspaceManager(_dataDir, _desktopDir);

            string freshBackup = Path.Combine(mgr.ProfilesDir, "Work", "test.txt.bak.123_abc");
            string oldBackup = Path.Combine(mgr.ProfilesDir, "Work", "old.txt.bak.456_def");

            File.WriteAllText(freshBackup, "Fresh");
            File.WriteAllText(oldBackup, "Old");

            // Artificially age oldBackup to 10 days ago
            File.SetLastWriteTimeUtc(oldBackup, DateTime.UtcNow.AddDays(-10));

            int deleted = mgr.CleanupOldBackups(maxAgeDays: 7);

            Assert.Equal(1, deleted);
            Assert.True(File.Exists(freshBackup));
            Assert.False(File.Exists(oldBackup));
        }
    }
}
