# 10 · Smooth trackpad scrolling in scrcpy

## What

A patched `scrcpy-server` 5.0.1 that re-times scroll events onto display frames. It works with the stock scrcpy 5.0.1 client: the client pushes the server you point it at.

## Why

Trackpad scrolling in the scrcpy window judders. It isn't tearing: 0 torn frames were found in any run below.

- Android batches and resamples touch moves to the display frame, but it delivers each `ACTION_SCROLL` as is (`InputConsumer.cpp:317-318`, `571-572`).
- The scrcpy client sends scroll deltas at an irregular ~120 Hz, and the adb forward bunches them further. So 0 to 3 events land in each 16.7 ms frame, and the content moves e.g. 19, 54, 34 px on consecutive frames.

The patch adds a `ScrollSmoother` to the server:

- It accumulates the incoming deltas with their arrival time.
- On every `Choreographer` frame, it injects the cumulative position averaged over the last 24 ms (about 12 ms behind the input). Each event is therefore spread over the frames its window overlaps.
- The total injected always equals the total received: once the window has passed the last event, the target is the exact total. There's no drift, and a stopped gesture flushes within 2 frames.
- It's on by default. Opt out with the server option `scroll_smoothing=false`.

A plain linear interpolation of the input (12 ms behind) was tried first. It left about 9% of frames off, because bunched arrivals collapse the interpolation interval.

## Results (Android 16, 720x1280, Settings, scripted 120 Hz trackpad gesture over the scrcpy control socket, 10 s per run)

"Off" means a moving frame whose displacement is more than 40% off the mean of its two neighbours. It's measured from the video stream by cross-correlating row profiles.

| Run | off | tears | frame interval p50/p90 | gfxinfo jank, p50/p90/p99 |
|---|---|---|---|---|
| stock, 4 runs | 708 / 2182 (32.4%) | 0 | 16.7 / 17.5–18.5 ms | 0.00%, 5/5/5 ms |
| patched, 4 runs | 27 / 2247 (1.2%) | 0 | 16.7 / 17.8–18.4 ms | ≤0.17%, 5/5/5 ms |
| patched, `scroll_smoothing=false` | 182 / 559 (32.6%) | 0 | 16.7 / 17.8 ms | 0.00%, 5/5/5 ms |

The remaining off frames in patched runs come from hitting the end of the list, or from a single pipeline hiccup (one 37 ms frame).

## Build

The steps below need the Android SDK (platform 36, build-tools 35.0.0) and a JDK; any recent JDK works with `-source 1.8`.

```sh
git clone --depth 1 --branch v5.0.1 https://github.com/Genymobile/scrcpy.git scrcpy-src
cd scrcpy-src
git apply <smolvm-android checkout>/scrcpy/scroll-smoothing.patch
mkdir -p ../scrcpy-smooth
cd server
ANDROID_HOME=$HOME/Library/Android/sdk ANDROID_PLATFORM=36 ANDROID_BUILD_TOOLS=35.0.0 \
  BUILD_DIR=$PWD/../../scrcpy-smooth ./build_without_gradle.sh
# -> ../../scrcpy-smooth/scrcpy-server
```

The server version must match the client (`5.0.1`), so build from the tag that matches the installed client.

## Run

```sh
SCRCPY_SERVER_PATH=/path/to/scrcpy-smooth/scrcpy-server \
  scrcpy -s 127.0.0.1:5557 --window-title 'redroid16gpu (Android 16, GPU)' --max-fps 60 --no-audio
```

To compare with stock behaviour, the client can't pass arbitrary server options. Run the stock client without `SCRCPY_SERVER_PATH` instead.

<details>
<summary>scroll-smoothing.patch (against v5.0.1)</summary>

```diff
diff --git a/server/src/main/java/com/genymobile/scrcpy/Options.java b/server/src/main/java/com/genymobile/scrcpy/Options.java
index 26a6ba9..483a041 100644
--- a/server/src/main/java/com/genymobile/scrcpy/Options.java
+++ b/server/src/main/java/com/genymobile/scrcpy/Options.java
@@ -60,6 +60,7 @@ public class Options {
     private String audioEncoder;
     private boolean powerOffScreenOnClose;
     private boolean clipboardAutosync = true;
+    private boolean scrollSmoothing = true;
     private boolean downsizeOnError = true;
     private boolean cleanup = true;
     private boolean powerOn = true;
@@ -235,6 +236,10 @@ public class Options {
         return clipboardAutosync;
     }
 
+    public boolean getScrollSmoothing() {
+        return scrollSmoothing;
+    }
+
     public boolean getDownsizeOnError() {
         return downsizeOnError;
     }
@@ -459,6 +464,9 @@ public class Options {
                 case "clipboard_autosync":
                     options.clipboardAutosync = Boolean.parseBoolean(value);
                     break;
+                case "scroll_smoothing":
+                    options.scrollSmoothing = Boolean.parseBoolean(value);
+                    break;
                 case "downsize_on_error":
                     options.downsizeOnError = Boolean.parseBoolean(value);
                     break;
diff --git a/server/src/main/java/com/genymobile/scrcpy/control/Controller.java b/server/src/main/java/com/genymobile/scrcpy/control/Controller.java
index 55d6e11..3255161 100644
--- a/server/src/main/java/com/genymobile/scrcpy/control/Controller.java
+++ b/server/src/main/java/com/genymobile/scrcpy/control/Controller.java
@@ -94,6 +94,7 @@ public class Controller implements AsyncProcessor, VirtualDisplayListener {
     private final boolean clipboardAutosync;
     private final boolean powerOn;
     private final boolean keepActive;
+    private final ScrollSmoother scrollSmoother;
 
     private final KeyCharacterMap charMap = KeyCharacterMap.load(KeyCharacterMap.VIRTUAL_KEYBOARD);
 
@@ -125,6 +126,7 @@ public class Controller implements AsyncProcessor, VirtualDisplayListener {
             this.clipboardAutosync = false;
             this.powerOn = false;
             this.keepActive = false;
+            this.scrollSmoother = null;
             return;
         }
 
@@ -133,6 +135,7 @@ public class Controller implements AsyncProcessor, VirtualDisplayListener {
         this.clipboardAutosync = options.getClipboardAutosync();
         this.powerOn = options.getPowerOn();
         this.keepActive = options.getKeepActive();
+        this.scrollSmoother = options.getScrollSmoothing() ? new ScrollSmoother() : null;
         initPointers();
         sender = new DeviceMessageSender(controlChannel);
 
@@ -631,6 +634,11 @@ public class Controller implements AsyncProcessor, VirtualDisplayListener {
         Point point = pair.first;
         int targetDisplayId = pair.second;
 
+        if (scrollSmoother != null) {
+            scrollSmoother.add(point, targetDisplayId, hScroll, vScroll, buttons);
+            return true;
+        }
+
         MotionEvent.PointerProperties props = pointerProperties[0];
         props.id = 0;
 
diff --git a/server/src/main/java/com/genymobile/scrcpy/control/ScrollSmoother.java b/server/src/main/java/com/genymobile/scrcpy/control/ScrollSmoother.java
new file mode 100644
index 0000000..690eef2
--- /dev/null
+++ b/server/src/main/java/com/genymobile/scrcpy/control/ScrollSmoother.java
@@ -0,0 +1,176 @@
+package com.genymobile.scrcpy.control;
+
+import com.genymobile.scrcpy.device.Device;
+import com.genymobile.scrcpy.model.Point;
+import com.genymobile.scrcpy.util.Ln;
+
+import android.os.Looper;
+import android.os.SystemClock;
+import android.view.Choreographer;
+import android.view.InputDevice;
+import android.view.MotionEvent;
+
+/**
+ * Re-times scroll events onto display frames.
+ * <p>
+ * Android batches and resamples touch moves per frame, but delivers each ACTION_SCROLL as is. Trackpad scrolling from the client arrives at an
+ * irregular ~120 Hz, and the adb forward bunches them further, so 0 to 3 events land in each frame and the content jumps unevenly. This injects,
+ * once per frame, the cumulative scroll position averaged over a short trailing window (about 12 ms behind the input), so every event is spread
+ * over the frames its window overlaps. The total injected always equals the total received.
+ */
+public final class ScrollSmoother implements Choreographer.FrameCallback {
+
+    private static final long WINDOW_NS = 24_000_000;
+    private static final int HISTORY = 256;
+
+    private final Object lock = new Object();
+    private final long[] times = new long[HISTORY];
+    private final double[] cumH = new double[HISTORY];
+    private final double[] cumV = new double[HISTORY];
+    private int head; // index of the oldest sample
+    private int count;
+
+    private double totalH;
+    private double totalV;
+    private double sentH;
+    private double sentV;
+
+    private Point point;
+    private int displayId;
+    private int buttons;
+
+    private Choreographer choreographer;
+    private boolean scheduled;
+
+    private final MotionEvent.PointerProperties[] props = {new MotionEvent.PointerProperties()};
+    private final MotionEvent.PointerCoords[] coords = {new MotionEvent.PointerCoords()};
+
+    public ScrollSmoother() {
+        props[0].id = 0;
+        props[0].toolType = MotionEvent.TOOL_TYPE_MOUSE;
+        coords[0].orientation = 0;
+        coords[0].size = 0;
+        Thread thread = new Thread(() -> {
+            Looper.prepare();
+            synchronized (lock) {
+                choreographer = Choreographer.getInstance();
+                lock.notifyAll();
+            }
+            Looper.loop();
+        }, "scroll-smoother");
+        thread.setDaemon(true);
+        thread.start();
+    }
+
+    public void add(Point point, int displayId, float hScroll, float vScroll, int buttons) {
+        long now = System.nanoTime();
+        synchronized (lock) {
+            if (!scheduled) {
+                // Idle, so everything before is sent: restart the history from the current total
+                count = 0;
+                push(now - 1, totalH, totalV);
+            }
+            totalH += hScroll;
+            totalV += vScroll;
+            push(now, totalH, totalV);
+            this.point = point;
+            this.displayId = displayId;
+            this.buttons = buttons;
+            if (!scheduled) {
+                while (choreographer == null) {
+                    try {
+                        lock.wait();
+                    } catch (InterruptedException e) {
+                        Thread.currentThread().interrupt();
+                        return;
+                    }
+                }
+                scheduled = true;
+                choreographer.postFrameCallback(this);
+            }
+        }
+    }
+
+    @Override
+    public void doFrame(long frameTimeNanos) {
+        double dh;
+        double dv;
+        Point p;
+        int display;
+        int btns;
+        synchronized (lock) {
+            long t = Math.min(frameTimeNanos, System.nanoTime());
+            double h = average(cumH, t, totalH);
+            double v = average(cumV, t, totalV);
+            dh = h - sentH;
+            dv = v - sentV;
+            sentH = h;
+            sentV = v;
+            p = point;
+            display = displayId;
+            btns = buttons;
+            if (sentH == totalH && sentV == totalV) {
+                scheduled = false;
+            } else {
+                choreographer.postFrameCallback(this);
+            }
+        }
+        if (dh != 0 || dv != 0) {
+            inject(p, display, (float) dh, (float) dv, btns);
+        }
+    }
+
+    private void inject(Point p, int display, float h, float v, int btns) {
+        long now = SystemClock.uptimeMillis();
+        coords[0].x = p.getX();
+        coords[0].y = p.getY();
+        coords[0].setAxisValue(MotionEvent.AXIS_HSCROLL, h);
+        coords[0].setAxisValue(MotionEvent.AXIS_VSCROLL, v);
+        MotionEvent event = MotionEvent.obtain(now, now, MotionEvent.ACTION_SCROLL, 1, props, coords, 0, btns, 1f, 1f, 0, 0,
+                InputDevice.SOURCE_MOUSE, 0);
+        if (!Device.injectEvent(event, display, Device.INJECT_MODE_ASYNC)) {
+            Ln.w("Could not inject smoothed scroll event");
+        }
+    }
+
+    private long lastTime() {
+        return times[(head + count - 1) % HISTORY];
+    }
+
+    private void push(long t, double h, double v) {
+        int i;
+        if (count < HISTORY) {
+            i = (head + count) % HISTORY;
+            ++count;
+        } else {
+            i = head;
+            head = (head + 1) % HISTORY;
+        }
+        times[i] = t;
+        cumH[i] = h;
+        cumV[i] = v;
+    }
+
+    // Mean of the cumulative position (a step function) over [t - WINDOW, t]; once the window has passed the newest sample it is the exact total,
+    // so input that stops is flushed without drift.
+    private double average(double[] cum, long t, double total) {
+        long from = t - WINDOW_NS;
+        if (from >= lastTime()) {
+            return total;
+        }
+        double area = 0;
+        for (int k = 0; k < count; ++k) {
+            int i = (head + k) % HISTORY;
+            long start = Math.max(times[i], from);
+            long end = k + 1 < count ? Math.min(times[(head + k + 1) % HISTORY], t) : t;
+            if (end > start) {
+                area += cum[i] * (end - start);
+            }
+        }
+        long firstTime = times[head];
+        if (firstTime > from) {
+            area += cum[head] * (Math.min(firstTime, t) - from);
+        }
+        return area / WINDOW_NS;
+    }
+}
```

</details>
