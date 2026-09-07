"""Raw Opus codec backed by the native libopus reference implementation."""

import asyncio
from array import array
import ctypes
from ctypes.util import find_library
from pathlib import Path
import sys
from typing import Iterable, Optional, Sequence, Tuple

from .domain import AudioFormat
from .errors import OpusCodecError
from .terminal_bridge import DecodedTerminalAudio
from .terminal_protocol import AudioParameters, MAX_BINARY_FRAME_BYTES


OPUS_APPLICATION_VOIP = 2048
OPUS_OK = 0
MAX_OPUS_PACKET_BYTES = 4000
SUPPORTED_SAMPLE_RATES = frozenset({8000, 12000, 16000, 24000, 48000})
SUPPORTED_FRAME_DURATIONS_MS = frozenset({5, 10, 20, 40, 60})
_COMMON_LIBRARY_PATHS = (
    "/opt/homebrew/opt/opus/lib/libopus.dylib",
    "/opt/homebrew/lib/libopus.dylib",
    "/usr/local/lib/libopus.dylib",
    "/usr/lib/libopus.so.0",
    "/usr/local/lib/libopus.so.0",
)


def _library_candidates(explicit_path: Optional[str] = None) -> Iterable[str]:
    if explicit_path is not None:
        yield str(explicit_path)
        return
    discovered = find_library("opus")
    if discovered:
        yield discovered
    for candidate in _COMMON_LIBRARY_PATHS:
        if Path(candidate).is_file():
            yield candidate


def find_libopus(explicit_path: Optional[str] = None) -> str:
    """Return the first loadable libopus location without leaking failed paths."""
    seen = set()
    for candidate in _library_candidates(explicit_path):
        if candidate in seen:
            continue
        seen.add(candidate)
        try:
            ctypes.CDLL(candidate)
        except (OSError, TypeError, ValueError):
            continue
        return candidate
    raise OpusCodecError("native libopus is unavailable")


class _LibOpus:
    def __init__(self, library_path: Optional[str] = None) -> None:
        self.path = find_libopus(library_path)
        try:
            self.library = ctypes.CDLL(self.path)
            self._bind()
        except (AttributeError, OSError, TypeError, ValueError) as exc:
            raise OpusCodecError("native libopus is unusable") from exc

    def _bind(self) -> None:
        library = self.library
        library.opus_get_version_string.argtypes = []
        library.opus_get_version_string.restype = ctypes.c_char_p

        library.opus_strerror.argtypes = [ctypes.c_int]
        library.opus_strerror.restype = ctypes.c_char_p

        library.opus_decoder_create.argtypes = [
            ctypes.c_int32,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_int),
        ]
        library.opus_decoder_create.restype = ctypes.c_void_p
        library.opus_decode.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.c_int32,
            ctypes.POINTER(ctypes.c_int16),
            ctypes.c_int,
            ctypes.c_int,
        ]
        library.opus_decode.restype = ctypes.c_int
        library.opus_decoder_destroy.argtypes = [ctypes.c_void_p]
        library.opus_decoder_destroy.restype = None

        library.opus_encoder_create.argtypes = [
            ctypes.c_int32,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_int),
        ]
        library.opus_encoder_create.restype = ctypes.c_void_p
        library.opus_encode.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_int16),
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.c_int32,
        ]
        library.opus_encode.restype = ctypes.c_int32
        library.opus_encoder_destroy.argtypes = [ctypes.c_void_p]
        library.opus_encoder_destroy.restype = None

    @property
    def version(self) -> str:
        raw = self.library.opus_get_version_string()
        if not raw:
            raise OpusCodecError("native libopus version is unavailable")
        return raw.decode("ascii", errors="replace")

    def error_message(self, code: int) -> str:
        raw = self.library.opus_strerror(code)
        if not raw:
            return "unknown error"
        return raw.decode("ascii", errors="replace")


class LibOpusCodec:
    """Async terminal codec for one-packet-per-WebSocket-frame raw Opus."""

    def __init__(self, library_path: Optional[str] = None) -> None:
        self._opus = _LibOpus(library_path)

    @property
    def library_path(self) -> str:
        return self._opus.path

    @property
    def version(self) -> str:
        return self._opus.version

    async def decode_uplink(
        self,
        frames: Sequence[bytes],
        source: AudioParameters,
    ) -> DecodedTerminalAudio:
        normalized = _validate_packets(frames)
        _validate_opus_parameters(source)
        pcm = await asyncio.to_thread(self._decode, normalized, source)
        return DecodedTerminalAudio(
            pcm=pcm,
            audio_format=AudioFormat(sample_rate=source.sample_rate),
        )

    async def encode_downlink(
        self,
        pcm: bytes,
        source: AudioFormat,
        target: AudioParameters,
    ) -> Tuple[bytes, ...]:
        normalized = _validate_pcm(pcm, source)
        _validate_opus_parameters(target)
        return await asyncio.to_thread(self._encode, normalized, source, target)

    def _decode(
        self, frames: Sequence[bytes], source: AudioParameters
    ) -> bytes:
        error = ctypes.c_int()
        decoder = self._opus.library.opus_decoder_create(
            source.sample_rate, source.channels, ctypes.byref(error)
        )
        if not decoder or error.value != OPUS_OK:
            raise OpusCodecError("native Opus decoder creation failed")

        frame_size = _frame_samples(source)
        decoded = array("h")
        try:
            for packet in frames:
                encoded = (ctypes.c_ubyte * len(packet)).from_buffer_copy(packet)
                output = (ctypes.c_int16 * frame_size)()
                sample_count = self._opus.library.opus_decode(
                    decoder,
                    encoded,
                    len(packet),
                    output,
                    frame_size,
                    0,
                )
                if sample_count < 0:
                    raise OpusCodecError("native Opus packet decode failed")
                decoded.extend(output[:sample_count])
        finally:
            self._opus.library.opus_decoder_destroy(decoder)

        if not decoded:
            raise OpusCodecError("decoded Opus audio is empty")
        return _samples_to_little_endian_bytes(decoded)

    def _encode(
        self, pcm: bytes, source: AudioFormat, target: AudioParameters
    ) -> Tuple[bytes, ...]:
        samples = _little_endian_bytes_to_samples(pcm)
        if source.sample_rate != target.sample_rate:
            samples = _resample_mono(
                samples, source.sample_rate, target.sample_rate
            )

        frame_size = _frame_samples(target)
        error = ctypes.c_int()
        encoder = self._opus.library.opus_encoder_create(
            target.sample_rate,
            target.channels,
            OPUS_APPLICATION_VOIP,
            ctypes.byref(error),
        )
        if not encoder or error.value != OPUS_OK:
            raise OpusCodecError("native Opus encoder creation failed")

        packets = []
        try:
            for offset in range(0, len(samples), frame_size):
                frame = array("h", samples[offset : offset + frame_size])
                if len(frame) < frame_size:
                    frame.extend([0] * (frame_size - len(frame)))
                native_frame = (ctypes.c_int16 * frame_size)(*frame)
                output = (ctypes.c_ubyte * MAX_OPUS_PACKET_BYTES)()
                packet_size = self._opus.library.opus_encode(
                    encoder,
                    native_frame,
                    frame_size,
                    output,
                    MAX_OPUS_PACKET_BYTES,
                )
                if packet_size < 0:
                    raise OpusCodecError("native Opus frame encode failed")
                if packet_size == 0:
                    raise OpusCodecError("encoded Opus packet is empty")
                packets.append(bytes(output[:packet_size]))
        finally:
            self._opus.library.opus_encoder_destroy(encoder)

        if not packets:
            raise OpusCodecError("encoded Opus audio is empty")
        return tuple(packets)


def _validate_opus_parameters(parameters: AudioParameters) -> None:
    if not isinstance(parameters, AudioParameters):
        raise OpusCodecError("Opus audio parameters are invalid")
    if parameters.format != "opus":
        raise OpusCodecError("Opus audio format is unsupported")
    if parameters.sample_rate not in SUPPORTED_SAMPLE_RATES:
        raise OpusCodecError("Opus sample rate is unsupported")
    if parameters.channels != 1:
        raise OpusCodecError("Opus channel count is unsupported")
    if parameters.frame_duration not in SUPPORTED_FRAME_DURATIONS_MS:
        raise OpusCodecError("Opus frame duration is unsupported")
    _frame_samples(parameters)


def _frame_samples(parameters: AudioParameters) -> int:
    samples, remainder = divmod(
        parameters.sample_rate * parameters.frame_duration, 1000
    )
    if remainder or samples <= 0:
        raise OpusCodecError("Opus frame duration is invalid")
    return samples


def _validate_packets(frames: Sequence[bytes]) -> Tuple[bytes, ...]:
    if isinstance(frames, (bytes, bytearray, str)):
        raise OpusCodecError("Opus packets are invalid")
    try:
        normalized = tuple(frames)
    except (TypeError, ValueError) as exc:
        raise OpusCodecError("Opus packets are invalid") from exc
    if not normalized:
        raise OpusCodecError("Opus packets are empty")
    for packet in normalized:
        if not isinstance(packet, bytes) or not packet:
            raise OpusCodecError("Opus packet is invalid")
        if len(packet) > MAX_BINARY_FRAME_BYTES:
            raise OpusCodecError("Opus packet is too large")
    return normalized


def _validate_pcm(pcm: bytes, source: AudioFormat) -> bytes:
    if not isinstance(pcm, bytes) or not pcm:
        raise OpusCodecError("PCM audio is empty")
    if not isinstance(source, AudioFormat):
        raise OpusCodecError("PCM audio format is invalid")
    if source.encoding != "pcm_s16le" or source.sample_width != 2:
        raise OpusCodecError("PCM encoding is unsupported")
    if source.channels != 1:
        raise OpusCodecError("PCM channel count is unsupported")
    if source.sample_rate <= 0:
        raise OpusCodecError("PCM sample rate is invalid")
    if len(pcm) % 2:
        raise OpusCodecError("PCM audio contains an incomplete sample")
    return pcm


def _little_endian_bytes_to_samples(pcm: bytes) -> array:
    samples = array("h")
    samples.frombytes(pcm)
    if sys.byteorder != "little":
        samples.byteswap()
    return samples


def _samples_to_little_endian_bytes(samples: array) -> bytes:
    output = array("h", samples)
    if sys.byteorder != "little":
        output.byteswap()
    return output.tobytes()


def _resample_mono(samples: array, source_rate: int, target_rate: int) -> array:
    if not samples or source_rate <= 0 or target_rate <= 0:
        raise OpusCodecError("PCM resampling parameters are invalid")
    output_length = max(1, round(len(samples) * target_rate / source_rate))
    if len(samples) == 1:
        return array("h", [samples[0]] * output_length)

    result = array("h")
    for destination_index in range(output_length):
        source_position = destination_index * source_rate / target_rate
        left = min(int(source_position), len(samples) - 1)
        right = min(left + 1, len(samples) - 1)
        fraction = source_position - left
        value = round(samples[left] + (samples[right] - samples[left]) * fraction)
        result.append(max(-32768, min(32767, value)))
    return result
