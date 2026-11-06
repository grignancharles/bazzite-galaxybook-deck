"""
Wire protocol implementation for Pling Quest <-> Server streaming.
Full bit-for-bit compatibility with PlingQuestAndroid (PlingClient.kt) and Pling server v2 (ContentView.swift).
"""

import struct
from typing import Generator, Tuple, Optional, Dict

# Protocol Anchors & Magic Bytes
MAGIC_BYTE = 0xAA
LEGACY_MAGIC = b"PLNG"

# Server -> Quest Packet Types
PACKET_VIDEO_COMPAT = 0x00   # Legacy video H.264/JPEG compat
PACKET_AUDIO = 0x01          # PCM Float32LE Stereo 48kHz
PACKET_KEEPALIVE = 0x02      # Empty keepalive packet (heartbeat)
PACKET_LIVE3D_CTRL = 0x04    # Color / Resolution / 3D control packet (27 bytes)
PACKET_DEPTH_RAW = 0x05      # Legacy depth map (disabled in 2D Linux mode)
PACKET_VIDEO_HEVC = 0x06     # Hardware HEVC (H.265) Annex B NAL units
PACKET_DEPTH_COMPR = 0x08    # Compressed depth map (disabled in 2D Linux mode)
PACKET_RTT_PROBE = 0x09      # RTT timestamp probe (8 bytes float64 LE)
PACKET_KEYBOARD_STATE = 0x0A # Virtual keyboard state (1 byte: 1 visible, 0 hidden)

# Quest -> Server Packet Types
PACKET_TOUCH = 0x06          # Action (1B) + nx (4B) + ny (4B) = 9 bytes
PACKET_KEYFRAME_REQ = 0x07   # Request immediate IDR keyframe (0 bytes payload)
PACKET_FLOW_ACK = 0x08       # Flow control ACK: bytesAcked (8B) + echoTs (8B) = 16 bytes
PACKET_KEYBOARD_INPUT = 0x0A # Kind (1B) + Data (NB)

# Touch actions (RemoteTouchView.kt)
TOUCH_ACTION_TAP = 0         # Left click
TOUCH_ACTION_LONG_PRESS = 1  # Right click
TOUCH_ACTION_SCROLL = 2      # Scroll wheel deltas
TOUCH_ACTION_DRAG_START = 3  # Left mouse button down
TOUCH_ACTION_DRAG_MOVE = 4   # Left mouse button dragged
TOUCH_ACTION_DRAG_END = 5    # Left mouse button up
TOUCH_ACTION_MOVE = 6        # Cursor hover / move without click

# Keyboard input kinds
KEYBOARD_KIND_TEXT = 0       # UTF-8 string
KEYBOARD_KIND_KEYCODE = 1    # macOS virtual keycode (1 byte)


def encode_packet(packet_type: int, payload: bytes = b"") -> bytes:
    """
    Wraps payload in standard Pling packet:
    [0xAA (1B)][Type (1B)][Size (4B LE)][Payload (NB)]
    """
    header = struct.pack("<BBI", MAGIC_BYTE, packet_type, len(payload))
    return header + payload


def encode_legacy_header(width: int, height: int, flags: int = 0) -> bytes:
    """
    Initial 'PLNG' handshake header sent immediately upon connection:
    ['PLNG' (4B)][width (2B LE)][height (2B LE)][flags (1B)]
    """
    w = max(0, min(65535, int(width)))
    h = max(0, min(65535, int(height)))
    return LEGACY_MAGIC + struct.pack("<HHB", w, h, flags)


def encode_live3d_control(
    enabled: bool = False,
    fps: int = 60,
    width: int = 1920,
    height: int = 1080,
    depth_w: int = 0,
    depth_h: int = 0,
    aspect: float = 16.0 / 9.0,
    white_near: int = 1,
    intensity: float = 0.0,
    gamma: float = 1.0,
    saturation: float = 1.0
) -> bytes:
    """
    Encodes the 27-byte control payload (Packet Type 0x04) matching Mac ContentView.swift:
    - enabled (1 byte uint8)
    - fps (1 byte uint8)
    - vw (2 bytes uint16 LE)
    - vh (2 bytes uint16 LE)
    - dw (2 bytes uint16 LE)
    - dh (2 bytes uint16 LE)
    - aspect (4 bytes float32 LE)
    - whiteNear (1 byte uint8)
    - intensity (4 bytes float32 LE)
    - gamma (4 bytes float32 LE)
    - saturation (4 bytes float32 LE)

    PlingQuestAndroid (PlingClient.kt) reads:
    - enabled at offset 0
    - intensity at offset 15
    - gamma at offset 19
    - saturation at offset 23
    """
    payload = bytearray(27)
    payload[0] = 1 if enabled else 0
    payload[1] = max(1, min(255, int(fps)))
    struct.pack_into("<HH", payload, 2, max(0, min(65535, width)), max(0, min(65535, height)))
    struct.pack_into("<HH", payload, 6, max(0, min(65535, depth_w)), max(0, min(65535, depth_h)))
    struct.pack_into("<f", payload, 10, float(aspect))
    payload[14] = int(white_near) & 0xFF
    struct.pack_into("<fff", payload, 15, float(intensity), float(gamma), float(saturation))
    return encode_packet(PACKET_LIVE3D_CTRL, bytes(payload))


def encode_rtt_probe(timestamp: float) -> bytes:
    """
    Encodes an RTT timestamp probe (packet type 0x09) with 8-byte double LE.
    The Quest client echoes this timestamp back in packet type 0x08.
    """
    return encode_packet(PACKET_RTT_PROBE, struct.pack("<d", float(timestamp)))


def encode_keyboard_state(visible: bool) -> bytes:
    """
    Encodes virtual keyboard visibility state (packet type 0x0A): 1 = show, 0 = hide.
    """
    return encode_packet(PACKET_KEYBOARD_STATE, b"\x01" if visible else b"\x00")


def parse_flow_ack(payload: bytes) -> Tuple[int, float]:
    """
    Parses Flow ACK (type 0x08).
    Returns (bytes_acked: int, echo_timestamp: float)
    """
    if len(payload) < 8:
        return 0, 0.0
    bytes_acked = struct.unpack_from("<Q", payload, 0)[0]
    echo_ts = 0.0
    if len(payload) >= 16:
        echo_ts = struct.unpack_from("<d", payload, 8)[0]
    return bytes_acked, echo_ts


def parse_touch_event(payload: bytes) -> Optional[Tuple[int, float, float]]:
    """
    Parses Touch packet (type 0x06).
    Payload must be 9 bytes: action (uint8), nx (float32 LE), ny (float32 LE).
    """
    if len(payload) < 9:
        return None
    action = payload[0]
    nx, ny = struct.unpack_from("<ff", payload, 1)
    return action, nx, ny


def parse_keyboard_event(payload: bytes) -> Optional[Tuple[int, bytes]]:
    """
    Parses Keyboard input packet (type 0x0A).
    Payload: kind (uint8) + data (remaining bytes).
    kind 0: UTF-8 text string
    kind 1: 1-byte virtual keycode
    """
    if len(payload) < 2:
        return None
    kind = payload[0]
    data = payload[1:]
    return kind, data


def is_hevc_keyframe(nal_data: bytes) -> bool:
    """
    Inspects Annex B H.265 bitstream for IDR / IRAP / VPS / SPS / PPS NAL units.
    NAL Unit Types in HEVC:
    19: IDR_W_RADL (Keyframe)
    20: IDR_N_LP (Keyframe)
    32: VPS
    33: SPS
    34: PPS
    """
    idx = 0
    length = len(nal_data)
    while idx + 4 < length:
        if nal_data[idx] == 0 and nal_data[idx + 1] == 0:
            offset = 0
            if nal_data[idx + 2] == 1:
                offset = idx + 3
            elif idx + 3 < length and nal_data[idx + 2] == 0 and nal_data[idx + 3] == 1:
                offset = idx + 4

            if 0 < offset < length:
                nal_header = nal_data[offset]
                nal_type = (nal_header >> 1) & 0x3F
                if nal_type in (19, 20, 32, 33, 34):
                    return True
                idx = offset
                continue
        idx += 1
    return False


def extract_hevc_parameter_sets(nal_data: bytes) -> Dict[str, bytes]:
    """
    Extracts VPS, SPS, and PPS NAL units from an Annex B HEVC bitstream.
    Returns dictionary with keys 'vps', 'sps', 'pps'.
    """
    params: Dict[str, bytes] = {}
    idx = 0
    length = len(nal_data)
    start_indices = []

    # Find all start codes
    while idx + 3 < length:
        if nal_data[idx] == 0 and nal_data[idx + 1] == 0:
            if nal_data[idx + 2] == 1:
                start_indices.append((idx, idx + 3))
                idx += 3
                continue
            elif idx + 3 < length and nal_data[idx + 2] == 0 and nal_data[idx + 3] == 1:
                start_indices.append((idx, idx + 4))
                idx += 4
                continue
        idx += 1

    for i, (sc_start, nalu_start) in enumerate(start_indices):
        sc_end = start_indices[i + 1][0] if i + 1 < len(start_indices) else length
        if nalu_start < sc_end:
            nal_header = nal_data[nalu_start]
            nal_type = (nal_header >> 1) & 0x3F
            nalu_bytes = nal_data[sc_start:sc_end]
            if nal_type == 32:
                params["vps"] = nalu_bytes
            elif nal_type == 33:
                params["sps"] = nalu_bytes
            elif nal_type == 34:
                params["pps"] = nalu_bytes

    return params


class PacketStreamParser:
    """
    Streaming packet parser that buffers incoming TCP chunks,
    locates 0xAA anchor byte, validates header length and payload bounds,
    and yields complete (packet_type, payload) frames.
    """
    def __init__(self, max_payload: int = 15_000_000):
        self._buffer = bytearray()
        self._max_payload = max_payload

    def feed(self, chunk: bytes) -> Generator[Tuple[int, bytes], None, None]:
        self._buffer.extend(chunk)

        while len(self._buffer) >= 6:
            # 1. Search for magic byte 0xAA
            try:
                magic_idx = self._buffer.index(MAGIC_BYTE)
            except ValueError:
                self._buffer.clear()
                break

            # Discard noise before magic byte
            if magic_idx > 0:
                del self._buffer[:magic_idx]

            if len(self._buffer) < 6:
                break

            # 2. Parse packet header: Magic(1) + Type(1) + Size(4 LE)
            packet_type = self._buffer[1]
            payload_size = struct.unpack_from("<I", self._buffer, 2)[0]

            # Sanity check size
            if payload_size > self._max_payload:
                del self._buffer[:1]
                continue

            total_packet_len = 6 + payload_size
            if len(self._buffer) < total_packet_len:
                break

            # 3. Extract payload
            payload = bytes(self._buffer[6:total_packet_len])
            del self._buffer[:total_packet_len]

            yield packet_type, payload
