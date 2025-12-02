#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Complete Package Creator
Creates a complete, ready-to-distribute package
"""

import os
import shutil
from pathlib import Path
from datetime import datetime

def create_package():
    """Create complete distribution package"""

    # Source and destination
    source = Path(__file__).parent
    version = "v2.3.1"
    date = datetime.now().strftime("%Y%m%d")
    dest_name = f"DoctorVoicePro-Complete-{version}-{date}"
    dest = source.parent / dest_name

    print(f"\n{'='*60}")
    print(f"  Creating Complete Package")
    print(f"{'='*60}\n")
    print(f"Source: {source}")
    print(f"Destination: {dest}\n")

    # Remove if exists
    if dest.exists():
        print(f"[INFO] Removing existing folder...")
        shutil.rmtree(dest)

    # Create destination
    dest.mkdir(parents=True, exist_ok=True)
    print(f"[OK] Created destination folder\n")

    # Copy backend
    print(f"[1/13] Copying backend folder...")
    shutil.copytree(source / "backend", dest / "backend",
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'venv', '.env'))
    print(f"[OK] Backend copied\n")

    # Copy frontend
    print(f"[2/13] Copying frontend folder...")
    shutil.copytree(source / "frontend", dest / "frontend",
                    ignore=shutil.ignore_patterns('node_modules', '.next', '.env.local'))
    print(f"[OK] Frontend copied\n")

    # Copy Python files
    print(f"[3/13] Copying Python files...")
    python_files = [
        'port_finder.py',
        'connection_manager.py',
        'start_with_connection.py'
    ]
    for file in python_files:
        if (source / file).exists():
            shutil.copy2(source / file, dest / file)
    print(f"[OK] Python files copied\n")

    # Create connection_config.json
    print(f"[4/13] Creating connection_config.json...")
    config = '''{
  "backend": {
    "host": "localhost",
    "port": 8010,
    "protocol": "http"
  },
  "frontend": {
    "host": "localhost",
    "port": 3000,
    "protocol": "http"
  },
  "connection": {
    "health_check_interval": 5,
    "reconnect_interval": 3,
    "max_reconnect_attempts": 100,
    "timeout": 5
  }
}'''
    (dest / "connection_config.json").write_text(config, encoding='utf-8')
    print(f"[OK] Config file created\n")

    # Create batch files
    print(f"[5/13] Creating ONE_CLICK_INSTALL_AND_RUN.bat...")
    install_bat = '''@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo ================================================================
echo   Doctor Voice Pro - Auto Install and Run
echo ================================================================
echo.

python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python not installed!
    pause
    exit /b 1
)

node --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Node.js not installed!
    pause
    exit /b 1
)

echo [OK] Python installed
echo [OK] Node.js installed
echo.

echo [2] Backend Installation
echo.
cd backend
pip install -r requirements.txt
python -m alembic upgrade head > nul 2>&1
cd ..

echo.
echo [3] Frontend Installation
echo.
cd frontend
npm install
cd ..

echo.
echo [4] Starting Server
echo.
python start_with_connection.py

pause
'''
    (dest / "ONE_CLICK_INSTALL_AND_RUN.bat").write_text(install_bat, encoding='utf-8')
    print(f"[OK] Install script created\n")

    print(f"[6/13] Creating run_connected.bat...")
    run_bat = '''@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo Starting Doctor Voice Pro...
python start_with_connection.py

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Server startup failed!
    pause
)
'''
    (dest / "run_connected.bat").write_text(run_bat, encoding='utf-8')
    print(f"[OK] Run script created\n")

    print(f"[7/13] Creating 닥터보이스프로.bat...")
    smart_bat = '''@echo off
chcp 65001 > nul
cd /d "%~dp0"

if exist "backend\\__pycache__" (
    if exist "frontend\\node_modules" (
        echo Starting Doctor Voice Pro...
        run_connected.bat
    ) else (
        ONE_CLICK_INSTALL_AND_RUN.bat
    )
) else (
    ONE_CLICK_INSTALL_AND_RUN.bat
)
'''
    (dest / "닥터보이스프로.bat").write_text(smart_bat, encoding='utf-8')
    print(f"[OK] Smart launcher created\n")

    print(f"[8/13] Creating CREATE_DESKTOP_SHORTCUT.bat...")
    shortcut_bat = '''@echo off
chcp 65001 > nul

set "SCRIPT_DIR=%~dp0"
set "DESKTOP=%USERPROFILE%\\Desktop"
set "ONEDRIVE_DESKTOP=%USERPROFILE%\\OneDrive\\Desktop"

if exist "%ONEDRIVE_DESKTOP%" (
    set "DESKTOP=%ONEDRIVE_DESKTOP%"
)

echo Creating desktop shortcut...

echo Set oWS = WScript.CreateObject("WScript.Shell") > "%TEMP%\\CreateShortcut.vbs"
echo sLinkFile = "%DESKTOP%\\Doctor Voice Pro.lnk" >> "%TEMP%\\CreateShortcut.vbs"
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> "%TEMP%\\CreateShortcut.vbs"
echo oLink.TargetPath = "%SCRIPT_DIR%ONE_CLICK_INSTALL_AND_RUN.bat" >> "%TEMP%\\CreateShortcut.vbs"
echo oLink.WorkingDirectory = "%SCRIPT_DIR%" >> "%TEMP%\\CreateShortcut.vbs"
echo oLink.Save >> "%TEMP%\\CreateShortcut.vbs"

cscript //nologo "%TEMP%\\CreateShortcut.vbs"
del "%TEMP%\\CreateShortcut.vbs"

echo [SUCCESS] Desktop shortcut created!
pause
'''
    (dest / "CREATE_DESKTOP_SHORTCUT.bat").write_text(shortcut_bat, encoding='utf-8')
    print(f"[OK] Shortcut creator created\n")

    print(f"[9/13] Creating INSTALL_NODEJS.bat...")
    nodejs_bat = '''@echo off
chcp 65001 > nul

echo Node.js installation is required.
echo.
echo Opening Node.js download page...
start https://nodejs.org/
pause
'''
    (dest / "INSTALL_NODEJS.bat").write_text(nodejs_bat, encoding='utf-8')
    print(f"[OK] Node.js installer created\n")

    print(f"[10/13] Creating LICENSE.txt...")
    license_text = '''MIT License

Copyright (c) 2025 DoctorVoicePro

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
'''
    (dest / "LICENSE.txt").write_text(license_text, encoding='utf-8')
    print(f"[OK] License created\n")

    print(f"[11/13] Creating README.md...")
    readme = f'''# Doctor Voice Pro {version}

AI-powered medical blog content generation platform

## Quick Start

```cmd
ONE_CLICK_INSTALL_AND_RUN.bat
```

## System Requirements

- Windows 10+ (64-bit)
- Python 3.10+
- Node.js 16+
- 2GB disk space

## Installation

### Method 1: One-Click Install
```cmd
ONE_CLICK_INSTALL_AND_RUN.bat
```

### Method 2: Quick Run
```cmd
run_connected.bat
```

### Method 3: Smart Launcher
```cmd
닥터보이스프로.bat
```

## Features

- Automatic port management
- Connection management
- One-click installation
- Portable

## Documentation

- README.md - This file
- QUICK_FIX.md - Troubleshooting
- LICENSE.txt - License

Version: {version}
Date: {date}
'''
    (dest / "README.md").write_text(readme, encoding='utf-8')
    print(f"[OK] README created\n")

    print(f"[12/13] Creating QUICK_FIX.md...")
    quickfix = '''# Quick Fix Guide

## Server Startup Failed

**Solution:**
```cmd
ONE_CLICK_INSTALL_AND_RUN.bat
```

## Port Conflict

**Check ports:**
```cmd
netstat -ano | findstr "8010 3000"
```

## Package Installation Failed

**Backend:**
```cmd
cd backend
pip install -r requirements.txt
```

**Frontend:**
```cmd
cd frontend
npm install
```

## Database Error

**Reset database:**
```cmd
cd backend
del medical_blog.db
python -m alembic upgrade head
```

## Complete Reset

```cmd
cd backend
rmdir /s /q venv
del medical_blog.db

cd ../frontend
rmdir /s /q node_modules

cd ..
ONE_CLICK_INSTALL_AND_RUN.bat
```
'''
    (dest / "QUICK_FIX.md").write_text(quickfix, encoding='utf-8')
    print(f"[OK] Quick fix guide created\n")

    print(f"[13/13] Creating execution guide...")
    guide = '''Doctor Voice Pro - Quick Execution Guide

Method 1: Desktop Shortcut (Easiest!)
======================================
1. Run CREATE_DESKTOP_SHORTCUT.bat (once)
2. Double-click "Doctor Voice Pro" icon on desktop

Method 2: Simple Launcher
=========================
Double-click: 닥터보이스프로.bat

Method 3: Direct Execution
==========================
First time: ONE_CLICK_INSTALL_AND_RUN.bat
Already installed: run_connected.bat

Summary
=======
First use: CREATE_DESKTOP_SHORTCUT.bat (once)
Later: Double-click desktop icon

Tips
====
- Pin to taskbar for quick access
- Can copy to USB for portable use
'''
    (dest / "실행방법_요약.txt").write_text(guide, encoding='utf-8')
    print(f"[OK] Execution guide created\n")

    print(f"{'='*60}")
    print(f"  [SUCCESS] Package Created!")
    print(f"{'='*60}\n")
    print(f"Location: {dest}\n")
    print(f"Next steps:")
    print(f"1. cd {dest}")
    print(f"2. ONE_CLICK_INSTALL_AND_RUN.bat\n")

if __name__ == '__main__':
    try:
        create_package()
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")
