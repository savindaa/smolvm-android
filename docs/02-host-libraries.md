# 02 · Host libraries

The installed smolvm is never modified. A private copy of its lib dir gets the patched `libkrun.dylib` and `libvirglrenderer.1.dylib`, and `SMOLVM_LIB_DIR` points at it.

| Library | Patch | Why |
|---|---|---|
| libkrun (rutabaga) | `patches/libkrun/0001` | Apple blob handles carry no fd (-1); `try_clone` tried to dup it and failed |
| virglrenderer 0.10.4e-krunkit | upstream smolvm `0001-macos-venus-bridge` + `0002`, `0003` | share exported memory across contexts by host pointer; keep it alive until the last unref; page-round host-pointer imports |
| libepoxy 1.5.10 | none, built from source | virglrenderer dependency |

## libkrun

Ran in this project (session build, from the libkrun fork, branch `v1.36.1-apple-blob`):

```sh
git clone -b v1.36.1-apple-blob https://github.com/savindaa/libkrun $WORK/libkrun && cd $WORK/libkrun
# pkg-config must answer for virglrenderer + epoxy; point it at the built libs/headers
LIBCLANG_PATH=/Library/Developer/CommandLineTools/usr/lib \
CARGO_TARGET_AARCH64_UNKNOWN_LINUX_MUSL_LINKER=rust-lld \
CARGO_TARGET_AARCH64_UNKNOWN_LINUX_MUSL_RUSTFLAGS="-C linker-flavor=ld.lld -C link-self-contained=yes -C link-arg=--strip-debug" \
PATH=$HOME/.rustup/toolchains/1.95.0-aarch64-apple-darwin/lib/rustlib/aarch64-apple-darwin/bin:$PATH \
cargo +1.95.0 build --release --features blk,net,gpu,input
```

Output: `target/release/libkrun.dylib` (or `$CARGO_TARGET_DIR/release/`).

## virglrenderer + libepoxy

Scripted in the smolvm fork (untested end to end; the session ran the equivalent meson commands by hand):

```sh
cd smolvm   # android-gpu branch
uv venv target/android-gpu/host-venv
uv pip install --python target/android-gpu/host-venv/bin/python meson ninja pkgconf
PATH="$PWD/target/android-gpu/host-venv/bin:$PATH" SKIP_DEPS=1 \
  VULKAN_HEADERS="$PWD/target/android-gpu/mesa" \
  OUT="$PWD/target/android-gpu/host/libvirglrenderer.1.dylib" \
  scripts/build-virglrenderer-macos.sh
```

Session-run equivalent (meson flags that produced the tested lib):

```sh
meson setup $W/virgl-build $VIRGL_SRC -Dvenus=true -Drender-server=false -Dbuildtype=release
meson compile -C $W/virgl-build
```

with `PKG_CONFIG_PATH=$W/epoxy-prefix/lib/pkgconfig`, `CFLAGS="-mmacosx-version-min=11.0 -I<mesa>/include"` (Vulkan headers), `LDFLAGS="-mmacosx-version-min=11.0 -L<smolvm lib dir>"` (MoltenVK).

## Private lib dir

```sh
LIBKRUN=$WORK/libkrun/target/release/libkrun.dylib \
VIRGL=target/android-gpu/host/libvirglrenderer.1.dylib \
  scripts/android-gpu/install-host-libs.sh
export SMOLVM_LIB_DIR="$PWD/target/android-gpu/lib"
```

What the script does (all ran in the session):

| Step | Command |
|---|---|
| copy installed lib dir | `cp -R <smolvm>/libexec/lib/. $SMOLVM_LIB_DIR/` |
| keep the original install name | `install_name_tool -id /opt/homebrew/opt/smolvm/libexec/lib/<lib> <lib>` |
| resolve siblings locally | `install_name_tool -change <abs path>/libMoltenVK.dylib @loader_path/libMoltenVK.dylib` (same for libepoxy, libvirglrenderer) |
| re-sign | `codesign -f -s - <lib>` |

Check: `otool -L $SMOLVM_LIB_DIR/libvirglrenderer.1.dylib` shows only `@loader_path/` and system deps.
