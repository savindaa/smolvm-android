# smolvm-android

Android (Redroid) as a [smolvm](https://github.com/smol-machines/smolvm) machine on Apple Silicon macOS, with GLES rendered on the host GPU through Metal, and Google Play.

```
Android app ─ GLES ─▶ ANGLE ─ Vulkan ─▶ Mesa Venus (guest) ─▶ virtio-gpu
   ─▶ libkrun / rutabaga ─▶ virglrenderer (Venus) ─▶ MoltenVK ─▶ Metal
gralloc.venus (guest) allocates every graphics buffer as Venus-exported memory
```

SurfaceFlinger on an M3 Pro reports:

```
ANGLE (Apple, Vulkan 1.1.334 (Virtio-GPU Venus (Apple M3 Pro)), venus-26.1.8)
```

## Status

| Stage | Android 13 | Android 16 |
|---|---|---|
| Boots in smolvm | ✓ | ✓ with the kernel fork ([06](docs/06-kernel.md)) |
| GPU rendering (ANGLE → Venus → Metal) | ✓ | ✓ |
| Apps run without graphics aborts | ✓ | ✓ |
| Scroll p50/p90/p99 (Settings, steady state) | 5 / 18 / 22 ms | 5 / 7 / 10 ms |
| Google Play | — | ✓ sign-in and app installs (Brave) ([08](docs/08-google-play.md)) |
| Smooth trackpad scrolling in scrcpy | — | ✓ with the patched scrcpy-server ([10](docs/10-scrcpy-smooth-scroll.md)) |

## Forks

| Component | Fork | Branch | What |
|---|---|---|---|
| libkrun | https://github.com/savindaa/libkrun | `v1.36.1-apple-blob` (rev smolvm 1.36.1 pins), `apple-blob-clone` (newer upstream) | clone Apple blob handles without dup'ing fd -1 |
| smolvm | https://github.com/savindaa/smolvm/tree/android-gpu | `android-gpu` | virglrenderer patches 0002–0003, Mesa Android patch, gralloc.venus, build/deploy scripts, [android-gpu.md](https://github.com/savindaa/smolvm/blob/android-gpu/docs/android-gpu.md) |
| libkrunfw | https://github.com/savindaa/libkrunfw | `android-bpf` | kernel config for Android 15/16: eBPF JIT, socket diagnostics, write-mounted block devices, ashmem on memfd |

## Quick start

```sh
git clone -b android-gpu https://github.com/savindaa/smolvm && cd smolvm
git clone https://github.com/savindaa/smolvm-android ../smolvm-android
```

Then follow [docs/](docs/) in order:

| # | Doc | Result |
|---|---|---|
| 01 | [prerequisites](docs/01-prerequisites.md) | toolchains without Homebrew |
| 02 | [host libraries](docs/02-host-libraries.md) | private `SMOLVM_LIB_DIR` with patched libkrun + virglrenderer |
| 03 | [Mesa Venus for Android](docs/03-mesa-android.md) | `vulkan.virtio.so` |
| 04 | [gralloc.venus](docs/04-gralloc-venus.md) | `gralloc.venus.so` |
| 05 | [Android 13 machine](docs/05-android13.md) | Redroid 13 on the host GPU |
| 06 | [kernel](docs/06-kernel.md) | libkrunfw with Android 16 kernel options |
| 07 | [Android 16 machine](docs/07-android16.md) | Redroid 16 on the host GPU |
| 08 | [Google Play](docs/08-google-play.md) | Play Store installs |
| 09 | [results and troubleshooting](docs/09-results-troubleshooting.md) | numbers, root causes, tracing |
| 10 | [smooth trackpad scrolling](docs/10-scrcpy-smooth-scroll.md) | patched scrcpy-server |

`SMOLVM_LIB_DIR` must be set on every `smolvm machine run` and `machine start`; without it the stock libs load and Android apps abort.
