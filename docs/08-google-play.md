# 08 · Google Play

MindTheGapps added by hand to the running Android 16 machine (stock `redroid/redroid:16.0.0_64only-latest` plus the kernel from [06](06-kernel.md) and the machine setup from [07](07-android16.md)). No source build.

| Version | Package | sha256 |
|---|---|---|
| 16 (tested) | `MindTheGapps-16.0.0-arm64-20261023_034858.zip` from https://github.com/MindTheGapps/16.0.0-arm64/releases | verified OK against the release `.sha256sum` |
| 15 (untested) | `MindTheGapps-15.0.0-arm64-20260915_032013.zip` from https://github.com/MindTheGapps/15.0.0-arm64/releases | verified OK |

The package holds `system/product/{app,etc,framework,lib64,overlay,priv-app}` and `system/system_ext/{etc,priv-app}`; no 32-bit libs, so it fits the 64only image. In the Redroid rootfs `/product` and `/system_ext` are symlinks to `/system/product` and `/system/system_ext`, and the root is a writable overlay, so the trees extract straight into `/system`.

## 1. Stage the files (Mac)

```sh
Z=MindTheGapps-16.0.0-arm64-20261023_034858.zip
R=https://github.com/MindTheGapps/16.0.0-arm64/releases/download/${Z%.zip}
curl -LO "$R/$Z" -LO "$R/$Z.sha256sum"
shasum -a 256 -c "$Z.sha256sum"
mkdir gapps16 && cd gapps16 && unzip -q "../$Z"
mkdir stage && cp -R system/product system/system_ext stage/
# Google's SetupWizard is dropped and AOSP Provision kept: MindTheGapps' installer only removes
# Provision when SetupWizard is installed, so this pair is a supported combination and skips the wizard.
rm -rf stage/system_ext/priv-app/SetupWizard
cd stage
find . -type d -exec chmod 755 {} +
find . -type f -exec chmod 644 {} +
COPYFILE_DISABLE=1 tar --uid 0 --gid 0 --uname root --gname root --no-mac-metadata \
  -cf ../gapps16.tar product system_ext
cd ../..
```

The installer's own rules (from `META-INF/com/google/android/update-binary`): dirs 0755, files 0644 (0755 only for `.sh` or extension-less files; the 16.0.0 package has none), owner root, and `rm -rf system_ext/priv-app/Provision` only when SetupWizard is present.

## 2. Install into the machine

```sh
export SMOLVM_LIB_DIR=$WORK/klib
smolvm machine cp --mode 644 gapps16/gapps16.tar redroid16gpu:/data/local/tmp/gapps16.tar
smolvm machine exec --name redroid16gpu -- sh -c \
  'cd /system && tar -xpf /data/local/tmp/gapps16.tar && rm /data/local/tmp/gapps16.tar'
smolvm machine stop --name redroid16gpu
smolvm machine start --name redroid16gpu
```

No boot-arg change needed: with Provision kept, `device_provisioned` and `user_setup_complete` are both `1` after boot.

## 3. Verify

```sh
A="adb -s 127.0.0.1:5557"
$A shell getprop sys.boot_completed                       # 1
$A shell pm list packages | grep -E 'vending|google.android.gms$|gsf$'
$A shell am start -W -n com.android.vending/com.google.android.finsky.activities.MainActivity
$A shell dumpsys SurfaceFlinger | grep GLES                # ANGLE ... Virtio-GPU Venus (Apple M3 Pro)
```

Expected on first boot: GMS crashes 2–3 times within seconds with `IllegalArgumentException: Unexpected safety source: AdvancedProtection` (newer GMS registers a Safety Center source the Android 16 r2 platform config doesn't define), then stays up. The Play Store opens to its sign-in flow.

## 4. Device registration (uncertified device)

Current GMS keeps Gservices in its own data dir; the GSF path from older guides no longer exists.

```sh
adb root
adb shell 'sqlite3 /data/user/0/com.google.android.gms/databases/gservices.db \
  "select value from main where name = \"android_id\";"'
```

Register that decimal value at https://www.google.com/android/uncertified (Google sign-in), wait for it to apply (can take hours), then restart the machine and sign in to the Play Store.

## Result (Android 16, M3 Pro)

Sign-in, device registration and installing Brave from the Play Store all work.

## Limits

| Limit | Why |
|---|---|
| banking, wallet, many games, DRM apps refuse or hide | Play Integrity needs a locked bootloader and hardware-backed attestation since May 2025 (https://developer.android.com/google/play/integrity/improvements) |
| 32-bit-only ARM apps | 64only image; Apple M-series likely lacks AArch32 (unverified) |
| Play Store video previews may crash SurfaceFlinger on YV12 | seen on Redroid 15 (redroid-doc #942); untested here |
