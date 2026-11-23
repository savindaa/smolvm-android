# 07 · Android 16 machine

Image `redroid/redroid:16.0.0_64only-latest` (arm64, pushed 2025-06-29). Graphics HALs are the same HIDL gralloc0 path as 13, so 03 and 04 carry over.

```sh
export SMOLVM_LIB_DIR=<private lib dir from 02, with the 06 kernel>
smolvm machine run -d --name redroid16gpu --net --gpu --mem 4096 --cpus 8 \
  -p 5557:5555 --image redroid/redroid:16.0.0_64only-latest -- \
  /init qemu=1 androidboot.hardware=redroid androidboot.redroid_gpu_mode=guest \
  androidboot.use_memfd=1 androidboot.redroid_fps=60
```

## Workarounds found

| Problem | Fix | File |
|---|---|---|
| init exits after ~23 s: APEXes are loop-mounted images; smolvm gives a read-only `/sys` and no `/dev/loop-control` | wrapper `/init` remounts `/sys` rw, creates loop nodes, execs `/system/bin/init` | [android16/init.wrap](../android16/init.wrap) |
| APEX mounts fail `EBUSY` (kernel refuses mounting a block device apexd holds open for write) | `CONFIG_BLK_DEV_WRITE_MOUNTED=y` in the 06 kernel (a libkrun cmdline `bdev_allow_write_mounted=1` also works but is no longer needed) | [06](06-kernel.md) |
| default guest mode picks `gralloc.redroid` + software Vulkan; SurfaceFlinger aborts "output buffer not gpu writeable" | Android 16's own `gpu_config.sh` plus a `venus` mode, used when `/vendor/etc/gpu_gralloc` exists | [android16/gpu_config.sh](../android16/gpu_config.sh) |
| netd crash-loop on eBPF JIT; netd `inet_diag` errors | kernel fork | [06](06-kernel.md) |
| every app aborts on present | Mesa: advertise sync_fd fences only when exportable | smolvm fork `patches/mesa-android/0002` |
| gralloc.venus rejects formats 0x39/0x3a/0x3b | added to gralloc.venus | [04](04-gralloc-venus.md) |
| battery shows `?` | fixed battery via init rc (below) | [android16/battery_fixed.rc](../android16/battery_fixed.rc) |

Installing the wrapper by hand (skip this block when using the deploy script below, which does the same; busybox taken from the `busybox:musl` image):

```sh
smolvm machine run --image busybox:musl -v $WORK/bb:/out -- cp /bin/busybox /out/busybox
smolvm machine cp --mode 755 $WORK/bb/busybox redroid16gpu:/busybox
smolvm machine exec --name redroid16gpu -- /busybox rm /init
smolvm machine cp --mode 755 android16/init.wrap redroid16gpu:/init
```

Deploy:

```sh
SMOLVM_FORK=<smolvm android-gpu checkout> OUT=<dir with vulkan.virtio.so and gralloc.venus.so> \
  BUSYBOX=$WORK/bb/busybox scripts/deploy-android.sh redroid16gpu 5557 --android16
```

Check the driver before deploying: `strings vulkan.virtio.so | grep 'Mesa 2'` must show `Mesa 26.1.8`. An older build (e.g. Mesa 24) lacks the Android swapchain and SurfaceFlinger crash-loops (09).

## Battery

Redroid has no battery. The rc reports a full battery on external power at every boot:

```sh
smolvm machine cp --mode 644 android16/battery_fixed.rc redroid16gpu:/vendor/etc/init/battery_fixed.rc
```

Order matters: set `ac` and `level` before `present`. A present battery at level 0 without power makes system_server request `shutdown,battery` seconds after boot (seen once, then fixed by reordering).

## CPUs

`--cpus 8` is fine; change it in place with `smolvm machine update --cpus N` (no data loss).

| vCPU | boot | one-way scroll p50/p90/p99 | host CPU while scrolling (mean) | host CPU idle |
|---|---|---|---|---|
| 4 | 4.3 s | 5/9/19 ms | 73% | 18% |
| 6 | 4.4 s | 5/6/12 ms | 69% | 25% |
| 8 | 4.4 s | 5/7/11 ms typical; one run 19/22/27 ms (see 09) | 61% | 17% |

## Checks (M3 Pro, 8 vCPU)

| Check | Result |
|---|---|
| boot to `sys.boot_completed` | ~4–18 s |
| SurfaceFlinger renderer | `ANGLE (Apple, Vulkan 1.1.334 (Virtio-GPU Venus (Apple M3 Pro)), venus-26.1.8)` |
| apps (Settings, SystemUI, Launcher) | no graphics aborts |
| scrcpy | streams (kernel 06 includes the ashmem-on-memfd fix) |
| steady-state scroll | p90 5–7 ms, jank ≤ 0.52% |
