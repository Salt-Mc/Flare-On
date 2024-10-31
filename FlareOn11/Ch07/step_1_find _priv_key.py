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

def decrypt_coord(x_coord_str):
    x_coord_byt = list(bytes.fromhex(x_coord_str))
    xor_key = [0x37, 0x13]

    obfus_byt = b''
    x_byt = 0

    for idx, byt in enumerate(x_coord_byt):
        x_byt = xor(byt, xor_key[idx % 2])
        obfus_byt += x_byt.to_bytes()
    return obfus_byt.hex()

# Curver parametes from the constructor in EXE file
p_hex = 'c90102faa48f18b5eac1f76bb40a1b9fb0d841712bbe3e5576a7a56976c2baeca47809765283aa078583e1e65172a3fd'  
a_hex = 'a079db08ea2470350c182487b50f7707dd46a58a1d160ff79297dcc9bfad6cfc96a81c4a97564118a40331fe0fc1327f'  
b_hex = '9f939c02a7bd7fc263a4cce416f4c575f28d0c1315c4f0c282fca6709a5f9f7f9c251c9eede9eb1baa31602167fa5380'  
  
p = int(p_hex, 16)  
a = int(a_hex, 16)  
b = int(b_hex, 16)  

# Define the finite field and elliptic curve  
F = GF(p)
# Define a curve based on curve parameters
E = EllipticCurve(F, [a, b])  

# X and Y parametes of point G on curve E 
GX_hex = '087b5fe3ae6dcfb0e074b40f6208c8f6de4f4f0679d6933796d3b9bd659704fb85452f041fff14cf0e9aa7e45544f9d8'  
GY_hex = '127425c1d330ed537663e87459eaa1b1b53edfe305f6a79b184b3180033aab190eb9aa003e02e9dbf6d593c5e3b08182'  
  
# Convert hex strings to integers  
xG = int(GX_hex, 16) 
yG = int(GY_hex, 16)

# Get the actual point from the X and Y parametes of G  
G = E.point([xG, yG])

# Public key coords X and Y of the client (EXE file)
Qx_hex = '0a6c559073da49754e9ad9846a72954745e4f2921213eccda4b1422e2fdd646fc7e28389c7c2e51a591e0147e2ebe7ae' # As it is sent from Client (exe file)
Qx_hex = HexStrToBigIntHex(Qx_hex)
Qx_hex = decrypt_coord(Qx_hex)
Qx_hex = HexStrToBigIntHex(Qx_hex)

Qy_hex = '264022daf8c7676a1b2720917b82999d42cd1878d31bc57b6db17b9705c7ff2404cbbf13cbdb8c096621634045293922' # As it is sent from Client
Qy_hex = HexStrToBigIntHex(Qy_hex)
Qy_hex = decrypt_coord(Qy_hex)
Qy_hex = HexStrToBigIntHex(Qy_hex)

# Limit to Finite Field -- optional though
xQ = F(int(Qx_hex, 16))
yQ = F(int(Qy_hex, 16))

# Calculate the actual Public Key Q from X and Y coords of Q. A point on curve E
Q = E.point([xQ, yQ])


# Curve Order N is computed separately in another script
N = 30937339651019945892244794266256713890440922455872051984762505561763526780311616863989511376879697740787911484829297 # Order of the curve

# Factorize N, these factors will also be essential for recovering full priv key (k) from partial one that we will get from this script 
factors = N.factor()
primes = [factor**exponent for factor, exponent in factors[:-1]]

print("Prime Factors of N:", primes)  
  
# Initialize list for CRT (Chinese Remainder Theorem)
congruences = []

for factor in primes:
    t = N // int(factor)
    iG = t * G
    if iG.is_zero(): continue  # Skip is iG is 0
    iQ = t * Q
    d_log = discrete_log(iQ, iG, operation="+")
    congruences.append(d_log)
    print(f"For Prime: {factor: <{8}}, Discrete Log = {d_log: <{8}}")

k = crt(congruences,primes)
print(f"The value of Scalar k: {k}\nIn Hex: {hex(k)}\nBit Length: {k.bit_length()}")

# This product will be used as modulo for bruteforcing the partially recovered k, it's same as what get from line 76 except the last value (it's too big)
print(f"N' = {35809 * 46027 * 56369 * 57301 * 65063 * 111659 * 113111}")

