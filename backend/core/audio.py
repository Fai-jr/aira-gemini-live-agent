import base64
import struct


# Audio configuration constants
SAMPLE_RATE = 16000        # 16kHz - required by Gemini Live API input
CHANNELS = 1               # Mono
SAMPLE_WIDTH = 2           # 16-bit PCM
CHUNK_SIZE = 1024          # Frames per chunk
OUTPUT_SAMPLE_RATE = 24000 # Gemini returns 24kHz audio


def encode_audio_to_base64(audio_bytes: bytes) -> str:
    """Encode raw PCM bytes to base64 string for Gemini Live API."""
    return base64.b64encode(audio_bytes).decode("utf-8")


def decode_audio_from_base64(b64_string: str) -> bytes:
    """Decode base64 string back to raw PCM bytes."""
    return base64.b64decode(b64_string)


def pcm_to_wav_bytes(pcm_data: bytes, sample_rate: int = OUTPUT_SAMPLE_RATE) -> bytes:
    """
    Wrap raw PCM data in a WAV header so the browser audio player can play it.
    """
    bits_per_sample = 16
    byte_rate = sample_rate * CHANNELS * bits_per_sample // 8
    block_align = CHANNELS * bits_per_sample // 8
    data_size = len(pcm_data)
    chunk_size = 36 + data_size

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        chunk_size,
        b"WAVE",
        b"fmt ",
        16,
        1,
        CHANNELS,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b"data",
        data_size,
    )
    return header + pcm_data


def normalize_audio_chunk(audio_bytes: bytes) -> bytes:
    """Trim odd trailing byte to keep 16-bit alignment."""
    if len(audio_bytes) % 2 != 0:
        return audio_bytes[:-1]
    return audio_bytes


def calculate_audio_duration(audio_bytes: bytes, sample_rate: int = SAMPLE_RATE) -> float:
    """Return duration in seconds of a raw PCM buffer."""
    return (len(audio_bytes) // SAMPLE_WIDTH) / sample_rate


def is_silence(audio_bytes: bytes, threshold: int = 500) -> bool:
    """
    Simple amplitude-based silence detection.
    Returns True if the chunk contains no meaningful audio signal.
    """
    if len(audio_bytes) < 2:
        return True
    total = 0
    num_samples = len(audio_bytes) // 2
    for i in range(0, len(audio_bytes) - 1, 2):
        sample = struct.unpack_from("<h", audio_bytes, i)[0]
        total += abs(sample)
    return (total / num_samples if num_samples > 0 else 0) < threshold


def merge_audio_chunks(chunks: list) -> bytes:
    """Merge a list of PCM chunks into one buffer."""
    return b"".join(chunks)