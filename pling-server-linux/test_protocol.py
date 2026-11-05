"""
Unit tests for Pling protocol encoding, parsing, and framing.
"""

import struct
import unittest
from pling.protocol import (
    MAGIC_BYTE,
    PACKET_VIDEO_HEVC,
    PACKET_AUDIO,
    PACKET_TOUCH,
    PACKET_KEYFRAME_REQ,
    PACKET_FLOW_ACK,
    PACKET_KEYBOARD_INPUT,
    encode_packet,
    encode_legacy_header,
    encode_live3d_control,
    encode_rtt_probe,
    parse_flow_ack,
    parse_touch_event,
    parse_keyboard_event,
    is_hevc_keyframe,
    PacketStreamParser
)

class TestPlingProtocol(unittest.TestCase):
    def test_encode_packet(self):
        payload = b"hello pling"
        packet = encode_packet(PACKET_VIDEO_HEVC, payload)
        self.assertEqual(packet[0], MAGIC_BYTE)
        self.assertEqual(packet[1], PACKET_VIDEO_HEVC)
        size = struct.unpack_from("<I", packet, 2)[0]
        self.assertEqual(size, len(payload))
        self.assertEqual(packet[6:], payload)

    def test_legacy_header(self):
        hdr = encode_legacy_header(1920, 1080)
        self.assertEqual(hdr[:4], b"PLNG")
        w, h, flags = struct.unpack_from("<HHB", hdr, 4)
        self.assertEqual(w, 1920)
        self.assertEqual(h, 1080)
        self.assertEqual(flags, 0)

    def test_stream_parser(self):
        parser = PacketStreamParser()
        p1 = encode_packet(PACKET_KEYFRAME_REQ, b"")
        p2 = encode_packet(PACKET_AUDIO, b"\x00" * 128)
        
        # Test split across multiple TCP chunks and leading junk noise
        stream_data = b"junk123" + p1 + p2[:50]
        events = list(parser.feed(stream_data))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0][0], PACKET_KEYFRAME_REQ)
        self.assertEqual(events[0][1], b"")

        # Feed remaining chunk
        events2 = list(parser.feed(p2[50:]))
        self.assertEqual(len(events2), 1)
        self.assertEqual(events2[0][0], PACKET_AUDIO)
        self.assertEqual(events2[0][1], b"\x00" * 128)

    def test_flow_ack(self):
        payload = struct.pack("<Qd", 12345678, 1234.5678)
        acked, echo = parse_flow_ack(payload)
        self.assertEqual(acked, 12345678)
        self.assertAlmostEqual(echo, 1234.5678)

    def test_touch_event(self):
        # Action 0 (Tap), nx=0.5, ny=0.25
        payload = struct.pack("<Bff", 0, 0.5, 0.25)
        parsed = parse_touch_event(payload)
        self.assertIsNotNone(parsed)
        action, nx, ny = parsed
        self.assertEqual(action, 0)
        self.assertAlmostEqual(nx, 0.5)
        self.assertAlmostEqual(ny, 0.25)

    def test_keyboard_event(self):
        payload = b"\x00Hello Quest!"
        kind, text_bytes = parse_keyboard_event(payload)
        self.assertEqual(kind, 0)
        self.assertEqual(text_bytes.decode("utf-8"), "Hello Quest!")

    def test_hevc_keyframe_detection(self):
        # VPS NAL type = 32 -> header = (32 << 1) = 64
        vps_nal = b"\x00\x00\x00\x01" + bytes([32 << 1, 0x01]) + b"\x12\x34"
        # Non-IDR slice NAL type = 1 -> header = (1 << 1) = 2
        p_nal = b"\x00\x00\x00\x01" + bytes([1 << 1, 0x01]) + b"\x56\x78"

        self.assertTrue(is_hevc_keyframe(vps_nal))
        self.assertFalse(is_hevc_keyframe(p_nal))

if __name__ == "__main__":
    unittest.main()
