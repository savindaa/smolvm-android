# 05 · Android 13 machine (GPU)

Tested end to end.

```sh
export SMOLVM_LIB_DIR=<private lib dir from 02>
smolvm machine run -d --name redroid13gpu --net --gpu --mem 4096 --cpus 8 \
  -p 5556:5555 --image redroid/redroid:13.0.0_64only-latest -- \
  /init qemu=1 androidboot.hardware=redroid androidboot.redroid_gpu_mode=guest \
  androidboot.use_memfd=1 androidboot.redroid_fps=60
```

Deploy the guest pieces and restart ([scripts/deploy-android.sh](../scripts/deploy-android.sh)):

| Host file | Guest path | Mode |
|---|---|---|
| `vulkan.virtio.so` (03) | `/vendor/lib64/hw/vulkan.virtio.so` | 644 |
| `gralloc.venus.so` (04) | `/vendor/lib64/hw/gralloc.venus.so` | 644 |
| `android/vendor/gpu_config.sh` (smolvm fork) | `/vendor/bin/gpu_config.sh` | 755 |
| `android/vendor/gpu_gralloc` (`venus`) | `/vendor/etc/gpu_gralloc` | 644 |
| `android/vendor/gpu_egl` (`angle`) | `/vendor/etc/gpu_egl` | 644 |

```sh
scripts/deploy-android.sh redroid13gpu 5556
```

## Verify

| Check | Command | Expect |
|---|---|---|
| boot | `adb -s 127.0.0.1:5556 shell getprop sys.boot_completed` | `1` |
| renderer | `adb -s 127.0.0.1:5556 shell dumpsys SurfaceFlinger \| grep GLES` | `ANGLE (Apple, Vulkan … Venus (Apple M…))` |
| no aborts | `adb -s 127.0.0.1:5556 logcat -d \| grep 'F DEBUG'` | nothing from RenderThread / `vulkan.virtio.so` |
| UI | `adb -s 127.0.0.1:5556 exec-out screencap -p > shot.png` | real UI, not black |
| view | `scrcpy -s 127.0.0.1:5556 --max-fps 60 --no-audio` | live window |
