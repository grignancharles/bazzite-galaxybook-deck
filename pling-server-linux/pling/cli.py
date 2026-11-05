"""
Command-Line Interface and Runner for Pling Server Linux.
"""

import os
import sys
import json
import socket
import argparse
import logging
from pling.config import PlingConfig
from pling.server import PlingServer

def send_ipc_command(sock_path: str, cmd_dict: dict) -> dict:
    if not os.path.exists(sock_path):
        return {"status": "error", "message": f"Server not running (no socket at {sock_path})"}
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(sock_path)
        s.sendall(json.dumps(cmd_dict).encode("utf-8"))
        res = s.recv(4096).decode("utf-8")
        s.close()
        return json.loads(res)
    except Exception as e:
        return {"status": "error", "message": str(e)}

def main():
    parser = argparse.ArgumentParser(description="Pling Server Linux - Native Meta Quest 2D Ultra-Low Latency Streaming")
    subparsers = parser.add_subparsers(dest="action")

    # Serve command (default)
    serve_parser = subparsers.add_parser("serve", help="Run the streaming server daemon")
    serve_parser.add_argument("--port", type=int, default=3000, help="TCP listening port (default: 3000)")
    serve_parser.add_argument("--bitrate", type=int, default=30, help="HEVC bitrate in Mbps (default: 30)")
    serve_parser.add_argument("--fps", type=int, default=60, help="Target framerate (default: 60)")
    serve_parser.add_argument("--width", type=int, default=1920, help="Display width (default: 1920)")
    serve_parser.add_argument("--height", type=int, default=1080, help="Display height (default: 1080)")
    serve_parser.add_argument("--capture-mode", choices=["auto", "kms", "pipewire", "x11"], default="auto", help="Screen capture pipeline")
    serve_parser.add_argument("--video-type", type=int, choices=[0, 6], default=6, help="Video packet type (default: 6)")
    serve_parser.add_argument("--no-audio", action="store_true", help="Disable desktop audio streaming")
    serve_parser.add_argument("--no-adb", action="store_true", help="Disable ADB USB auto-bridge")
    serve_parser.add_argument("--debug", action="store_true", help="Enable verbose debug logging")

    # Remote control commands (via IPC)
    subparsers.add_parser("status", help="Get status of running Pling server")
    
    br_parser = subparsers.add_parser("bitrate", help="Set bitrate of running server")
    br_parser.add_argument("value", type=int, help="Bitrate in Mbps")

    subparsers.add_parser("keyframe", help="Force immediate IDR keyframe")
    subparsers.add_parser("stop-stream", help="Pause screen streaming")
    subparsers.add_parser("start-stream", help="Resume screen streaming")

    audio_parser = subparsers.add_parser("audio", help="Toggle audio streaming")
    audio_parser.add_argument("state", choices=["on", "off"], help="Audio on or off")

    args = parser.parse_args()

    # Default to serve if no action specified
    action = args.action or "serve"

    config = PlingConfig.load()

    if action == "status":
        res = send_ipc_command(config.ipc_socket_path, {"command": "status"})
        print(json.dumps(res, indent=2))
        return

    elif action == "bitrate":
        res = send_ipc_command(config.ipc_socket_path, {"command": "set_bitrate", "bitrate_mbps": args.value})
        print(json.dumps(res, indent=2))
        return

    elif action == "keyframe":
        res = send_ipc_command(config.ipc_socket_path, {"command": "force_keyframe"})
        print(json.dumps(res, indent=2))
        return

    elif action == "stop-stream":
        res = send_ipc_command(config.ipc_socket_path, {"command": "stop_stream"})
        print(json.dumps(res, indent=2))
        return

    elif action == "start-stream":
        res = send_ipc_command(config.ipc_socket_path, {"command": "start_stream"})
        print(json.dumps(res, indent=2))
        return

    elif action == "audio":
        res = send_ipc_command(config.ipc_socket_path, {"command": "toggle_audio", "enabled": args.state == "on"})
        print(json.dumps(res, indent=2))
        return

    # Run serve daemon
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S"
    )

    config.tcp_port = args.port
    config.bitrate_mbps = args.bitrate
    config.fps = args.fps
    config.width = args.width
    config.height = args.height
    config.capture_mode = args.capture_mode
    config.video_packet_type = args.video_type
    config.audio_enabled = not args.no_audio
    config.auto_adb = not args.no_adb

    server = PlingServer(config)
    if not server.start():
        sys.exit(1)

    try:
        while server.is_running:
            import time
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\nInterrupt received. Stopping Pling Server...")
    finally:
        server.stop()

if __name__ == "__main__":
    main()
