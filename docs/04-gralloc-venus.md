# 04 · gralloc.venus

A gralloc0 HAL module (loaded by Redroid's HIDL allocator@2.0 / mapper@2.0 passthrough) whose buffers are Venus-exported dma-bufs, so every process imports the same host memory.

```sh
cd smolvm   # android-gpu branch; needs 03 first (headers from Mesa's android_stub)
scripts/android-gpu/build-gralloc-venus.sh   # → target/android-gpu/out/gralloc.venus.so
```

Session-run compile line:

```sh
$NDK/toolchains/llvm/prebuilt/darwin-x86_64/bin/aarch64-linux-android33-clang -O2 -Wall -Wextra \
  -Wno-unused-parameter -fPIC -shared -fvisibility=hidden \
  -I$MESA/include/android_stub -I$MESA/include -o gralloc.venus.so gralloc_venus.c -llog -lvulkan
```

| Design point | Detail |
|---|---|
| module name | `CrOS Gralloc`, so Mesa's u_gralloc takes its CrOS path and calls `perform(4)` (GET_BUFFER_INFO) |
| allocation | lazy Vulkan device; LINEAR image for layout (rowPitch, size); exportable host-visible coherent memory; export dma-buf; free the memory at once (the host keeps it alive, patch 0003) |
| size | aligned to 16384 (Metal wraps whole pages) |
| formats | RGBA/RGBX, BGRA, 565, FP16, 1010102, R_8; RGB_888, YCbCr_420_888 (NV12), NV21, YV12, BLOB as plain memory; IMPLEMENTATION_DEFINED → NV12 for video/camera, else RGBX |
| lock | mmap the dma-buf, cached per handle; `lockAsync` waits on the fence |
| Android 16 formats | 0x39, 0x3a, 0x3b added (smolvm fork `android/gralloc-venus/gralloc_venus.c`) |
