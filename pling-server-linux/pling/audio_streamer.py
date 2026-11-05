"""
Ultra-low latency audio streamer for Pling Quest client.
Captures system audio via PipeWire / PulseAudio as PCM Float32LE 48000Hz Stereo.
"""

import os
import time
import shutil
import logging
import subprocess
import threading
from typing import Callable, Optional
from pling.config import PlingConfig

logger = logging.getLogger("PlingAudio")

class AudioStreamer:
    """
    Captures desktop output audio in real time and provides raw PCM Float32 frames
    ready to be framed with packet type 0x01.
    """
    def __init__(self, config: PlingConfig, on_audio_chunk: Callable[[bytes], None]):
        self.config = config
        self.on_audio_chunk = on_audio_chunk
        self._process: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        return self._running and self._process is not None and self._process.poll() is None

    def _get_capture_command(self) -> list[str]:
        rate = self.config.audio_sample_rate
        channels = self.config.audio_channels

        # 1. PipeWire pw-record (Standard on Bazzite / Fedora)
        if shutil.which("pw-record"):
            return [
                "pw-record",
                f"--rate={rate}",
                f"--channels={channels}",
                "--format=f32",
                "--target=@DEFAULT_AUDIO_SINK@.monitor",
                "-"
            ]

        # 2. PulseAudio parec
        if shutil.which("parec"):
            return [
                "parec",
                f"--rate={rate}",
                f"--channels={channels}",
                "--format=float32le",
                "-"
            ]

        # 3. FFmpeg Pulse capture fallback
        ffmpeg_bin = shutil.which("ffmpeg") or "/usr/bin/ffmpeg"
        return [
            ffmpeg_bin, "-nostdin", "-loglevel", "quiet",
            "-f", "pulse", "-i", "default",
            "-f", "f32le", "-acodec", "pcm_f32le",
            "-ar", str(rate), "-ac", str(channels),
            "-"
        ]

    def start(self) -> bool:
        with self._lock:
            if self._running:
                return True

            if not self.config.audio_enabled:
                logger.info("Audio streaming is disabled in configuration.")
                return False

            cmd = self._get_capture_command()
            logger.info(f"Starting audio capture: {' '.join(cmd)}")

            try:
                self._process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    bufsize=32768
                )
            except Exception as e:
                logger.error(f"Failed to start audio recorder: {e}")
                return False

            self._running = True
            self._thread = threading.Thread(target=self._capture_loop, name="PlingAudioCapture", daemon=True)
            self._thread.start()
            return True

    def stop(self) -> None:
        with self._lock:
            if not self._running:
                return
            self._running = False

            if self._process:
                try:
                    self._process.terminate()
                    self._process.wait(timeout=0.5)
                except Exception:
                    try:
                        self._process.kill()
                    except Exception:
                        pass
                self._process = None

    def _capture_loop(self) -> None:
        stdout = self._process.stdout if self._process else None
        if not stdout:
            return

        # 960 samples per channel * 2 channels * 4 bytes/sample = 7680 bytes (20ms)
        chunk_size = self.config.audio_chunk_samples * self.config.audio_channels * 4

        while self._running:
            try:
                data = stdout.read(chunk_size)
                if not data:
                    if self._process and self._process.poll() is not None:
                        logger.warning("Audio capture process ended.")
                        break
                    time.sleep(0.005)
                    continue

                if len(data) > 0:
                    self.on_audio_chunk(data)
            except Exception as e:
                logger.error(f"Error in audio capture loop: {e}")
                break

        self._running = False
