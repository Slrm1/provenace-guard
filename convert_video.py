"""Convert the generated AVI walkthrough to a browser-friendly MP4."""

import subprocess
from pathlib import Path

import imageio_ffmpeg


root = Path(__file__).parent
source = root / "demo_walkthrough.avi"
target = root / "demo_walkthrough.mp4"
subprocess.run([
    imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-i", str(source),
    "-vf", "fps=24", "-c:v", "libx264", "-preset", "medium", "-crf", "23",
    "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", str(target),
], check=True)
print(f"Created {target}")
