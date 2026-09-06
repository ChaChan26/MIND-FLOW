"""
MIND-FLOW Workspace Manager
Module: backend/workspace_manager.py

Handles isolated workspace profile swapping (Work vs Recharge modes),
atomic file movements, backup retention, and cloud sync safety.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
"""

import os
import sys
import json
import shutil
import threading
import time

class WorkspaceManager:
    _lock = threading.RLock()
    
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.profiles_dir = os.path.join(data_dir, "Workspace_Profiles")
        self.registry_path = os.path.join(self.profiles_dir, "swapped_files.json")
        self.manifest_path = os.path.join(self.profiles_dir, "workspace_recovery_manifest.json")
        self.desktop_dir = self.get_desktop_dir()
        self.lock = WorkspaceManager._lock
        
        # Ensure directories exist
        os.makedirs(self.profiles_dir, exist_ok=True)
        os.makedirs(os.path.join(self.profiles_dir, "Work"), exist_ok=True)
        os.makedirs(os.path.join(self.profiles_dir, "Recharge"), exist_ok=True)
        
        self.is_cloud_sync = self.detect_cloud_sync()
        
        # Clean up old backups (older than 7 days)
        try:
            self.cleanup_old_backups(max_age_days=7)
        except Exception as e:
            print(f"[WorkspaceManager] Error running automated backup cleanup: {e}")

        # Auto-recover any stranded files from a previous crash/reboot on startup
        self.recover_stranded_files()

    def get_desktop_dir(self):
        """Retrieve the desktop folder path securely, with registry fallback on Windows."""
        if sys.platform == "win32":
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as key:
                    path, _ = winreg.QueryValueEx(key, "Desktop")
                    return os.path.expandvars(path)
            except Exception:
                pass
        return os.path.join(os.path.expanduser("~"), "Desktop")

    def detect_cloud_sync(self):
        """Check if the Desktop directory is backed up by a known cloud sync service."""
        path_parts = [p.strip().lower() for p in self.desktop_dir.replace("/", "\\").split("\\")]
        cloud_keywords = {"onedrive", "dropbox", "google drive", "google_drive", "icloud", "creative cloud"}
        for part in path_parts:
            if part in cloud_keywords:
                return True
            if "onedrive" in part or "google drive" in part or "google_drive" in part:
                return True
        return False

    def _write_manifest(self, file_moves):
        """Write a manifest of pending file moves to disk atomically for crash recovery."""
        temp_path = self.manifest_path + ".tmp"
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(file_moves, f, indent=4)
            os.replace(temp_path, self.manifest_path)
        except Exception as e:
            print(f"[WorkspaceManager] Error writing recovery manifest: {e}")
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

    def _clear_manifest(self):
        """Remove the manifest after successful completion of moves."""
        if os.path.exists(self.manifest_path):
            try:
                os.remove(self.manifest_path)
            except Exception as e:
                print(f"[WorkspaceManager] Error clearing recovery manifest: {e}")

    def _safe_path(self, parent_dir, filename):
        """Validate and resolve paths securely to prevent directory traversal."""
        if not filename or filename in (".", ".."):
            raise ValueError(f"Invalid filename: {filename}")
        if "/" in filename or "\\" in filename or ".." in filename:
            raise ValueError(f"Directory traversal attempt detected: {filename}")
        target_path = os.path.abspath(os.path.join(parent_dir, filename))
        parent_abs = os.path.abspath(parent_dir)
        norm_target = os.path.normcase(target_path)
        norm_parent = os.path.normcase(parent_abs)
        if not norm_target.startswith(norm_parent + os.sep) and norm_target != norm_parent:
            raise ValueError(f"Directory traversal attempt detected: {filename}")
        return target_path

    def _safe_move(self, src, dst):
        """Move src to dst safely. If dst exists, rename it to a backup first instead of deleting."""
        import uuid
        backup_path = None
        if os.path.exists(dst):
            timestamp = int(time.time() * 1000)
            u_id = uuid.uuid4().hex[:8]
            backup_path = f"{dst}.bak.{timestamp}_{u_id}"
            if os.path.exists(backup_path):
                try:
                    if os.path.isdir(backup_path):
                        shutil.rmtree(backup_path)
                    else:
                        os.remove(backup_path)
                except (PermissionError, OSError) as e:
                    print(f"[WorkspaceManager] Warning: error removing duplicate backup {backup_path}: {e}")
            try:
                os.rename(dst, backup_path)
                print(f"[WorkspaceManager] Backup created: {dst} -> {os.path.basename(backup_path)}")
            except (PermissionError, OSError) as e:
                print(f"[WorkspaceManager] Warning: failed to rename destination to backup {backup_path}: {e}")
                raise e
        try:
            shutil.move(src, dst)
        except (PermissionError, OSError) as e:
            print(f"[WorkspaceManager] Error moving file {src} to {dst}: {e}")
            # Rollback: restore backup to dst if backup exists and dst was vacated
            if backup_path and os.path.exists(backup_path) and not os.path.exists(dst):
                try:
                    os.rename(backup_path, dst)
                    print(f"[WorkspaceManager] Successfully rolled back backup: {os.path.basename(backup_path)} -> {dst}")
                except Exception as rollback_err:
                    print(f"[WorkspaceManager] Critical: Failed to rollback backup {backup_path} to {dst}: {rollback_err}")
            raise e

    def _execute_moves(self, moves, log_callback=None):
        """Execute a list of moves, writing and clearing manifest, tracking failures."""
        if not moves:
            return True, []
        self._write_manifest(moves)
        failed_moves = []
        successful_filenames = []
        for move in moves:
            src = move["src"]
            dst = move["dst"]
            try:
                self._safe_move(src, dst)
                successful_filenames.append(os.path.basename(src))
                if log_callback:
                    log_callback(move)
            except Exception as e:
                print(f"[WorkspaceManager] Error moving file {src} to {dst}: {e}")
                failed_moves.append(move)
        
        if failed_moves:
            self._write_manifest(failed_moves)
            return False, successful_filenames
        else:
            self._clear_manifest()
            return True, successful_filenames

    def recover_stranded_files(self):
        """Read recovery manifest on startup and restore any stranded files."""
        if self.is_cloud_sync:
            return
        with self.lock:
            if os.path.exists(self.manifest_path):
                print("[WorkspaceManager] Stranded recovery manifest found. Restoring files...")
                failed_moves = []
                try:
                    with open(self.manifest_path, "r", encoding="utf-8") as f:
                        file_moves = json.load(f)
                    if isinstance(file_moves, list):
                        for move in file_moves:
                            src = move.get("src")
                            dst = move.get("dst")
                            if src and dst and os.path.exists(src):
                                try:
                                    self._safe_move(src, dst)
                                    print(f"[WorkspaceManager] Recovered: {os.path.basename(src)} -> {dst}")
                                except Exception as e:
                                    print(f"[WorkspaceManager] Error recovering file {src} to {dst}: {e}")
                                    failed_moves.append(move)
                except Exception as e:
                    print(f"[WorkspaceManager] Error during recovery process: {e}")
                if failed_moves:
                    self._write_manifest(failed_moves)
                else:
                    self._clear_manifest()

    def _load_registry(self):
        """Load the registry of currently swapped files from disk."""
        if os.path.exists(self.registry_path):
            try:
                with open(self.registry_path, "r", encoding="utf-8") as f:
                    reg = json.load(f)
                    if isinstance(reg, dict):
                        return reg
            except Exception:
                pass
        return {"work": [], "recharge": []}

    def _save_registry(self, reg):
        """Save the registry of currently swapped files to disk atomically."""
        temp_path = self.registry_path + ".tmp"
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(reg, f, indent=4)
            os.replace(temp_path, self.registry_path)
        except Exception as e:
            print(f"[WorkspaceManager] Error saving swapped files registry: {e}")
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

    def sweep_back_all(self):
        """Clean up any swapped files currently on the Desktop and return them to their profiles."""
        with self.lock:
            if self.is_cloud_sync:
                print("[WorkspaceManager] Warning: Cloud sync detected. Skipping physical sweep.")
                return

            reg = self._load_registry()
            all_moves = []
            mode_by_file = {}
            files_to_prune = []
            
            for mode in ["work", "recharge"]:
                filenames = reg.get(mode, [])
                if filenames:
                    profile_folder = os.path.join(self.profiles_dir, mode.capitalize())
                    for fname in filenames:
                        try:
                            desktop_file = self._safe_path(self.desktop_dir, fname)
                            dst_file = self._safe_path(profile_folder, fname)
                            if os.path.exists(desktop_file):
                                all_moves.append({"src": desktop_file, "dst": dst_file})
                                mode_by_file[os.path.basename(desktop_file)] = mode
                            else:
                                files_to_prune.append((mode, fname))
                                print(f"[WorkspaceManager] Pruning missing file from registry: {fname} ({mode})")
                        except ValueError as e:
                            print(f"[WorkspaceManager] Path validation error during sweep: {e}")

            if all_moves:
                def log_cb(move):
                    fname = os.path.basename(move["src"])
                    m = mode_by_file.get(fname, "unknown")
                    print(f"[WorkspaceManager] Swept back: {fname} -> {m.capitalize()} profile")
                
                _, successful_files = self._execute_moves(all_moves, log_callback=log_cb)
                
                for fname in successful_files:
                    m = mode_by_file.get(fname)
                    if m and fname in reg[m]:
                        reg[m].remove(fname)
                        
            for mode, fname in files_to_prune:
                if fname in reg[mode]:
                    reg[mode].remove(fname)
            self._save_registry(reg)

    def transition_workspace(self, from_mode, to_mode):
        """Move files between the desktop and profile directories when the mode changes."""
        with self.lock:
            from_mode = from_mode.lower().strip() if from_mode else ""
            to_mode = to_mode.lower().strip() if to_mode else ""
            
            if self.is_cloud_sync:
                print("[WorkspaceManager] Warning: Cloud sync detected. Skipping physical workspace transition.")
                return

            # 1. Sweep back old mode files if transitioning out of work or recharge
            if from_mode in ["work", "recharge"]:
                reg = self._load_registry()
                filenames = reg.get(from_mode, [])
                if filenames:
                    profile_folder = os.path.join(self.profiles_dir, from_mode.capitalize())
                    moves = []
                    files_to_prune = []
                    for fname in filenames:
                        try:
                            desktop_file = self._safe_path(self.desktop_dir, fname)
                            dst_file = self._safe_path(profile_folder, fname)
                            if os.path.exists(desktop_file):
                                moves.append({"src": desktop_file, "dst": dst_file})
                            else:
                                files_to_prune.append(fname)
                                print(f"[WorkspaceManager] Pruning missing file from transition registry: {fname} ({from_mode})")
                        except ValueError as e:
                            print(f"[WorkspaceManager] Path validation error during transition sweep: {e}")
                    
                    if moves:
                        def log_cb_sweep(move):
                            print(f"[WorkspaceManager] Swept back on transition: {os.path.basename(move['src'])} -> {from_mode.capitalize()} profile")
                        _, successful_files = self._execute_moves(moves, log_callback=log_cb_sweep)
                        
                        for fname in successful_files:
                            if fname in reg[from_mode]:
                                reg[from_mode].remove(fname)
                                
                    for fname in files_to_prune:
                        if fname in reg[from_mode]:
                            reg[from_mode].remove(fname)
                    self._save_registry(reg)

            # 2. Swap in new mode files if transitioning into work or recharge
            if to_mode in ["work", "recharge"]:
                profile_folder = os.path.join(self.profiles_dir, to_mode.capitalize())
                try:
                    filenames = os.listdir(profile_folder)
                except Exception as e:
                    print(f"[WorkspaceManager] Error listing files in {to_mode.capitalize()} folder: {e}")
                    filenames = []

                moves = []
                for fname in filenames:
                    if fname.lower() in ["work_readme.txt", "recharge_readme.txt"]:
                        continue
                    try:
                        src_path = self._safe_path(profile_folder, fname)
                        dest_path = self._safe_path(self.desktop_dir, fname)
                        moves.append({"src": src_path, "dst": dest_path})
                    except ValueError as e:
                        print(f"[WorkspaceManager] Path validation error during transition swap-in: {e}")
                
                if moves:
                    def log_cb_swap(move):
                        print(f"[WorkspaceManager] Swapped in: {os.path.basename(move['src'])} -> Desktop")
                    _, successful_files = self._execute_moves(moves, log_callback=log_cb_swap)
                    
                    if successful_files:
                        reg = self._load_registry()
                        existing = set(reg.get(to_mode, []))
                        existing.update(successful_files)
                        reg[to_mode] = list(existing)
                        self._save_registry(reg)

    def emergency_restore_all(self):
        """Forcefully move ALL files in Workspace_Profiles/Work and Recharge back to the Desktop."""
        with self.lock:
            restored = []
            moves = []
            for mode in ["Work", "Recharge"]:
                profile_folder = os.path.join(self.profiles_dir, mode)
                if os.path.exists(profile_folder):
                    try:
                        filenames = os.listdir(profile_folder)
                    except Exception:
                        filenames = []
                    for fname in filenames:
                        if fname.lower() in ["work_readme.txt", "recharge_readme.txt"]:
                            continue
                        try:
                            src = self._safe_path(profile_folder, fname)
                            dst = self._safe_path(self.desktop_dir, fname)
                            moves.append({"src": src, "dst": dst})
                        except ValueError as e:
                            print(f"[WorkspaceManager] Path validation error during emergency restore: {e}")
            
            if moves:
                def log_cb(move):
                    print(f"[WorkspaceManager] Emergency Restored: {os.path.basename(move['src'])} -> Desktop")
                _, successful_files = self._execute_moves(moves, log_callback=log_cb)
                restored.extend(successful_files)
            
            # Clear registry and manifest files to reset workspace status
            self._save_registry({"work": [], "recharge": []})
            self._clear_manifest()
            return restored

    def sweep_back_all_async(self, timeout=5.0):
        """Execute sweep_back_all in a daemon thread to ensure non-blocking file moves.
        
        If timeout is specified (>0), joins the thread up to timeout seconds.
        """
        def _async_target():
            try:
                self.sweep_back_all()
            except Exception as e:
                print(f"[WorkspaceManager] Error during asynchronous sweep_back_all: {e}")

        thread = threading.Thread(target=_async_target, daemon=True, name="WorkspaceSweepThread")
        thread.start()
        if timeout is not None and timeout > 0:
            thread.join(timeout=timeout)
            if thread.is_alive():
                print(f"[WorkspaceManager] sweep_back_all_async timed out after {timeout}s; continuing in background.")
        return thread

    def cleanup_old_backups(self, max_age_days=7):
        """Inspect backup files and directories in Workspace_Profiles and remove those older than max_age_days.
        
        Returns the number of deleted backup items.
        """
        with self.lock:
            if not os.path.exists(self.profiles_dir):
                return 0

            now = time.time()
            max_age_seconds = float(max_age_days * 86400)
            deleted_count = 0

            for root, dirs, files in os.walk(self.profiles_dir, topdown=False):
                # Clean up backup files
                for fname in files:
                    if ".bak." in fname or fname.endswith(".bak"):
                        fpath = os.path.join(root, fname)
                        if self._is_backup_expired(fpath, fname, now, max_age_seconds):
                            try:
                                os.remove(fpath)
                                deleted_count += 1
                                print(f"[WorkspaceManager] Deleted old backup file: {fname}")
                            except Exception as e:
                                print(f"[WorkspaceManager] Error deleting backup file {fpath}: {e}")

                # Clean up backup directories
                for dname in list(dirs):
                    if ".bak." in dname or dname.endswith(".bak"):
                        dpath = os.path.join(root, dname)
                        if self._is_backup_expired(dpath, dname, now, max_age_seconds):
                            try:
                                shutil.rmtree(dpath)
                                dirs.remove(dname)
                                deleted_count += 1
                                print(f"[WorkspaceManager] Deleted old backup directory: {dname}")
                            except Exception as e:
                                print(f"[WorkspaceManager] Error deleting backup directory {dpath}: {e}")

            return deleted_count

    def _is_backup_expired(self, path, name, now, max_age_seconds):
        """Determine if a backup item exceeds the maximum allowed age."""
        backup_time = None
        if ".bak." in name:
            parts = name.rsplit(".bak.", 1)
            if len(parts) == 2 and parts[1].isdigit():
                try:
                    backup_time = float(parts[1])
                except ValueError:
                    pass

        if backup_time is None:
            try:
                backup_time = os.path.getmtime(path)
            except Exception:
                return False

        return (now - backup_time) > max_age_seconds


if __name__ == "__main__":
    import argparse
    from backend.database import get_default_data_dir

    parser = argparse.ArgumentParser(
        description="MIND-FLOW Workspace Manager CLI & Emergency Recovery Tool"
    )
    parser.add_argument(
        "--emergency-restore",
        action="store_true",
        help="Forcefully restore all files from Work and Recharge profiles back to Desktop"
    )
    parser.add_argument(
        "--cleanup-backups",
        action="store_true",
        help="Clean up backup files older than max-age-days (default: 7 days)"
    )
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=7,
        help="Maximum age in days for backup retention (default: 7)"
    )
    parser.add_argument(
        "--sweep-back",
        action="store_true",
        help="Sweep back swapped files from Desktop to profile folders"
    )

    args = parser.parse_args()

    data_dir = get_default_data_dir()
    mgr = WorkspaceManager(data_dir)

    if args.emergency_restore:
        print("[CLI] Executing Emergency Restore All...")
        restored = mgr.emergency_restore_all()
        print(f"[CLI] Emergency Restore Complete. {len(restored)} files restored to Desktop.")
    elif args.cleanup_backups:
        print(f"[CLI] Cleaning up backup files older than {args.max_age_days} days...")
        deleted = mgr.cleanup_old_backups(max_age_days=args.max_age_days)
        print(f"[CLI] Backup cleanup complete. Deleted {deleted} backup items.")
    elif args.sweep_back:
        print("[CLI] Sweeping back swapped files...")
        mgr.sweep_back_all()
        print("[CLI] Sweep back complete.")
    else:
        parser.print_help()

