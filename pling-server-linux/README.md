# Pling Server Linux (Ultra-Low Latency Meta Quest Streaming)

Native Linux port of the **Pling Streaming Server**, specifically optimized for **Intel Iris Xe Graphics (Tiger Lake Gen12)** on **Bazzite / SteamOS / Fedora / Arch / Ubuntu**.

Ported directly from the original Mac macOS code (`ContentView.swift`) and Meta Quest client (`PlingQuestAndroid`), reproducing identical wire protocol, rate control, sliders, and audio pipelines — with 3D depth disabled (2D pure ultra-low latency).

---

## Architecture Overview

```
                      +---------------------------------------+
                      |       Meta Quest 2 / 3 / Pro / 3S     |
                      |  PlingClient.kt (Android MediaCodec)  |
                      +-------------------+-------------------+
                                          |
                        TCP 3000 (Stream) | UDP 7001 (Discovery)
                                          |
                      +-------------------+-------------------+
                      |          Pling Server Linux           |
                      +---------------------------------------+
                     /                   |                     \
                    /                    |                      \
+-------------------------+ +-------------------------+ +-------------------------+
|     Video Pipeline      | |     Audio Pipeline      | |     Input Injection     |
|  - Intel Iris Xe VA-API | |  - PipeWire pw-record   | |  - /dev/uinput          |
|  - Intel QSV (oneVPL)   | |  - PCM Float32LE Stereo | |  - Touch -> Left/Right  |
|  - x264 / x265 fallback | |  - 48000 Hz Continuous  | |  - Scroll -> REL_WHEEL  |
|  - KMS Zero-Copy Grab   | |  - Realtime Volume Gain | |  - macOS Keycode Trans  |
|  - Dynamic AIMD Bitrate | |  - Zero POP/Click buffer| |  - Virtual VR Keyboard  |
+-------------------------+ +-------------------------+ +-------------------------+
```

---

## Comparison: Mac Original vs Linux Tiger Lake Port

| Feature | Original Mac (`ContentView.swift`) | Linux Port (`pling-server-linux`) |
|---------|------------------------------------|-----------------------------------|
| **Video Encoder** | Apple VideoToolbox (`VTCompressionSession` HEVC) | **Intel VA-API (`hevc_vaapi`) & QSV (`hevc_qsv`)** hardware acceleration + `libx265`/`libx264` CPU fallback |
| **Screen Capture** | Apple `ScreenCaptureKit` | **KMS Direct Framebuffer Zero-Copy Grab (`kmsgrab`)**, X11 (`x11grab`), & PipeWire |
| **Dynamic Bitrate** | AIMD (Additive Increase, Multiplicative Decrease via ACKs) | **Exact AIMD Flow Control algorithm**: In-flight limit (~70ms), frame drop before encoding, smoothed RTT |
| **Resolution Presets** | Stepper: 720p, 1080p, 1440p, 2160p (Native) | **Identical Stepper**: 720p, 1080p, 1440p, 2160p with even-pixel rounding & aspect-ratio preservation |
| **FPS Cap** | [25, 30, 60] | **[25, 30, 60]** |
| **Color Sliders** | Saturation (0.0–2.0), Gamma (0.5–5.0) | **Identical Sliders**: Sent in real-time via packet `0x04` to update Quest shaders |
| **Audio Pipeline** | CoreAudio Float32 @ 48kHz, 0.15x gain boost | **PipeWire / PulseAudio Float32LE @ 48kHz**, volume gain boost (0.0x–10.0x) |
| **Input Injection** | `CGEvent` (macOS HID tap) | **/dev/uinput virtual device** + `xdotool`/`ydotool` fallback |
| **VR Keyboard** | AXUIElement text focus monitor & typing | **/dev/uinput virtual keyboard** (UTF-8 text + macOS virtual keycode translation) |
| **USB Tethering** | Bundled `adb reverse tcp:3000 tcp:3000` + God Mode | **Automatic `adb reverse` monitor + God Mode** (CPU/GPU lvl 5, sharpening, prox sensor) |
| **Discovery** | UDP Broadcast on 7001 (`MAC_SERVER:<ip>:3000`) | **Identical UDP Broadcast on 7001** (`MAC_SERVER:<ip>:3000`) targeting LAN & iPhone hotspot range |
| **3D Model** | CoreML Depth Anything v2 | *Excluded* (exclusive to Mac; Linux operates in pure 2D ultra-low latency) |

---

## Wire Protocol Specifications

The server communicates over **TCP port 3000** using binary frames framed with the anchor byte `0xAA`:

```
[0xAA (1 Byte)] [Packet Type (1 Byte)] [Payload Size (4 Bytes LE)] [Payload (N Bytes)]
```

### Packet Types

| Type | Direction | Name | Payload Structure |
|------|-----------|------|-------------------|
| `0x06` | Server -> Quest | **HEVC Video** | Annex B HEVC NAL units with start codes `00 00 00 01` (VPS/SPS/PPS/IDR/P-slices). Parameter sets cached and prepended to all keyframes. |
| `0x01` | Server -> Quest | **Audio Frame** | Raw PCM Float32 Little-Endian Stereo @ 48,000 Hz. Scaled with volume boost multiplier. |
| `0x02` | Server -> Quest | **KeepAlive** | Heartbeat frame (0 bytes payload). |
| `0x04` | Server -> Quest | **2D Control** | 27-byte control packet: `enabled=0` (1B), `fps` (1B), `width` (2B), `height` (2B), `depth_w` (2B), `depth_h` (2B), `aspect` (4B), `whiteNear` (1B), `intensity` (4B), `gamma` (4B), `saturation` (4B). PlingQuestAndroid reads intensity, gamma, saturation to configure shaders. |
| `0x07` | Quest -> Server | **IDR Request** | 0 bytes payload. Requests immediate IDR keyframe generation when decoder initializes. |
| `0x08` | Quest -> Server | **Flow ACK** | 16 bytes: `bytesAcked` (8B uint64 LE) + `echoTimestamp` (8B float64 LE). Used to calculate in-flight bytes, RTT, and drive AIMD rate controller. |
| `0x09` | Server -> Quest | **RTT Probe** | 8 bytes float64 LE send timestamp. Quest echoes this back inside packet `0x08`. |
| `0x06` | Quest -> Server | **Touch/Mouse** | 9 bytes: `action` (1B) + `nx` (4B float32 LE) + `ny` (4B float32 LE). |
| `0x0A` | Quest -> Server | **Keyboard** | `kind` (1B: `0`=UTF-8 text, `1`=macOS virtual keycode) + `data` (N Bytes). |

---

## Hardware Optimization (Tiger Lake Iris Xe)

- **Hardware Encoder**: `hevc_vaapi` via `/dev/dri/renderD128` (Intel QuickSync Gen12) or `hevc_qsv`.
- **Direct KMS Grab**: Grabs DRM framebuffers directly from `/dev/dri/card0` into VA-API with **zero memory copy** between CPU and GPU.
- **CBR & Zero-Latency**: Configured with `-tune zerolatency`, `-bf 0`, and small slice buffers for sub-8ms local encoding latency.

---

## USB Tethering (0ms Jitter Mode)

When Meta Quest is connected via USB-C:
1. Pling Server automatically detects the device via `adb`.
2. Sets up `adb reverse tcp:3000 tcp:3000`.
3. Activates **God Mode** optimizations on Quest (`cpu_level 5`, `gpu_level 5`, sharpening enabled).
4. Quest connects over `127.0.0.1:3000` with 0ms network jitter and maximum bitrate (up to 70-80 Mbps).
5. When disconnected, Pling Server automatically restores Quest defaults.

---

## Installation & Offline Deployment

### 100% Offline Installation via `install-all-in-one.sh`
The repository installer `install-all-in-one.sh` installs Pling Server completely offline:
- Copies Python modules to `/usr/local/share/pling`
- Creates `/usr/local/bin/pling-server`, `pling-ctl`, `pling-tray`
- Installs `/etc/udev/rules.d/99-pling-uinput.rules`
- Enables and starts `pling-server.service` via systemd

### Standalone Installer
```bash
sudo ./install.sh
```

---

## CLI Control (`pling-ctl`)

Full scriptable and interactive control utility:

```bash
# View formatted server and link status (RTT, Bitrate, FPS, Quest IP, Sliders)
pling-ctl status

# View raw JSON status
pling-ctl status --json

# Set bitrate (e.g. 35 Mbps) or switch to Auto AIMD flow control
pling-ctl bitrate 35
pling-ctl bitrate auto

# Set FPS Cap (25, 30, 60)
pling-ctl fps 60

# Set resolution preset height (720, 1080, 1440, 2160)
pling-ctl resolution 1080

# Adjust Color Sliders (sent live to Meta Quest shader)
pling-ctl gamma 1.2
pling-ctl saturation 1.1

# Adjust Volume Boost multiplier (0.0 to 10.0x)
pling-ctl volume 1.5

# Switch Hardware Encoder on the fly
pling-ctl encoder vaapi   # Intel VA-API Tiger Lake Gen12
pling-ctl encoder qsv     # Intel Quick Sync
pling-ctl encoder x265    # Software CPU fallback

# Toggle PipeWire desktop audio streaming
pling-ctl audio off
pling-ctl audio on

# Force immediate IDR Keyframe
pling-ctl keyframe

# Stream control
pling-ctl stop
pling-ctl start
pling-ctl restart
```
