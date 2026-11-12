#!/usr/bin/env python3
"""Regenerate the ROM-free source inventory and its public presentation."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def main():
    subprocess.run([sys.executable, 'tools/scripts/metadata_build.py'], cwd=ROOT, check=True)
    subprocess.run([sys.executable, 'tools/scripts/progress_visuals.py',
                    '--metadata-dir', 'build/metadata', '--out', 'docs/progress/usa'],
                   cwd=ROOT, check=True)
    receipt = ROOT / 'config/regions/eu_verified.json'
    # Missing receipts must overwrite old verified views with an unverified one.
    subprocess.run([sys.executable, 'tools/scripts/region_progress.py',
                    '--report', str(receipt), '--out', 'docs/progress'],
                   cwd=ROOT, check=True)


if __name__ == '__main__':
    main()
