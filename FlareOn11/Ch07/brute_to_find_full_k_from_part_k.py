from sage.all import *  
import hashlib  
import time
import struct
from operator import xor

def HexStrToBigIntHex(hex_str):
    new_str = ""
    for i in range(0, len(hex_str), 8):
        new_str += struct.pack('<I', int(hex_str[(i//8) * 8 : i + 8], 16)).hex()
    return new_str

EXPECTED_X_COORD = '0a6c559073da49754e9ad9846a72954745e4f2921213eccda4b1422e2fdd646fc7e28389c7c2e51a591e0147e2ebe7ae'
# EXPECTED_X_COORD = '7e264a3c934e4c22815fcadd51b4f38bf8790e316ae5871b0ba49b26c8cf305fcb21091da3d782ef92b360ee2cdd4ca6' # TEST

# Convert hex strings to integers  
p_hex = 'c90102faa48f18b5eac1f76bb40a1b9fb0d841712bbe3e5576a7a56976c2baeca47809765283aa078583e1e65172a3fd'  
a_hex = 'a079db08ea2470350c182487b50f7707dd46a58a1d160ff79297dcc9bfad6cfc96a81c4a97564118a40331fe0fc1327f'  
b_hex = '9f939c02a7bd7fc263a4cce416f4c575f28d0c1315c4f0c282fca6709a5f9f7f9c251c9eede9eb1baa31602167fa5380'   
p = int(p_hex, 16)  
a = int(a_hex, 16)  
b = int(b_hex, 16)  

  
# Define the finite field and elliptic curve  
F = GF(p)  
E = EllipticCurve(F, [a, b])

# Define the finite field and elliptic curve  
F = GF(p)  
E = EllipticCurve(F, [a, b])  

GX_hex = '087b5fe3ae6dcfb0e074b40f6208c8f6de4f4f0679d6933796d3b9bd659704fb85452f041fff14cf0e9aa7e45544f9d8'  
GY_hex = '127425c1d330ed537663e87459eaa1b1b53edfe305f6a79b184b3180033aab190eb9aa003e02e9dbf6d593c5e3b08182'  
  
# Convert hex strings to integers  
xG = int(GX_hex, 16) 
yG = int(GY_hex, 16)

# Define the base point G  
G = E.point([xG, yG])


"""
key_hex = 'C7FBC938AB2149DFE9825E053CCA3F45' #TEST// FULL_k:0x38c9fbc7df4921ab055e82e9453fca3c PART_k:0x4a49e3279803d464d7550ad21dd1
# key_hex = i.to_bytes().hex() + j.to_bytes().hex() + part_k_hex
# key_hex = part_k_hex + i.to_bytes().hex() + j.to_bytes().hex()

#key_hex = HexStrToBigIntHex(key_hex)

part_k_hex = 'c0f9af2dbc735ae5a57cf155b870'
"""

match_found = False
#k_partial_found = 0xc0f9af2dbc735ae5a57cf155b870

# Given values  
k_partial = 0xc0f9af2dbc735ae5a57cf155b870   # Recovered integer  
N_prime = 4374617177662805965808447230529629 # The modulus used in Pohlig-Hellman (N' = Products of all primes used for calculating k_partial - it do not include the last prime in this case)  
  
# Maximum value for k (since it's a 128-bit integer)  
k_max = 1 << 128  
  
# Missing bits  
missing_bits_length = 128 -  k.bit_length()
total_candidates = 1 << missing_bits_length  # 2^16 = 65536  
  
# List to store possible k values (if needed)  
k_candidates = []  
  
# Iterate over possible values of m  
for m in range(total_candidates):  
    k_candidate = k_partial + N_prime * m
    if k_candidate < k_max:
        Q = k_candidate * G

        if Q.is_zero(): continue

        # Get the affine coordinates  
        x_Q, y_Q = Q.xy()  

        x_coord_str = HexStrToBigIntHex(x_Q.to_bytes().hex())
        x_coord_byt = list(bytes.fromhex(x_coord_str))
        xor_key = [0x37, 0x13]

        obfus_byt = b''
        x_byt = 0

        for idx, byt in enumerate(x_coord_byt):
            x_byt = xor(byt, xor_key[idx % 2])
            obfus_byt += x_byt.to_bytes()

        encrypted_x_coord = HexStrToBigIntHex(obfus_byt.hex())
        if encrypted_x_coord == EXPECTED_X_COORD:
            print(f"Matched {encrypted_x_coord} for k = {k_candidate} ({hex(k_candidate)}) at m {m}")
            match_found = True
            break;
    else:
        break  # No need to consider k_candidate >= 2^128  
        
if not match_found:
    print("NOT FOUND")
    
