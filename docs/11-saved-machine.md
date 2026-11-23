# 11 · Saved Android 16 + Google Play machine

One file that starts a never-booted Android 16 with the Metal GPU path, the battery fix and Google Play, with no build steps. It bundles the patched host libraries (libkrun, virglrenderer, MoltenVK, libkrunfw with the 06 kernel), but `machine create --from` / `machine start` don't use them: `SMOLVM_LIB_DIR` must still point at the private lib dir from 02/06, or the stock kernel boots and Android never starts.

| | |
|---|---|
| Registry | `ghcr.io/savindaa/smolvm-android:16-gplay` (private package) |
| Contents | `redroid/redroid@sha256:e194edc9…` + one layer: `/init` wrapper, busybox, `gpu_config.sh`, `gpu_gralloc`/`gpu_egl`, `battery_fixed.rc`, `vulkan.virtio.so` (Mesa 26.1.8), `gralloc.venus.so`, MindTheGapps 16.0.0 20261023 minus SetupWizard |
| Defaults | 8 vCPU, 4096 MiB, GPU, network, `/init qemu=1 androidboot.hardware=redroid androidboot.redroid_gpu_mode=guest androidboot.use_memfd=1 androidboot.redroid_fps=60` |
| Size | 1.1 GB |
| Built with | smolvm 1.36.1 |

## Start a machine from it

```sh
# private package: a GitHub token with read:packages
gh auth refresh -h github.com -s read:packages
cat >> ~/.config/smolvm/config.toml <<'EOF'
[machines.registries."ghcr.io"]
username = "<github user>"
password_env = "GHCR_TOKEN"
EOF

export GHCR_TOKEN=$(gh auth token)
smolvm pack pull ghcr.io/savindaa/smolvm-android:16-gplay -o android16-gplay.smolmachine
export SMOLVM_LIB_DIR=<private lib dir from 02, with the 06 kernel>
smolvm machine create --name android16 --from android16-gplay.smolmachine --gpu --net -p 5558:5555
smolvm machine start --name android16
adb connect 127.0.0.1:5558
```

`[machines.registries]` is the section `pack push`/`pack pull` read; `[images.registries]` only covers container images.

Use `machine create --from` and `machine start`. The pack's own launcher (`./android16-gplay start`) boots the VM but does not run the Android entrypoint.

Each machine gets its own device ID on first boot: register it (08 §4) before signing in to the Play Store.

## Checks (M3 Pro, fresh machine from the pulled file)

| Check | Result |
|---|---|
| boot to `sys.boot_completed` | ~8 s |
| SurfaceFlinger | `ANGLE (Apple, Vulkan 1.1.334 (Virtio-GPU Venus (Apple M3 Pro) (0x1A060209)), venus-26.1.8)` |
| battery | AC powered, present, level 100 |
| packages | `com.android.vending`, `com.google.android.gms`, `com.google.android.gsf`, `com.android.provision`; no SetupWizard; `user_setup_complete=1` |
| Play Store | opens to the sign-in screen |
| pulled file | byte-identical to the pushed file |

## Rebuild and publish

Inputs: the two guest libraries from 03 and 04, an arm64 busybox (07), the MindTheGapps zip (08), and the private lib dir from 02/06 (the pack bundles whatever `SMOLVM_LIB_DIR` points at).

```sh
mise exec aqua:google/go-containerregistry -- crane version   # installs crane
CRANE=$(mise where aqua:google/go-containerregistry)/crane
mkdir guest && cp vulkan.virtio.so gralloc.venus.so busybox guest/
uv run image/build-image.py --gapps MindTheGapps-16.0.0-arm64-20261023_034858.zip \
  --guest guest --crane "$CRANE" -o android16-gplay.tar

export SMOLVM_LIB_DIR=<private lib dir>
smolvm pack create --smolfile image/Smolfile --image android16-gplay.tar --gpu -o android16-gplay
GHCR_TOKEN=$(gh auth token) smolvm pack push -f android16-gplay.smolmachine ghcr.io/<user>/smolvm-android:16-gplay
```

Pushing needs `write:packages` (`gh auth refresh -h github.com -s write:packages`). A new GHCR package is private.

`build-image.py` writes the layer with root ownership and only adds directory entries for directories the base image lacks ([image/base-dirs-16.txt](../image/base-dirs-16.txt)), so the base keeps its own owners (several `/vendor` directories are group 2000). The base is pinned by digest; a new base needs a new directory list.

The package stays private: it contains Google's apps, which Google does not license for redistribution.
