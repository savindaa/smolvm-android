# scripts

| Script | Where | What |
|---|---|---|
| `deploy-android.sh` | here | copy guest pieces into a Redroid 13/16 machine, restart, wait for boot |
| `image/build-image.py` | here | never-booted Android 16 + GPU + Google Play image (11) |
| `env.sh`, `build-mesa-android.sh`, `build-gralloc-venus.sh`, `install-host-libs.sh`, `deploy-redroid.sh` | smolvm fork, `scripts/android-gpu/` on `android-gpu` | NDK download (sha256), Mesa + gralloc builds, private lib dir |
| `build-virglrenderer-macos.sh` | smolvm fork | virglrenderer + libepoxy, `VULKAN_HEADERS` override (no brew) |
