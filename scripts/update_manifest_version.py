#!/usr/bin/env python3
"""Update manifest.json version for semantic release."""

import json
import sys
from pathlib import Path


def main():
    """Update manifest version."""
    if len(sys.argv) != 2:
        print("Usage: update_manifest_version.py <version>")
        sys.exit(1)

    version = sys.argv[1]
    manifest_path = Path("custom_components/smartly_bridge/manifest.json")

    if not manifest_path.exists():
        print(f"❌ Error: manifest.json not found at {manifest_path}")
        sys.exit(1)

    # Read manifest
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # Update version
    old_version = manifest.get("version", "unknown")
    manifest["version"] = version

    # Write back
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"✓ Updated manifest.json version: {old_version} → {version}")


if __name__ == "__main__":
    main()
