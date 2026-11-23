# 09 · Results and troubleshooting

## Results (Android 13, M3 Pro, 720x1280, 40 scripted swipes)

| Check | Software rendering | GPU (this repo) |
|---|---|---|
| Host Venus fatals per app launch | — | 0 |
| Settings p50/p90/p99 | 21 / 32 / 57 ms | 5 / 18 / 22 ms |
| Settings deadline-missed frames | 6.36% | 0.18% |
| Launcher all-apps p50/p90/p99 | — | 17 / 21 / 44 ms |
| Render time p90 (framestats) | — | 6.7 ms |
| Display | 60 Hz | 60 Hz, 0 frames dropped by SurfaceFlinger |
| Host CPU during scroll (mean) | — | 61% Settings, 85% launcher |

p90 above 16.7 ms comes from injected-input latency (133 "high input latency" frames, 0 slow UI thread, 0 missed vsync); real mouse input in scrcpy felt smooth.

## Results (Android 16, M3 Pro, 8 vCPU)

| Run | jank | p50/p90/p99 |
|---|---|---|
| Settings, 30 one-way swipes | 0.00% | 5 / 7 / 10 ms |
| Launcher app drawer, 30 swipes | 0.00% | 5 / 6 / 9 ms |
| with scrcpy streaming | 0.25% | 5 / 5 / 11 ms |
| intermittent full-buffer mode | 0.24% | 19 / 23 / 28 ms |

The full-buffer mode: the app waits ~1 frame in `dequeueBuffer` (`DequeueBufferDuration` p50 15.4 ms vs 0 normally); still 60 fps, one frame late. hwcomposer.redroid reports `PresentFences=false`, which likely hampers recovery (untested). Not tied to boot age or vCPU count.

Trackpad scrolling in scrcpy looks like tearing but is judder: 0 torn frames in ~4,200, while 27–32% of frames move >40% off their neighbours. Android batches and resamples touch moves but not scroll events (`InputConsumer.cpp:317-318`, `571-572`). Fix: [10](10-scrcpy-smooth-scroll.md).

## Root causes found

| Symptom | Cause | Fix |
|---|---|---|
| blob resources can't be shared | rutabaga `try_clone` dup'd fd -1 of an Apple handle | libkrun patch 0001 |
| `GetMemoryFdProperties` → `INVALID_EXTERNAL_HANDLE`; import of other process's buffers fails | macOS has no dma-buf fds; host required DMABUF fd type | virglrenderer 0002: import by host pointer (`VkImportMemoryHostPointerInfoEXT`), answer resource memory properties for pointer resources |
| GPU clear of imported image invisible | host maps DRM-modifier images to OPTIMAL private textures | Mesa: LINEAR images for gralloc buffers |
| apps SIGABRT `vn_ring_submit abort on fatal` in `CreateSwapchainKHR` | host freed exported memory on the exporter's detach; MoltenVK `newBufferWithBytesNoCopy` on the dead pointer → `VK_ERROR_OUT_OF_DEVICE_MEMORY`; next bind looked up a missing object | virglrenderer 0003: keep exported memory until the last unref |
| same, with non-page-aligned sizes | Metal wraps whole pages only | 0003: round host-pointer imports up to the resource size |
| Android 16 init exits | APEX loop mounts: read-only `/sys`, no loop nodes | init wrapper (07) |
| Android 16 APEX `EBUSY` | block device held open for write | `bdev_allow_write_mounted=1` (07) |
| Android 16 netd crash-loop | no eBPF JIT in libkrunfw kernel | kernel fork (06) |
| Android 16 apps abort on present | Venus advertised sync_fd fences it can't export | Mesa 0002 |
| Android 16 netd `inet_diag` errors | no socket diagnostics in kernel | kernel fork (06) |
| Android 16 shuts down seconds after boot | battery rc set `present` before power and level | reorder (07) |

## Tracing the host

virglrenderer logs go through libkrun's logger, which smolvm doesn't surface (`VIRGL_LOG_FILE` writes nothing). Guest `vn_ring_submit abort on fatal` always means a host-side fatal. The session used a debug build (virglrenderer branch `debug-trace`, not published) that:

- appends `vkr_log` lines to the file named by `VKR_TRACE_FILE`
- wraps `vkr_cs_decoder_set_fatal`, `vkr_cs_encoder_set_fatal`, `vkr_context_set_fatal` in macros that log `FATAL file:line func`

```sh
SMOLVM_LIB_DIR=<lib dir with the trace build> VKR_TRACE_FILE=$WORK/vkr-trace.log smolvm machine start --name <machine>
sort $WORK/vkr-trace.log | uniq -c | sort -rn | head
```

The first `FATAL` line names the failing lookup or call (e.g. `failed to look up object 21` after a failed import).

## Gotchas

| Gotcha | Note |
|---|---|
| `SMOLVM_LIB_DIR` | needed on every `machine run` and `machine start` |
| `vkr_log` level | INFO; `VIRGL_LOG_LEVEL` takes `debug`/`info`/`warning`/`error` but output never reaches a file under smolvm |
| Redroid bluetooth crashes | simulated service; unrelated to the GPU |
| `adb input swipe` | inflates "high input latency" counts; once crashed system_server (InputDispatcher pointer overlap with the Taskbar) ~60 s after boot |
| measuring right after a driver swap | first run can be slow; measure steady state |
| gralloc restart | its context teardown frees exported memory still held by apps (untested risk) |
