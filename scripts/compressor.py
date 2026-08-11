#!/usr/bin/env python3

# compressor for linker
# compressor.py <filename> <comptype>

import os
import sys
import struct
import subprocess

filename = sys.argv[1]
comptype = sys.argv[2]

if comptype == 'lz':
    gbagfx = 'tools/gbagfx/gbagfx.exe' if os.name == 'nt' else 'tools/gbagfx/gbagfx'
    subprocess.check_call([gbagfx, filename, filename + '.lz'])
elif comptype == 'fk':
    size = os.path.getsize(filename) + 4
    with open(filename, 'rb') as f:
        data = f.read()
    with open(filename + '.fk', 'wb') as f:
        f.write(struct.pack('<I', size << 8))
        f.write(data)

