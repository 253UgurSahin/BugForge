"""Shared by the scripts that read PNG screenshots byte by byte: imgdiff.py here and ../forge-design/eyedropper.py
(which puts this folder on sys.path). It splits a PNG file into its chunks and undoes the filter of each row of
its image data.

Not a script: no command line. imgdiff.py imports it by name, which works because Python puts a script's own
folder first on sys.path. Standard library only.
"""

import struct
from itertools import accumulate
from operator import add

MOD256 = list(range(256)) * 2  # MOD256[n] is n % 256 for n up to 511


def chunks_of(data):
    """{chunk type: [its bodies, in order]} of the bytes of a PNG file, after its 8-byte signature."""
    chunks, pos = {}, 8
    while pos + 8 <= len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        chunks.setdefault(kind, []).append(data[pos + 8:pos + 8 + length])
        pos += 12 + length  # length, type, body, checksum
    return chunks


def paeth(left, up, upleft):
    """The PNG Paeth predictor: whichever neighbour is closest to left + up - upleft."""
    guess = left + up - upleft
    distances = [abs(guess - left), abs(guess - up), abs(guess - upleft)]
    return (left, up, upleft)[distances.index(min(distances))]  # on a tie: left, then up


def unfilter(kind, line, prev, bpp):
    """Undo filter type 0 to 4 on one row of PNG image data (the PNG spec, section 9)."""
    if kind == 1:  # add the byte one pixel to the left: a running total per channel
        for channel in range(bpp):
            line[channel::bpp] = bytearray(map((255).__and__, accumulate(line[channel::bpp])))
    elif kind == 2:  # add the byte above
        line = bytearray(map(MOD256.__getitem__, map(add, line, prev)))
    elif kind in (3, 4):  # add the average of left and above, or the Paeth guess: byte by byte
        for i in range(len(line)):
            left, upleft = (line[i - bpp], prev[i - bpp]) if i >= bpp else (0, 0)
            guess = (left + prev[i]) >> 1 if kind == 3 else paeth(left, prev[i], upleft)
            line[i] = (line[i] + guess) & 255
    return line
