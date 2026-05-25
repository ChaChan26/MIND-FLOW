import os
import shutil

PROFILE_DIRS = {
    "work": r"C:\MIND\Workspace_Profiles\Work",
    "recharge": r"C:\MIND\Workspace_Profiles\Recharge"
}

class WorkspaceManager:
    def __init__(self):
        # Resolve Desktop path dynamically
        self.desktop_dir = os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")), "Desktop")
        self.workspace_dir = os.path.join(self.desktop_dir, "Current_Workspace")
        
        # Ensure all profile directories exist
        os.makedirs(self.workspace_dir, exist_ok=True)
        for path in PROFILE_DIRS.values():
            os.makedirs(path, exist_ok=True)
            
        # Create initial placeholders if profiles are empty
        self.initialize_placeholders()

    def initialize_placeholders(self):
        """Create placeholder info files to demonstrate switching on first run."""
        work_info = os.path.join(PROFILE_DIRS["work"], "Work_Readme.txt")
        if not os.listdir(PROFILE_DIRS["work"]) and not os.path.exists(work_info):
            try:
                with open(work_info, "w", encoding="utf-8") as f:
                    f.write("=== MIND-FLOW WORKSPACE: WORK MODE ===\n\n"
                            "This folder holds your academic and work-related files.\n"
                            "Add shortcuts to IDEs, PDFs, and notes here.\n"
                            "They will be automatically swapped onto your desktop when you start working!\n")
            except Exception as e:
                print(f"Failed to create work placeholder: {e}")

        recharge_info = os.path.join(PROFILE_DIRS["recharge"], "Recharge_Readme.txt")
        if not os.listdir(PROFILE_DIRS["recharge"]) and not os.path.exists(recharge_info):
            try:
                with open(recharge_info, "w", encoding="utf-8") as f:
                    f.write("=== MIND-FLOW WORKSPACE: RECHARGE MODE ===\n\n"
                            "This folder holds your entertainment and gaming files.\n"
                            "Add shortcuts to games, music players, and watchlists here.\n"
                            "They will be automatically swapped onto your desktop when you relax!\n")
            except Exception as e:
                print(f"Failed to create recharge placeholder: {e}")

    def is_link_or_junction(self, path):
        """Detect if path is a symbolic link or a Windows directory junction/reparse point."""
        if os.path.islink(path):
            return True
        try:
            st = os.lstat(path)
            # FILE_ATTRIBUTE_REPARSE_POINT is 1024 (0x400)
            if hasattr(st, 'st_file_attributes') and (st.st_file_attributes & 1024):
                return True
        except Exception:
            pass
        return False

    def safe_remove(self, path):
        """Safely remove a file or folder, ensuring symbolic links/junctions are not traversed."""
        try:
            if self.is_link_or_junction(path):
                # Unlink the symlink or junction itself
                if os.path.isdir(path):
                    os.rmdir(path)
                else:
                    os.remove(path)
            elif os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
        except Exception as e:
            print(f"Failed to safe_remove {path}: {e}")

    def clean_workspace_folder(self):
        """Helper to force-clean the workspace folder in case of dangling files."""
        if os.path.exists(self.workspace_dir):
            for item in os.listdir(self.workspace_dir):
                path = os.path.join(self.workspace_dir, item)
                self.safe_remove(path)

    def move_contents(self, src, dst):
        """Safely moves all contents of src folder into dst folder, handling collisions."""
        if not os.path.exists(src) or not os.path.exists(dst):
            return
        
        for item in os.listdir(src):
            s = os.path.join(src, item)
            d = os.path.join(dst, item)
            try:
                if os.path.exists(d) or self.is_link_or_junction(d):
                    self.safe_remove(d)
                shutil.move(s, d)
            except Exception as e:
                print(f"Error moving {s} to {d}: {e}")

    def swap_workspace(self, from_mode, to_mode):
        """
        Main routing function to sweep and swap directories.
        Only performs sweeps/swaps if we transition between 'work' and 'recharge'.
        If moving to neutral or rest, we sweep the current mode's files back to safety
        and leave the workspace folder clean.
        """
        # Normalize modes to lowercase
        f_mode = str(from_mode).lower()
        t_mode = str(to_mode).lower()

        # Step 1: Sweep current desktop workspace to its appropriate profile storage
        if f_mode in PROFILE_DIRS:
            target_profile = PROFILE_DIRS[f_mode]
            # Sweep all files back from Desktop/Current_Workspace to profile
            self.move_contents(self.workspace_dir, target_profile)
        
        # Ensure workspace is totally empty before bringing in new profile
        self.clean_workspace_folder()

        # Step 2: Swap in files from the new profile storage to Desktop/Current_Workspace
        if t_mode in PROFILE_DIRS:
            source_profile = PROFILE_DIRS[t_mode]
            self.move_contents(source_profile, self.workspace_dir)
            print(f"Workspace swapped: {f_mode} -> {t_mode}")
        else:
            print(f"Workspace cleared (active mode: {t_mode})")
            
        return True
