#!/usr/bin/env python3
"""
Fix Windows Long Path Support for Python
Allows pip to install packages with long file paths (required for openai-whisper)
"""

import sys
import subprocess

print("=" * 70)
print("  Windows Long Path Support Fix")
print("=" * 70)
print()

# Check if running as administrator
try:
    import ctypes
    is_admin = ctypes.windll.shell.IsUserAnAdmin()
except:
    is_admin = False

if not is_admin:
    print("❌ This script must run as Administrator")
    print()
    print("Steps:")
    print("1. Right-click on PowerShell")
    print("2. Select 'Run as Administrator'")
    print("3. Navigate to D:\\G.A.R.V.I.S")
    print("4. Run: python fix_long_path.py")
    sys.exit(1)

print("✅ Running as Administrator")
print()

# Try to enable long path support via registry
try:
    print("Attempting to enable Windows Long Path support...")
    import winreg
    
    # Registry path for Windows 10/11
    key_path = r"SYSTEM\CurrentControlSet\Control\FileSystem"
    
    # Try to modify registry (might fail on some systems)
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, access=winreg.KEY_WRITE)
        winreg.SetValueEx(key, "LongPathsEnabled", 0, winreg.REG_DWORD, 1)
        winreg.CloseKey(key)
        print("✅ Registry updated: LongPathsEnabled = 1")
    except PermissionError:
        print("⚠️  Could not update registry (insufficient permissions)")
        print("   Try manually: https://bit.ly/windows-long-path")
    
except ImportError:
    print("⚠️  winreg not available on this system")

print()
print("=" * 70)
print("Now installing openai-whisper...")
print("=" * 70)
print()

# Install whisper with --no-user flag
result = subprocess.run(
    [sys.executable, "-m", "pip", "install", "openai-whisper"],
    capture_output=False
)

if result.returncode == 0:
    print()
    print("✅ openai-whisper installed successfully!")
    print()
    print("You can now run: python main.py")
else:
    print()
    print("❌ Installation failed")
    print()
    print("Alternative: Install pre-compiled wheel from:")
    print("https://github.com/jartine/openai-whisper/releases")

print()
