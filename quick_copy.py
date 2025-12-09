#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Quick copy script for deployment"""

import os
import sys
import shutil
from pathlib import Path

# Source and destination
source = Path(r"C:\Users\u\doctor-voice-pro")
dest = Path(r"C:\Users\u\DoctorVoicePro-v2.0.1-20251030")

# Exclude patterns
exclude_patterns = {
    'node_modules', '__pycache__', '.next', '.git',
    'venv', 'env', '.venv', 'logs', 'data',
    'error_reports', 'backups', 'nul',
    '.backend.pid', '.frontend.pid'
}

exclude_extensions = {'.pyc', '.pyo', '.log', '.db', '.sqlite', '.sqlite3'}

def should_ignore(dir_path, files):
    """Determine which files to ignore"""
    ignored = []
    for f in files:
        # Check exclude patterns
        if f in exclude_patterns:
            ignored.append(f)
            continue

        # Check extensions
        if any(f.endswith(ext) for ext in exclude_extensions):
            ignored.append(f)
            continue

        # Check .env files
        if f == '.env' or f.startswith('.env.'):
            if f != '.env.example':
                ignored.append(f)

    return ignored

try:
    print("Copying files...")
    print(f"From: {source}")
    print(f"To: {dest}")

    if dest.exists():
        shutil.rmtree(dest)

    shutil.copytree(
        source,
        dest,
        ignore=should_ignore,
        dirs_exist_ok=False
    )

    # Create necessary directories
    (dest / 'logs').mkdir(exist_ok=True)
    (dest / 'data').mkdir(exist_ok=True)
    (dest / 'error_reports').mkdir(exist_ok=True)
    (dest / 'backups').mkdir(exist_ok=True)

    # Create .gitkeep files
    for dir_name in ['logs', 'data', 'error_reports', 'backups']:
        (dest / dir_name / '.gitkeep').touch()

    print("Copy completed successfully!")
    print(f"Destination: {dest}")

except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
