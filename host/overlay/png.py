"""A minimal PNG writer (numpy and the standard library only), so frames can be saved and embedded without an imaging library."""
import base64
import struct
import zlib

import numpy as np


def png_bytes(rgb):
    """PNG bytes of an H x W x 3 uint8 array."""
    rgb = np.ascontiguousarray(rgb, dtype=np.uint8)
    if rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError("expected an H x W x 3 uint8 array")
    height, width, _ = rgb.shape
    raw = b"".join(b"\x00" + rgb[row].tobytes() for row in range(height))

    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b"")


def data_uri(rgb):
    return "data:image/png;base64," + base64.b64encode(png_bytes(rgb)).decode("ascii")
