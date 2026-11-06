"""
Command-Line Interface and Control Utility for Pling Server Linux.
Provides CLI daemon execution and IPC remote control for 'pling-server' and 'pling-ctl'.
"""

import os
import sys
import json
import socket
import argparse
import logging
from pling.config import PlingConfig, HEIGHT_OPTIONS, FPS_OPTIONS
from pling.server import PlingServer

def send_ipc_command(sock_path: str, cmd_dict: dict, timeout: float = 2.0) -> dict:
    if not os.path.exists(sock_path):
        return {"status": "error", "message": f"Pling Server is not running (no socket at {sock_path})"}
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect(sock_path)
        s.sendall(json.dumps(cmd_dict).encode("utf-8"))
        res = s.recv(8192).decode("utf-8")
        s.close()
        return json.loads(res)
    except Exception as e:
        return {"status": "error", "message": str(e)}

def print_formatted_status(data: dict):
    if data.get("status") == "error":
        print(f"❌ Error: {data.get('message')}")
        return

    print("═════════════════════════════════════════════════════════════")
    print("🎮 PLING SERVER LINUX (TIGER LAKE GEN12)")
    print("═════════════════════════════════════════════════════════════")
    running = "🟢 ACTIVE" if data.get("running") else "🔴 STOPPED"
    print(f" Status:          {running}")
    print(f" Link Status:     {data.get('link_status', 'N/A')}")
    print(f" Connected Quest: {data.get('clients_count', 0)} device(s)")
    if data.get("clients"):
        for i, c in enumerate(data["clients"]):
            link = "USB Cable (Low Latency)" if c["is_usb"] else "Wi-Fi"
            print(f"   [{i+1}] {c['ip']}:{c['port']} via {link} | RTT: {c['rtt_ms']}ms | In-flight: {c['in_flight_kb']}KB")

    print("─────────────────────────────────────────────────────────────")
    print(f" Resolution:      {data.get('resolution')} (Height: {data.get('target_height')}p)")
    print(f" Framerate:       {data.get('fps')} FPS (Cap: {data.get('fps_cap')} FPS)")
    print(f" Bitrate:         {data.get('bitrate_mbps')} Mbps (Mode: {data.get('bitrate_mode', 'auto')})")
    print(f" Video Encoder:   {data.get('encoder')} ({data.get('capture_mode')})")
    print(f" Desktop Audio:   {'🔊 Enabled (PipeWire)' if data.get('audio_enabled') else '🔇 Disabled'}")
    print(f" Input Injection: {'✓ /dev/uinput ready' if data.get('uinput_ready') else '✗ Fallback mode'}")
    print("─────────────────────────────────────────────────────────────")
    print(f" Gamma Slider:    {data.get('gamma')} (Range: 0.5 - 5.0)")
    print(f" Saturation:      {data.get('saturation')} (Range: 0.0 - 2.0)")
    print(f" Volume Boost:    {data.get('volume_boost')}x (Range: 0.0 - 10.0x)")
    print("═════════════════════════════════════════════════════════════")

def main():
    parser = argparse.ArgumentParser(
        prog="pling-server / pling-ctl",
        description="Pling Server Linux - Native Meta Quest 2D Ultra-Low Latency Streaming"
    )
    subparsers = parser.add_subparsers(dest="action")

    # 1. SERVE (Daemon mode)
    serve_parser = subparsers.add_parser("serve", help="Run the streaming server daemon")
    serve_parser.add_argument("--port", type=int, default=3000, help="TCP listening port (default: 3000)")
    serve_parser.add_argument("--target-height", type=int, choices=HEIGHT_OPTIONS, default=1080, help="Target height preset (720, 1080, 1440, 2160)")
    serve_parser.add_argument("--fps", type=int, choices=FPS_OPTIONS, default=60, help="FPS cap (25, 30, 60)")
    serve_parser.add_argument("--bitrate", type=float, default=20.0, help="HEVC bitrate in Mbps (default: 20)")
    serve_parser.add_argument("--bitrate-mode", choices=["auto", "manual"], default="auto", help="Bitrate control: 'auto' (AIMD flow control) or 'manual'")
    serve_parser.add_argument("--encoder", choices=["auto", "vaapi", "qsv", "x265", "x264"], default="auto", help="Video encoder pipeline")
    serve_parser.add_argument("--capture-mode", choices=["auto", "kms", "pipewire", "x11"], default="auto", help="Display capture mechanism")
    serve_parser.add_argument("--gamma", type=float, default=1.0, help="Gamma slider (0.5 to 5.0)")
    serve_parser.add_argument("--saturation", type=float, default=1.0, help="Saturation slider (0.0 to 2.0)")
    serve_parser.add_argument("--volume-boost", type=float, default=1.0, help="Volume boost multiplier (0.0 to 10.0)")
    serve_parser.add_argument("--no-audio", action="store_true", help="Disable PipeWire desktop audio streaming")
    serve_parser.add_argument("--no-adb", action="store_true", help="Disable ADB USB auto-bridge")
    serve_parser.add_argument("--debug", action="store_true", help="Enable verbose debug logging")

    # 2. STATUS
    status_parser = subparsers.add_parser("status", help="Get status of running Pling server")
    status_parser.add_argument("--json", action="store_true", help="Output raw JSON format")

    # 3. BITRATE
    br_parser = subparsers.add_parser("bitrate", help="Set bitrate or enable auto AIMD control")
    br_parser.add_argument("value", help="Bitrate in Mbps (e.g. '25') or 'auto'")

    # 4. FPS
    fps_parser = subparsers.add_parser("fps", help="Set FPS cap")
    fps_parser.add_argument("value", type=int, choices=FPS_OPTIONS, help="Framerate cap (25, 30, 60)")

    # 5. RESOLUTION
    res_parser = subparsers.add_parser("resolution", help="Set target height resolution")
    res_parser.add_argument("value", type=int, choices=HEIGHT_OPTIONS, help="Target height (720, 1080, 1440, 2160)")

    # 6. SLIDERS: GAMMA, SATURATION, VOLUME
    g_parser = subparsers.add_parser("gamma", help="Set gamma slider (0.5 .. 5.0)")
    g_parser.add_argument("value", type=float, help="Gamma float value")

    s_parser = subparsers.add_parser("saturation", help="Set saturation slider (0.0 .. 2.0)")
    s_parser.add_argument("value", type=float, help="Saturation float value")

    v_parser = subparsers.add_parser("volume", help="Set volume boost multiplier (0.0 .. 10.0)")
    v_parser.add_argument("value", type=float, help="Volume multiplier float value")

    # 7. ENCODER
    enc_parser = subparsers.add_parser("encoder", help="Switch video encoder")
    enc_parser.add_argument("value", choices=["auto", "vaapi", "qsv", "x265", "x264"], help="Encoder name")

    # 8. AUDIO
    audio_parser = subparsers.add_parser("audio", help="Toggle PipeWire audio streaming")
    audio_parser.add_argument("state", choices=["on", "off"], help="Audio on or off")

    # 9. KEYFRAME & STREAM CONTROLS
    subparsers.add_parser("keyframe", help="Force immediate IDR keyframe")
    subparsers.add_parser("stop", help="Pause screen streaming")
    subparsers.add_parser("start", help="Resume screen streaming")
    subparsers.add_parser("restart", help="Restart streaming pipeline")

    args = parser.parse_args()
    config = PlingConfig.load()

    # If invoked with no action, default to 'status' if server is up, else show help
    if not args.action:
        if os.path.exists(config.ipc_socket_path):
            res = send_ipc_command(config.ipc_socket_path, {"command": "status"})
            print_formatted_status(res)
            return
        else:
            parser.print_help()
            return

    # Handle IPC Commands
    if args.action == "status":
        res = send_ipc_command(config.ipc_socket_path, {"command": "status"})
        if getattr(args, "json", False):
            print(json.dumps(res, indent=2))
        else:
            print_formatted_status(res)
        return

    elif args.action == "bitrate":
        res = send_ipc_command(config.ipc_socket_path, {"command": "set_bitrate", "value": args.value})
        print(json.dumps(res, indent=2))
        return

    elif args.action == "fps":
        res = send_ipc_command(config.ipc_socket_path, {"command": "set_fps", "value": args.value})
        print(json.dumps(res, indent=2))
        return

    elif args.action == "resolution":
        res = send_ipc_command(config.ipc_socket_path, {"command": "set_resolution", "value": args.value})
        print(json.dumps(res, indent=2))
        return

    elif args.action == "gamma":
        res = send_ipc_command(config.ipc_socket_path, {"command": "set_gamma", "value": args.value})
        print(json.dumps(res, indent=2))
        return

    elif args.action == "saturation":
        res = send_ipc_command(config.ipc_socket_path, {"command": "set_saturation", "value": args.value})
        print(json.dumps(res, indent=2))
        return

    elif args.action == "volume":
        res = send_ipc_command(config.ipc_socket_path, {"command": "set_volume_boost", "value": args.value})
        print(json.dumps(res, indent=2))
        return

    elif args.action == "encoder":
        res = send_ipc_command(config.ipc_socket_path, {"command": "set_encoder", "value": args.value})
        print(json.dumps(res, indent=2))
        return

    elif args.action == "audio":
        res = send_ipc_command(config.ipc_socket_path, {"command": "toggle_audio", "enabled": args.state == "on"})
        print(json.dumps(res, indent=2))
        return

    elif args.action == "keyframe":
        res = send_ipc_command(config.ipc_socket_path, {"command": "force_keyframe"})
        print(json.dumps(res, indent=2))
        return

    elif args.action == "stop":
        res = send_ipc_command(config.ipc_socket_path, {"command": "stop_stream"})
        print(json.dumps(res, indent=2))
        return

    elif args.action == "start":
        res = send_ipc_command(config.ipc_socket_path, {"command": "start_stream"})
        print(json.dumps(res, indent=2))
        return

    elif args.action == "restart":
        res = send_ipc_command(config.ipc_socket_path, {"command": "restart"})
        print(json.dumps(res, indent=2))
        return

    # Handle SERVE command
    if args.action == "serve":
        log_level = logging.DEBUG if args.debug else logging.INFO
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S"
        )

        config.tcp_port = args.port
        config.target_height = args.target_height
        config.fps = args.fps
        config.bitrate_mbps = args.bitrate
        config.bitrate_mode = args.bitrate_mode
        config.encoder = args.encoder
        config.capture_mode = args.capture_mode
        config.gamma = args.gamma
        config.saturation = args.saturation
        config.volume_boost = args.volume_boost
        config.audio_enabled = not args.no_audio
        config.auto_adb = not args.no_adb

        server = PlingServer(config)
        if not server.start():
            sys.exit(1)

        try:
            import time
            while server.is_running:
                time.sleep(1.0)
        except KeyboardInterrupt:
            print("\nShutting down Pling Server...")
        finally:
            server.stop()

if __name__ == "__main__":
    main()
