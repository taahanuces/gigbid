from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
FRAMES = ROOT / "docs" / "assets" / "demo-frames"
OUTPUT = ROOT / "docs" / "assets" / "gigbid-demo.gif"


def build() -> Path:
    paths = sorted(FRAMES.glob("frame-*.png"))
    if not paths:
        raise FileNotFoundError(f"No frames found in {FRAMES}")
    images: list[Image.Image] = []
    for path in paths:
        with Image.open(path) as source:
            frame = source.convert("RGB")
            frame.thumbnail((1200, 750), Image.Resampling.LANCZOS)
            images.append(frame.copy())
    images[0].save(
        OUTPUT,
        save_all=True,
        append_images=images[1:],
        duration=1800,
        loop=0,
        optimize=True,
    )
    return OUTPUT


if __name__ == "__main__":
    print(build())
