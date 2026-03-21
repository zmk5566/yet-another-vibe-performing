"""
Real-time audio player using PyAudio
"""

import pyaudio
import numpy as np
import threading
import queue

class RealtimeAudioPlayer:
    """
    Real-time audio player that plays audio chunks as they're generated
    """

    def __init__(self, sample_rate=44100, buffer_size=512, device_index=None):
        """
        Args:
            sample_rate: Audio sample rate
            buffer_size: Buffer size in samples
            device_index: Output device index (None = system default)
        """
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size
        self.device_index = device_index

        # PyAudio
        self.pa = pyaudio.PyAudio()
        self.stream = None

        # Audio queue (thread-safe)
        self.audio_queue = queue.Queue(maxsize=10)

        # State
        self.running = False

    def start(self):
        """Start audio playback"""
        if self.running:
            return

        self.running = True

        # Open audio stream with callback
        open_kwargs = dict(
            format=pyaudio.paFloat32,
            channels=2,
            rate=self.sample_rate,
            output=True,
            frames_per_buffer=self.buffer_size,
            stream_callback=self._audio_callback
        )
        if self.device_index is not None:
            open_kwargs['output_device_index'] = self.device_index

        self.stream = self.pa.open(**open_kwargs)
        self.stream.start_stream()

    def stop(self):
        """Stop audio playback"""
        if not self.running:
            return

        self.running = False

        if self.stream:
            self.stream.stop_stream()
            self.stream.close()

        self.pa.terminate()

    def _audio_callback(self, in_data, frame_count, time_info, status):
        """PyAudio callback - called when audio is needed"""
        try:
            # Get audio from queue (non-blocking)
            audio = self.audio_queue.get_nowait()

            # Ensure correct size
            if audio.shape[0] < frame_count * 2:
                # Pad with zeros if too short
                padding = np.zeros(frame_count * 2 - audio.shape[0], dtype=np.float32)
                audio = np.concatenate([audio, padding])
            elif audio.shape[0] > frame_count * 2:
                # Truncate if too long
                audio = audio[:frame_count * 2]

            return (audio.tobytes(), pyaudio.paContinue)

        except queue.Empty:
            # No audio available, return silence
            silence = np.zeros(frame_count * 2, dtype=np.float32)
            return (silence.tobytes(), pyaudio.paContinue)

    def play_chunk(self, audio_chunk):
        """
        Queue audio chunk for playback

        Args:
            audio_chunk: numpy array, shape (2, samples) - stereo audio
        """
        if not self.running:
            return

        # Convert from (2, samples) to interleaved float32
        audio_interleaved = audio_chunk.T.astype(np.float32).flatten()

        # Add to queue (non-blocking)
        try:
            self.audio_queue.put_nowait(audio_interleaved)
        except queue.Full:
            # Queue full, drop this chunk
            # This prevents audio from building up latency
            pass

    def __enter__(self):
        """Context manager entry"""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.stop()
