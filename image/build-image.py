#!/usr/bin/env python3
"""Build a never-booted Android 16 + GPU + Google Play image as one layer on top of Redroid 16.

    uv run image/build-image.py --gapps MindTheGapps-16.0.0-arm64-*.zip --guest <dir> -o android16-gplay.tar

<dir> holds vulkan.virtio.so, gralloc.venus.so (docs 03, 04) and an arm64 busybox (doc 07).
Needs `crane` (mise exec aqua:google/go-containerregistry -- crane).
"""
import argparse
import io
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

BASE = "redroid/redroid@sha256:e194edc99aa364358d1f8c214acb18b6d006c74fa0561f39259a20173ec30b66"
HERE = Path(__file__).resolve().parent
A16 = HERE.parent / "android16"


def base_dirs():
    # Existing dirs keep the base image's owner and mode (several vendor dirs are gid 2000),
    # so the layer only carries directory entries for dirs Google Play adds.
    return {line.split()[-1].lstrip("/") for line in (HERE / "base-dirs-16.txt").read_text().splitlines() if line}


def add(tar, name, data, mode):
    info = tarfile.TarInfo(name)
    info.size, info.mode, info.uid, info.gid, info.uname, info.gname = len(data), mode, 0, 0, "root", "root"
    tar.addfile(info, io.BytesIO(data))


def add_dir(tar, name):
    info = tarfile.TarInfo(name)
    info.type, info.mode, info.uid, info.gid, info.uname, info.gname = tarfile.DIRTYPE, 0o755, 0, 0, "root", "root"
    tar.addfile(info)


def build_layer(gapps, guest, out):
    known = base_dirs()
    with tarfile.open(out, "w", format=tarfile.PAX_FORMAT) as tar:
        add(tar, "init", (A16 / "init.wrap").read_bytes(), 0o755)
        add(tar, "busybox", (guest / "busybox").read_bytes(), 0o755)
        add(tar, "vendor/bin/gpu_config.sh", (A16 / "gpu_config.sh").read_bytes(), 0o755)
        add(tar, "vendor/etc/gpu_gralloc", b"venus", 0o644)
        add(tar, "vendor/etc/gpu_egl", b"angle", 0o644)
        add(tar, "vendor/etc/init/battery_fixed.rc", (A16 / "battery_fixed.rc").read_bytes(), 0o644)
        add(tar, "vendor/lib64/hw/vulkan.virtio.so", (guest / "vulkan.virtio.so").read_bytes(), 0o644)
        add(tar, "vendor/lib64/hw/gralloc.venus.so", (guest / "gralloc.venus.so").read_bytes(), 0o644)
        if (guest / "hwcomposer.venus.so").exists():
            add(tar, "vendor/lib64/hw/hwcomposer.venus.so", (guest / "hwcomposer.venus.so").read_bytes(), 0o644)

        with zipfile.ZipFile(gapps) as z:
            seen = set()
            for entry in sorted(z.namelist()):
                if not entry.startswith(("system/product/", "system/system_ext/")) or entry.endswith("/"):
                    continue
                # SetupWizard dropped, AOSP Provision kept (doc 08).
                if entry.startswith("system/system_ext/priv-app/SetupWizard/"):
                    continue
                parts = entry.split("/")
                for i in range(2, len(parts)):
                    d = "/".join(parts[:i])
                    if d not in known and d not in seen:
                        add_dir(tar, d)
                        seen.add(d)
                add(tar, entry, z.read(entry), 0o644)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--gapps", type=Path, required=True)
    p.add_argument("--guest", type=Path, required=True)
    p.add_argument("-o", "--output", type=Path, required=True)
    p.add_argument("--crane", default="crane")
    a = p.parse_args()
    layer = a.output.with_suffix(".layer.tar")
    build_layer(a.gapps, a.guest, layer)
    subprocess.run([a.crane, "append", "--platform", "linux/arm64", "-b", BASE, "-f", str(layer), "-t", "smolvm-android:16-gplay", "-o", str(a.output)], check=True)
    layer.unlink()
    print(a.output)


if __name__ == "__main__":
    sys.exit(main())
