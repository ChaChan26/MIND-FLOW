import os
import sys
import json
import shutil

class WorkspaceManager:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.profiles_dir = os.path.join(data_dir, "Workspace_Profiles")
        self.registry_path = os.path.join(self.profiles_dir, "swapped_files.json")
        self.manifest_path = os.path.join(self.profiles_dir, "workspace_recovery_manifest.json")
        self.desktop_dir = self.get_desktop_dir()
        
        # Ensure directories exist
        os.makedirs(self.profiles_dir, exist_ok=True)
        os.makedirs(os.path.join(self.profiles_dir, "Work"), exist_ok=True)
        os.makedirs(os.path.join(self.profiles_dir, "Recharge"), exist_ok=True)
        
        # Auto-recover any stranded files from a previous crash/reboot on startup
        self.recover_stranded_files()

    def get_desktop_dir(self):
        """Retrieve the desktop folder path securely, with registry fallback on Windows."""
        if sys.platform == "win32":
            try:
                import winreg
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders")
                path, _ = winreg.QueryValueEx(key, "Desktop")
                winreg.CloseKey(key)
                return os.path.expandvars(path)
            except Exception:
                pass
        return os.path.join(os.path.expanduser("~"), "Desktop")

    def detect_cloud_sync(self):
        """Check if the Desktop directory is backed up by a known cloud sync service."""
        path_lower = self.desktop_dir.lower()
        cloud_keywords = ["onedrive", "dropbox", "google drive", "google_drive", "icloud", "creative cloud", "box", "sync"]
        return any(kw in path_lower for kw in cloud_keywords)

    def _write_manifest(self, file_moves):
        """Write a manifest of pending file moves to disk for crash recovery."""
        try:
            with open(self.manifest_path, "w", encoding="utf-8") as f:
                json.dump(file_moves, f, indent=4)
        except Exception as e:
            print(f"[WorkspaceManager] Error writing recovery manifest: {e}")

    def _clear_manifest(self):
        """Remove the manifest after successful completion of moves."""
        if os.path.exists(self.manifest_path):
            try:
                os.remove(self.manifest_path)
            except Exception as e:
                print(f"[WorkspaceManager] Error clearing recovery manifest: {e}")

    def recover_stranded_files(self):
        """Read recovery manifest on startup and restore any stranded files."""
        if os.path.exists(self.manifest_path):
            print("[WorkspaceManager] Stranded recovery manifest found. Restoring files...")
            try:
                with open(self.manifest_path, "r", encoding="utf-8") as f:
                    file_moves = json.load(f)
                if isinstance(file_moves, list):
                    for move in file_moves:
                        src = move.get("src")
                        dst = move.get("dst")
                        if src and dst and os.path.exists(src):
                            try:
                                if os.path.exists(dst):
                                    if os.path.isdir(dst):
                                        shutil.rmtree(dst)
                                    else:
                                        os.remove(dst)
                                shutil.move(src, dst)
                                print(f"[WorkspaceManager] Recovered: {os.path.basename(src)} -> {dst}")
                            except Exception as e:
                                print(f"[WorkspaceManager] Error recovering file {src} to {dst}: {e}")
            except Exception as e:
                print(f"[WorkspaceManager] Error during recovery process: {e}")
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
        """Save the registry of currently swapped files to disk."""
        try:
            with open(self.registry_path, "w", encoding="utf-8") as f:
                json.dump(reg, f, indent=4)
        except Exception as e:
            print(f"[WorkspaceManager] Error saving swapped files registry: {e}")

    def sweep_back_all(self):
        """Clean up any swapped files currently on the Desktop and return them to their profiles."""
        if self.detect_cloud_sync():
            print("[WorkspaceManager] Warning: Cloud sync detected. Skipping physical sweep.")
            return

        reg = self._load_registry()
        for mode in ["work", "recharge"]:
            filenames = reg.get(mode, [])
            if filenames:
                profile_folder = os.path.join(self.profiles_dir, mode.capitalize())
                moves = []
                for fname in filenames:
                    desktop_file = os.path.join(self.desktop_dir, fname)
                    if os.path.exists(desktop_file):
                        moves.append({
                            "src": desktop_file,
                            "dst": os.path.join(profile_folder, fname)
                        })
                
                if moves:
                    self._write_manifest(moves)
                    for move in moves:
                        try:
                            src = move["src"]
                            dst = move["dst"]
                            if os.path.exists(dst):
                                if os.path.isdir(dst):
                                    shutil.rmtree(dst)
                                else:
                                    os.remove(dst)
                            shutil.move(src, dst)
                            print(f"[WorkspaceManager] Swept back: {os.path.basename(src)} -> {mode.capitalize()} profile")
                        except Exception as e:
                            print(f"[WorkspaceManager] Error sweeping back file {src}: {e}")
                    self._clear_manifest()
                reg[mode] = []
        self._save_registry(reg)

    def transition_workspace(self, from_mode, to_mode):
        """Move files between the desktop and profile directories when the mode changes."""
        if self.detect_cloud_sync():
            print("[WorkspaceManager] Warning: Cloud sync detected. Skipping physical workspace transition.")
            return

        # 1. Sweep back old mode files if transitioning out of work or recharge
        if from_mode in ["work", "recharge"]:
            reg = self._load_registry()
            filenames = reg.get(from_mode, [])
            if filenames:
                profile_folder = os.path.join(self.profiles_dir, from_mode.capitalize())
                moves = []
                for fname in filenames:
                    desktop_file = os.path.join(self.desktop_dir, fname)
                    if os.path.exists(desktop_file):
                        moves.append({
                            "src": desktop_file,
                            "dst": os.path.join(profile_folder, fname)
                        })
                
                if moves:
                    self._write_manifest(moves)
                    for move in moves:
                        try:
                            src = move["src"]
                            dst = move["dst"]
                            if os.path.exists(dst):
                                if os.path.isdir(dst):
                                    shutil.rmtree(dst)
                                else:
                                    os.remove(dst)
                            shutil.move(src, dst)
                            print(f"[WorkspaceManager] Swept back on transition: {os.path.basename(src)} -> {from_mode.capitalize()} profile")
                        except Exception as e:
                            print(f"[WorkspaceManager] Error sweeping back file {src}: {e}")
                    self._clear_manifest()
                reg[from_mode] = []
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
                src_path = os.path.join(profile_folder, fname)
                dest_path = os.path.join(self.desktop_dir, fname)
                moves.append({
                    "src": src_path,
                    "dst": dest_path
                })
            
            swapped = []
            if moves:
                self._write_manifest(moves)
                for move in moves:
                    try:
                        src = move["src"]
                        dst = move["dst"]
                        if os.path.exists(dst):
                            if os.path.isdir(dst):
                                shutil.rmtree(dst)
                            else:
                                os.remove(dst)
                        shutil.move(src, dst)
                        swapped.append(os.path.basename(src))
                        print(f"[WorkspaceManager] Swapped in: {os.path.basename(src)} -> Desktop")
                    except Exception as e:
                        print(f"[WorkspaceManager] Error swapping file {src} to Desktop: {e}")
                self._clear_manifest()

            if swapped:
                reg = self._load_registry()
                reg[to_mode] = swapped
                self._save_registry(reg)

    def emergency_restore_all(self):
        """Forcefully move ALL files in Workspace_Profiles/Work and Recharge back to the Desktop."""
        restored = []
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
                    src = os.path.join(profile_folder, fname)
                    dst = os.path.join(self.desktop_dir, fname)
                    try:
                        if os.path.exists(dst):
                            if os.path.isdir(dst):
                                shutil.rmtree(dst)
                            else:
                                os.remove(dst)
                        shutil.move(src, dst)
                        restored.append(fname)
                        print(f"[WorkspaceManager] Emergency Restored: {fname} -> Desktop")
                    except Exception as e:
                        print(f"[WorkspaceManager] Error emergency restoring {fname}: {e}")
        
        # Clear registry and manifest files to reset workspace status
        self._save_registry({"work": [], "recharge": []})
        self._clear_manifest()
        return restored
