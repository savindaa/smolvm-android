# 03 · Mesa Venus driver for Android

Mesa 26.1.8, Venus (`virtio`) Vulkan driver, cross-built for Android arm64 API 33 with the NDK. Replaces Redroid's bundled Mesa 24 driver.

```sh
cd smolvm   # android-gpu branch
scripts/android-gpu/build-mesa-android.sh   # → target/android-gpu/out/vulkan.virtio.so
```

Patch `patches/mesa-android/0001` (Mesa clone branch `smolvm-android-gpu`):

| Change | File | Why |
|---|---|---|
| plain LINEAR images for gralloc buffers (modifier 0, 1 plane) | `vn_android.c` | the macOS host turns DRM-modifier images into private Metal textures that don't alias shared memory |
| aspect passthrough for linear deferred images | `vn_image.c/.h` | follows from the LINEAR builder |
| advertise `OPAQUE_FD`/`DMA_BUF` external memory + `KHR_external_memory_fd`, `EXT_external_memory_dma_buf` | `vn_physical_device.c` | gralloc.venus exports buffers as dma-bufs |
| native_buffer gate, single graphics queue family, no fence-fd assert | `vn_physical_device.c`, `vn_device.c` | ANGLE on a MoltenVK host |

Key meson options: `-Dplatforms=android -Dplatform-sdk-version=33 -Dandroid-stub=true -Dvulkan-drivers=virtio -Dgallium-drivers= -Dopengl=false`. Build target: `src/virtio/vulkan/libvulkan_virtio.so`, then `llvm-strip`.
