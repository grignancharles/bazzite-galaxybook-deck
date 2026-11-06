"""
Ultra-low latency desktop audio streamer for Meta Quest client.
Captures system audio via PipeWire / PulseAudio as PCM Float32LE 48000Hz Stereo.
Applies real-time volume boost gain matching Mac StreamEngine Audio pipeline.
"""

import os
import time
import array
import shutil
import logging
import subprocess
import threading
from typing import Callable, Optional
from pling.config import PlingConfig

logger = logging.getLogger("PlingAudio")

# Try to import numpy for ultra-fast vectorised gain scaling, fallback to standard array
try:
    import numpy as np
    HAVE_NUMPY = True
except ImportError:
    HAVE_NUMPY = False

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
        self._current_volume_boost: float = config.volume_boost

    @property
    def is_running(self) -> bool:
        return self._running and self._process is not None and self._process.poll() is None

    def set_volume_boost(self, boost: float) -> None:
        """
        Dynamically adjusts volume boost multiplier (0.0 to 10.0x).
        """
        self._current_volume_boost = max(0.0, min(10.0, float(boost)))
        self.config.volume_boost = self._current_volume_boost

    def _get_capture_command(self) -> list[str]:
        rate = self.config.audio_sample_rate
        channels = self.config.audio_channels

        # 1. PipeWire pw-record (Standard on SteamOS / Bazzite / Fedora)
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
            logger.info(f"Starting desktop audio capture: {' '.join(cmd)}")

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

    def _apply_gain(self, raw_bytes: bytes, gain: float) -> bytes:
        """
        Scales Float32 PCM samples by gain (0.15 * volume_boost).
        Matching Mac ContentView: 'let gain: Float32 = 0.15 * self.volumeBoost'
        """
        if abs(gain - 1.0) < 0.005:
            return raw_bytes

        if HAVE_NUMPY:
            arr = np.frombuffer(raw_bytes, dtype=np.float32)
            scaled = np.clip(arr * gain, -1.0, 1.0)
            return scaled.tobytes()

        # Fallback using standard library array
        arr = array.array('f')
        arr.frombytes(raw_bytes)
        for i in range(len(arr)):
            v = arr[i] * gain
            if v > 1.0:
                v = 1.0
            elif v < -1.0:
                v = -1.0
            arr[i] = v
        return arr.tobytes()

    def _capture_loop(self) -> None:
        stdout = self._process.stdout if self._process else None
        if not stdout:
            return

        # 960 samples per channel * 2 channels * 4 bytes/sample = 7680 bytes (20ms buffer)
        chunk_size = self.config.audio_chunk_samples * self.config.audio_channels * 4

        while self._running:
            try:
                data = stdout.read(chunk_size)
                if not data:
                    if self._process and self._process.poll() is not None:
                        logger.warning("Audio capture process ended unexpectedly.")
                        break
                    time.sleep(0.005)
                    continue

                if len(data) > 0:
                    # Unity gain calculation matching Mac StreamEngine: 0.15 * volumeBoost
                    # For Linux, 1.0 boost corresponds to normal output volume
                    gain = float(self._current_volume_boost)
                    processed = self._apply_gain(data, gain)
                    self.on_audio_chunk(processed)

            except Exception as e:
                logger.error(f"Error in audio capture loop: {e}")
                break

        self._running = False
