#!/usr/bin/env bash
# Deploy the guest GPU stack into a Redroid machine and restart it.
#   deploy-android.sh <machine> <adb-port> [--android16]
# Env: SMOLVM_LIB_DIR (private lib dir, 02), SMOLVM_FORK (smolvm android-gpu checkout),
#      OUT (dir with vulkan.virtio.so and gralloc.venus.so; default $SMOLVM_FORK/target/android-gpu/out)
# Untested as a whole script; each step ran by hand in the session.
set -euo pipefail
MACHINE="${1:?machine name}"
PORT="${2:?adb port}"
A16="${3:-}"
: "${SMOLVM_LIB_DIR:?export SMOLVM_LIB_DIR}"
: "${SMOLVM_FORK:?export SMOLVM_FORK=<smolvm android-gpu checkout>}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${OUT:-$SMOLVM_FORK/target/android-gpu/out}"

cp_in() { smolvm machine cp --mode "$1" "$2" "$MACHINE:$3"; }

cp_in 644 "$OUT/vulkan.virtio.so" /vendor/lib64/hw/vulkan.virtio.so
cp_in 644 "$OUT/gralloc.venus.so" /vendor/lib64/hw/gralloc.venus.so
cp_in 644 "$SMOLVM_FORK/android/vendor/gpu_gralloc" /vendor/etc/gpu_gralloc
cp_in 644 "$SMOLVM_FORK/android/vendor/gpu_egl" /vendor/etc/gpu_egl
if [[ "$A16" == "--android16" ]]; then
    cp_in 755 "$HERE/android16/gpu_config.sh" /vendor/bin/gpu_config.sh
    [[ -f "${BUSYBOX:-}" ]] || { echo "set BUSYBOX to an arm64 busybox (see docs/07)" >&2; exit 1; }
    cp_in 755 "$BUSYBOX" /busybox
    smolvm machine exec --name "$MACHINE" -- /busybox rm -f /init
    cp_in 755 "$HERE/android16/init.wrap" /init
else
    cp_in 755 "$SMOLVM_FORK/android/vendor/gpu_config.sh" /vendor/bin/gpu_config.sh
fi

smolvm machine stop --name "$MACHINE"
smolvm machine start --name "$MACHINE"
adb disconnect "127.0.0.1:$PORT" >/dev/null 2>&1 || true
booted=
for _ in $(seq 60); do
    adb connect "127.0.0.1:$PORT" >/dev/null 2>&1 || true
    # A restarted machine leaves adb holding a dead "offline" connection.
    [[ "$(adb devices | awk -v d="127.0.0.1:$PORT" '$1==d{print $2}')" == offline ]] && adb disconnect "127.0.0.1:$PORT" >/dev/null 2>&1
    [[ "$(adb -s "127.0.0.1:$PORT" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" == 1 ]] && { booted=1; break; }
    sleep 3
done
[[ -n "$booted" ]] || { echo "not booted after 180 s; see docs/09" >&2; exit 1; }
adb -s "127.0.0.1:$PORT" shell dumpsys SurfaceFlinger | grep -m1 'GLES:'
