from pathlib import Path
from struct import pack
from zlib import compress, crc32

from .models import MOCK_BANNER, SeedProduct


def write_png(path: Path, product: SeedProduct) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    width, height = 320, 180
    colour = _colour(product.reference)
    rows = b"".join(_png_row(width, colour, y) for y in range(height))
    chunks = [
        _png_chunk(b"IHDR", pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)),
        _png_chunk(b"tEXt", f"Comment\x00{MOCK_BANNER} {product.title}".encode()),
        _png_chunk(b"IDAT", compress(rows)),
        _png_chunk(b"IEND", b""),
    ]
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"".join(chunks))


def write_jpeg(path: Path, product: SeedProduct) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    comment = f"{MOCK_BANNER} {product.title}".encode()
    # Minimal placeholder JPEG envelope with a comment marker. The seed is
    # metadata-focused; real imagery bytes arrive in a later storage sprint.
    payload = (
        b"\xff\xd8"
        + b"\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        + b"\xff\xfe"
        + pack(">H", len(comment) + 2)
        + comment
        + b"\xff\xd9"
    )
    path.write_bytes(payload)


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    checksum = crc32(kind + data) & 0xFFFFFFFF
    return pack(">I", len(data)) + kind + data + pack(">I", checksum)


def _colour(seed: str) -> tuple[int, int, int]:
    value = sum(seed.encode("utf-8"))
    return (64 + value % 120, 90 + value % 80, 120 + value % 70)


def _png_row(width: int, colour: tuple[int, int, int], y: int) -> bytes:
    pixels = []
    for x in range(width):
        band = (x // 32 + y // 24) % 4
        pixels.extend(
            (
                min(255, colour[0] + band * 12),
                min(255, colour[1] + band * 8),
                min(255, colour[2] + band * 10),
            )
        )
    return b"\x00" + bytes(pixels)
