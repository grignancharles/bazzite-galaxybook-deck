# Pling Server Linux (2D Ultra-Low Latency for Meta Quest)

Native Linux implementation of the Pling Streaming Server, specially engineered for **Intel Iris Xe Graphics (Tiger Lake Gen12 VA-API)** on **Bazzite / SteamOS / Fedora**.

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
|   Video Pipeline        | |   Audio Pipeline        | |   Input Injection       |
|  - Intel Iris Xe VA-API | |  - PipeWire pw-record   | |  - /dev/uinput          |
|  - KMS Zero-Copy Grab   | |  - PCM Float32LE Stereo | |  - Touch -> Left/Right  |
|  - hevc_vaapi CBR       | |  - 48000 Hz Continuous  | |  - Scroll -> REL_WHEEL  |
|  - NAL Unit Framing     | |  - 20ms Frame Chunks    | |  - macOS Keycode Trans  |
+-------------------------+ +-------------------------+ +-------------------------+
```

---

## Wire Protocol Specifications

The server communicates over **TCP port 3000** using binary frames framed with the anchor byte `0xAA`:

```
[0xAA (1 Byte)] [Packet Type (1 Byte)] [Payload Size (4 Bytes LE)] [Payload (N Bytes)]
```

### Packet Types

| Type | Direction | Name | Payload Structure |
|------|-----------|------|-------------------|
| `0x06` | Server -> Quest | **Video Frame** | Annex B HEVC (H.265) NAL units with start codes `00 00 00 01` (VPS/SPS/PPS/IDR/P-slices). *Note: `0x00` is also supported via `--video-type 0`.* |
| `0x01` | Server -> Quest | **Audio Frame** | Raw PCM Float32 Little-Endian Stereo @ 48,000 Hz. Streamed continuously to prevent pops/clicks. |
| `0x02` | Server -> Quest | **KeepAlive** | Empty payload (0 bytes). |
| `0x04` | Server -> Quest | **2D Control** | 27 bytes: `enabled=0` (1B), 14B reserved, `intensity=0.0` (4B), `gamma=1.0` (4B), `saturation=1.0` (4B). Disables 3D depth. |
| `0x07` | Quest -> Server | **IDR Request** | 0 bytes payload. Forces immediate encoder IDR keyframe generation. |
| `0x08` | Quest -> Server | **Flow ACK** | 16 bytes: `bytesAcked` (8B uint64 LE) + `echoTimestamp` (8B float64 LE). Used for RTT & congestion window. |
| `0x09` | Server -> Quest | **RTT Probe** | 8 bytes float64 LE send timestamp. Quest echoes this back inside packet `0x08`. |
| `0x06` | Quest -> Server | **Touch/Mouse** | 9 bytes: `action` (1B) + `nx` (4B float32 LE) + `ny` (4B float32 LE). |
| `0x0A` | Quest -> Server | **Keyboard** | `kind` (1B: `0`=UTF-8 string, `1`=macOS virtual keycode) + `data` (N Bytes). |

### Touch Action Codes

- `0`: **Tap** -> Moves cursor to `(nx, ny)`, triggers `BTN_LEFT` Down + Up.
- `1`: **Long Press** -> Moves cursor to `(nx, ny)`, triggers `BTN_RIGHT` Down + Up.
- `2`: **Scroll** -> Normalized `(nx, ny)` deltas mapped to `REL_WHEEL` and `REL_HWHEEL`.
- `3`: **Drag Start** -> Moves cursor to `(nx, ny)`, triggers `BTN_LEFT` Down.
- `4`: **Drag Move** -> Moves cursor to `(nx, ny)` with `BTN_LEFT` held.
- `5`: **Drag End** -> Triggers `BTN_LEFT` Up.
- `6`: **Hover / Move** -> Cursor move without click.

---

## Hardware Optimization (Tiger Lake Iris Xe)

- **Hardware Encoder**: `hevc_vaapi` via `/dev/dri/renderD128` (Intel QuickSync Gen12).
- **Direct KMS Grab**: Grabs DRM framebuffers directly from `/dev/dri/card0` into VA-API with **zero memory copy** between CPU and GPU.
- **PipeWire / Portal Grab**: Full Wayland support for Gamescope and KDE Plasma desktop sessions.
- **CBR & Zero-Latency**: Configured with `-tune zerolatency`, `-bf 0`, and small slice buffers for sub-8ms local encoding latency.

---

## USB Tethering (0ms Jitter Mode)

When Meta Quest is connected via USB-C:
1. Pling Server automatically detects the device via `adb`.
2. Sets up `adb reverse tcp:3000 tcp:3000`.
3. Activates **God Mode** optimizations on Quest (`cpu_level 5`, `gpu_level 5`, sharpening enabled).
4. Quest connects over `127.0.0.1:3000` with 0ms network jitter and maximum bitrate (up to 70-80 Mbps).

---

## System Tray Mini-App

The system tray widget (`pling-tray`) sits in the KDE Plasma / Bazzite panel next to brightness and volume:
- **Live Indicator**:
  - ⚪ Offline
  - 🟡 Waiting for Quest connection
  - 🟢 Connected & Streaming
- **Real-Time Tooltip**: Shows active link (USB / Wi-Fi), IP address, RTT in ms, bitrate, and FPS.
- **Quick Controls**:
  - One-click Toggle Streaming (Start / Stop)
  - Bitrate selector (15, 25, 35, 50, 70 Mbps)
  - Audio stream toggle (PipeWire)
  - Refresh Screen (Force IDR keyframe)
- **Desktop Notifications**: Alerts when Quest connects or disconnects.

---

## Installation & Usage

### Standalone Installation
```bash
sudo ./install.sh
```

### Run Server in Background
```bash
pling-server serve --bitrate 35 --fps 60
```

### Launch System Tray Mini-App
```bash
pling-tray &
```

### CLI Control (Scripting & Automation)
```bash
# Check status
pling-ctl status

# Set bitrate
pling-ctl bitrate 50

# Force keyframe
pling-ctl keyframe

# Toggle audio
pling-ctl audio off
```
