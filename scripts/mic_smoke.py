"""Record one ephemeral second and report format/energy without retaining audio."""

import argparse
import asyncio
import audioop
from pathlib import Path
import tempfile
import wave

from dolls_orchestrator.desktop_audio import SoundDeviceRecorder


async def run(seconds: float, device: str = None) -> None:
    selected_device = int(device) if device and device.isdigit() else device
    with tempfile.TemporaryDirectory(prefix="dolls-mic-smoke-") as temp_dir:
        path = Path(temp_dir) / "microphone.wav"
        await SoundDeviceRecorder(device=selected_device).record_until(
            path, asyncio.sleep(seconds)
        )
        with wave.open(str(path), "rb") as wav_file:
            frames = wav_file.getnframes()
            rate = wav_file.getframerate()
            sample_width = wav_file.getsampwidth()
            data = wav_file.readframes(frames)
        print(
            "frames=%d rate=%d channels=1 sample_width=%d rms=%d"
            % (frames, rate, sample_width, audioop.rms(data, sample_width))
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=1.0)
    parser.add_argument("--device")
    args = parser.parse_args()
    if args.seconds <= 0:
        parser.error("--seconds must be greater than zero")
    asyncio.run(run(args.seconds, args.device))


if __name__ == "__main__":
    main()
