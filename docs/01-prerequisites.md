# 01 · Prerequisites

| Need | Version used | How |
|---|---|---|
| Mac | Apple Silicon (tested M3 Pro, 18 GB) | — |
| smolvm | 1.36.1 | official installer / release |
| Xcode command line tools | — | `xcode-select --install` (clang, install_name_tool, codesign, otool) |
| Rust | 1.95.0 (1.94 fails on unstable `atomic_try_update`) | `rustup toolchain install 1.95.0 && rustup target add aarch64-unknown-linux-musl --toolchain 1.95.0` |
| uv | any | meson, ninja, mako, pkgconf go into uv venvs |
| Android NDK | r28c (darwin) | downloaded with sha256 check by `scripts/android-gpu/env.sh` in the smolvm fork |
| adb, scrcpy | any | for viewing |

No Homebrew installs: toolchains go through rustup, uv, mise or plain downloads into a work dir (`$WORK` below).

```sh
export WORK=$HOME/smolvm-android-work   # any scratch dir
```
