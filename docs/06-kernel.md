# 06 · Kernel (libkrunfw fork)

Android 15/16 needs kernel features that the libkrunfw 6.18.60 kernel bundled with smolvm 1.36.1 lacks. Without them, Android 16 netd crash-loops and boot never completes:

```
Kernel eBPF JIT failure ... CRITICAL FAILURE LOADING BPF PROGRAMS
Failed to get program from /sys/fs/bpf/netd_shared/prog_netd_skfilter_allowlist_xtbpf
```

Fork: https://github.com/savindaa/libkrunfw, branch `android-bpf` (based on `smol-machines/libkrunfw` `2e1a130`, the rev bundled with smolvm 1.36.1). Commits: `0be4e79` (eBPF, netfilter, ashmem shim), `d8b9d75` (socket diagnostics, IPsec, remaining netd options).

## What the branch changes

| Area | Options / patch | Why |
|---|---|---|
| eBPF | `BPF_JIT`, `BPF_JIT_ALWAYS_ON`, `CGROUP_BPF`, `NET_CLS_BPF`, `NET_ACT_BPF`, `NETFILTER_XT_MATCH_BPF` | netd and bpfloader treat a missing JIT as fatal on 16 |
| netfilter | xt matches/targets netd installs (`OWNER`, `SOCKET`, `QUOTA`, `CONNMARK`, `MARK`, `TCPMSS`, `IDLETIMER`, `CT`, `POLICY`, rpfilter), IPv6 filter/mangle/raw | netd's iptables chains |
| socket diagnostics | `INET_DIAG`, `INET_TCP_DIAG`, `INET_UDP_DIAG`, `INET_RAW_DIAG`, `INET_DIAG_DESTROY` | netd's socket destroy on network change (`ss -K`) |
| IPsec / IPv6 | `XFRM_USER`, `XFRM_INTERFACE`, `INET_ESP`, `INET6_ESP`, `IPV6_ROUTER_PREF`, `IPV6_ROUTE_INFO`, `IPV6_OPTIMISTIC_DAD` | netd's XfrmController, Android base config |
| block | `BLK_DEV_WRITE_MOUNTED`, dm-verity | apexd mounts APEX images through loop devices it holds open |
| shared memory | patch `0065` (port of android-mainline `mm/memfd-ashmem-shim.c`) | libcutils only uses memfd when `ASHMEM_GET_SIZE` works on a memfd; fixes the Android 16 screen-capture bug (redroid-doc #869/#862) |
| misc | `IKCONFIG` | `/proc/config.gz` for checking the running kernel |

## Build

The kernel builds natively for arm64 in a throwaway smolvm machine; the dylib wrapper is compiled on macOS. No Homebrew, no krunvm.

```sh
git clone -b android-bpf https://github.com/savindaa/libkrunfw.git $WORK/libkrunfw-src
mkdir -p $WORK/kb
```

`$WORK/kb/build.sh` (runs inside the build machine):

```sh
#!/bin/sh
set -e
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq build-essential flex bison bc libelf-dev libssl-dev python3 python3-pyelftools xz-utils cpio perl curl rsync >/dev/null
mkdir -p /build
rsync -a --delete --exclude 'linux-6.18.60/' --exclude kernel.c /src/ /build/
cd /build
make -j"$(nproc)" kernel.c > /build/make.log 2>&1 || { tail -60 /build/make.log; exit 1; }
cp linux-6.18.60/.config /kb/config.out
cp kernel.c /kb/kernel.c
ls -la /kb/kernel.c
```

Build the kernel bundle (`kernel.c`), then delete the machine:

```sh
smolvm machine create --name krunfw-builder --image ubuntu:24.04 --net --cpus 6 --mem 6144 --storage 40 \
  -v $WORK/libkrunfw-src:/src -v $WORK/kb:/kb
smolvm machine start --name krunfw-builder
smolvm machine exec --name krunfw-builder -- sh /kb/build.sh
smolvm machine stop --name krunfw-builder
smolvm machine delete --name krunfw-builder --force
```

Check the options landed: `grep -E '^CONFIG_(BPF_JIT|INET_DIAG_DESTROY|XFRM_USER)=' $WORK/kb/config.out`.

Compile the wrapper on macOS (same install name smolvm's bundled copy uses, so libkrun loads it from `SMOLVM_LIB_DIR`):

```sh
cd $WORK/kb
MACOSX_DEPLOYMENT_TARGET=11.0 cc -fPIC -DABI_VERSION=5 -shared -o libkrunfw.5.dylib kernel.c \
  -Wl,-install_name,/opt/homebrew/opt/smolvm/libexec/lib/libkrunfw.5.dylib
codesign -f -s - libkrunfw.5.dylib
otool -D libkrunfw.5.dylib
```

## Install

Swap it into the private lib dir only while no machine using that dir is running; the running VMM maps the dylib, so never overwrite it in place.

```sh
cp $WORK/klib/libkrunfw.5.dylib $WORK/klib-libkrunfw-prev.dylib
cp $WORK/kb/libkrunfw.5.dylib $WORK/klib/libkrunfw.5.dylib.new
mv -f $WORK/klib/libkrunfw.5.dylib.new $WORK/klib/libkrunfw.5.dylib
```

## Verify (inside Android, untested as written)

```sh
adb -s 127.0.0.1:5557 shell 'ls /proc/sys/net/core/bpf_jit_enable; zcat /proc/config.gz | grep -E "CONFIG_(BPF_JIT|INET_DIAG_DESTROY)="'
adb -s 127.0.0.1:5557 shell getprop sys.boot_completed
adb -s 127.0.0.1:5557 shell 'su 0 ss -K dst 192.0.2.1; echo $?'
```

With the kernel in place, the libkrun `bdev_allow_write_mounted` command-line workaround is no longer needed. The Android 16 init wrapper (loop device nodes, writable `/sys`) still is; see [07](07-android16.md).
