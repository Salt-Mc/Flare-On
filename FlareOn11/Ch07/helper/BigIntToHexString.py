import struct
import sys


hex_str = sys.argv[1]
bit_len = sys.argv[2]
bit_len = int(bit_len)
new_str = ""

for i in range(0, len(hex_str), 8):
    new_str += struct.pack('<I', int(hex_str[(i//bit_len) * bit_len : i + bit_len], 16)).hex()

print("BigInt: " + hex_str)
print("HexStr: " + new_str)