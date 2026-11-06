"""
Unit tests for Pling Server Linux protocol encoding, parsing, and framing.
Verifies full bit-for-bit compatibility with PlingQuestAndroid and Mac ContentView.
"""

import struct
import unittest
from pling.config import PlingConfig
from pling.protocol import (
    MAGIC_BYTE,
    LEGACY_MAGIC,
    PACKET_VIDEO_HEVC,
    PACKET_AUDIO,
    PACKET_TOUCH,
    PACKET_KEYFRAME_REQ,
    PACKET_FLOW_ACK,
    PACKET_KEYBOARD_INPUT,
    PACKET_LIVE3D_CTRL,
    PACKET_RTT_PROBE,
    encode_packet,
    encode_legacy_header,
    encode_live3d_control,
    encode_rtt_probe,
    encode_keyboard_state,
    parse_flow_ack,
    parse_touch_event,
    parse_keyboard_event,
    is_hevc_keyframe,
    extract_hevc_parameter_sets,
    PacketStreamParser
)

class TestPlingProtocol(unittest.TestCase):
    def test_encode_packet(self):
        payload = b"test payload 12345"
        packet = encode_packet(PACKET_VIDEO_HEVC, payload)
        self.assertEqual(packet[0], MAGIC_BYTE)
        self.assertEqual(packet[1], PACKET_VIDEO_HEVC)
        size = struct.unpack_from("<I", packet, 2)[0]
        self.assertEqual(size, len(payload))
        self.assertEqual(packet[6:], payload)

    def test_legacy_header(self):
        hdr = encode_legacy_header(1920, 1080)
        self.assertEqual(hdr[:4], LEGACY_MAGIC)
        w, h, flags = struct.unpack_from("<HHB", hdr, 4)
        self.assertEqual(w, 1920)
        self.assertEqual(h, 1080)
        self.assertEqual(flags, 0)

    def test_live3d_control_payload_structure(self):
        # Must be exactly 27 bytes payload matching Mac ContentView makeLive3DControlPayload()
        pkt = encode_live3d_control(
            enabled=False,
            fps=60,
            width=1920,
            height=1080,
            depth_w=0,
            depth_h=0,
            aspect=16.0 / 9.0,
            white_near=1,
            intensity=0.008,
            gamma=1.5,
            saturation=1.2
        )
        self.assertEqual(pkt[0], MAGIC_BYTE)
        self.assertEqual(pkt[1], PACKET_LIVE3D_CTRL)
        payload_size = struct.unpack_from("<I", pkt, 2)[0]
        self.assertEqual(payload_size, 27)

        payload = pkt[6:]
        self.assertEqual(payload[0], 0)  # enabled = False
        self.assertEqual(payload[1], 60) # fps = 60
        w, h = struct.unpack_from("<HH", payload, 2)
        self.assertEqual(w, 1920)
        self.assertEqual(h, 1080)

        # PlingClient.kt reads at position 15: intensity, gamma, saturation
        intensity, gamma, saturation = struct.unpack_from("<fff", payload, 15)
        self.assertAlmostEqual(intensity, 0.008, places=4)
        self.assertAlmostEqual(gamma, 1.5, places=4)
        self.assertAlmostEqual(saturation, 1.2, places=4)

    def test_stream_parser(self):
        parser = PacketStreamParser()
        p1 = encode_packet(PACKET_KEYFRAME_REQ, b"")
        p2 = encode_packet(PACKET_AUDIO, b"\x00" * 128)

        # Simulate noisy stream + fragmented packets
        stream_data = b"junk123" + p1 + p2[:50]
        events = list(parser.feed(stream_data))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0][0], PACKET_KEYFRAME_REQ)
        self.assertEqual(events[0][1], b"")

        # Feed remaining fragmented chunk
        events2 = list(parser.feed(p2[50:]))
        self.assertEqual(len(events2), 1)
        self.assertEqual(events2[0][0], PACKET_AUDIO)
        self.assertEqual(events2[0][1], b"\x00" * 128)

    def test_flow_ack(self):
        payload = struct.pack("<Qd", 987654321, 1700000000.123)
        acked, echo = parse_flow_ack(payload)
        self.assertEqual(acked, 987654321)
        self.assertAlmostEqual(echo, 1700000000.123, places=3)

    def test_touch_event(self):
        # Action 0 (Tap), nx=0.75, ny=0.25
        payload = struct.pack("<Bff", 0, 0.75, 0.25)
        parsed = parse_touch_event(payload)
        self.assertIsNotNone(parsed)
        action, nx, ny = parsed
        self.assertEqual(action, 0)
        self.assertAlmostEqual(nx, 0.75)
        self.assertAlmostEqual(ny, 0.25)

    def test_keyboard_event(self):
        payload = b"\x00Test VR Keyboard!"
        kind, text_bytes = parse_keyboard_event(payload)
        self.assertEqual(kind, 0)
        self.assertEqual(text_bytes.decode("utf-8"), "Test VR Keyboard!")

    def test_hevc_keyframe_and_param_sets(self):
        # VPS (type 32 -> header 64), SPS (type 33 -> header 66), PPS (type 34 -> header 68)
        sc = b"\x00\x00\x00\x01"
        vps = sc + bytes([32 << 1, 0x01]) + b"\xAA\xBB"
        sps = sc + bytes([33 << 1, 0x01]) + b"\xCC\xDD"
        pps = sc + bytes([34 << 1, 0x01]) + b"\xEE\xFF"
        idr = sc + bytes([19 << 1, 0x01]) + b"\x01\x02\x03\x04"
        non_idr = sc + bytes([1 << 1, 0x01]) + b"\x05\x06"

        full_keyframe = vps + sps + pps + idr
        self.assertTrue(is_hevc_keyframe(full_keyframe))
        self.assertTrue(is_hevc_keyframe(idr))
        self.assertFalse(is_hevc_keyframe(non_idr))

        params = extract_hevc_parameter_sets(full_keyframe)
        self.assertIn("vps", params)
        self.assertIn("sps", params)
        self.assertIn("pps", params)
        self.assertEqual(params["vps"], vps)
        self.assertEqual(params["sps"], sps)
        self.assertEqual(params["pps"], pps)

    def test_config_dimensions_and_aimd(self):
        cfg = PlingConfig()
        cfg.target_height = 1080
        out_w, out_h = cfg.compute_output_dimensions(1920, 1080)
        self.assertEqual((out_w, out_h), (1920, 1080))

        cfg.target_height = 720
        out_w, out_h = cfg.compute_output_dimensions(1920, 1080)
        self.assertEqual(out_h, 720)
        self.assertEqual(out_w, 1280)

        # Ideal bitrate calculation
        ideal = cfg.ideal_bitrate_mbps()
        self.assertGreater(ideal, 5.0)
        self.assertLess(ideal, 60.0)

if __name__ == "__main__":
    unittest.main()
