"""
Curve Parameters:

Curve: P-384, which is an elliptic curve over a 384-bit prime field.
Order ( N ): The order of the elliptic curve group ( E(\mathbb{F}_p) ) is approximately ( 2^{384} ).
Scalar ( k ): Originally a 128-bit integer.

Recovered Scalar ( k ): 112 bits after applying Pohlig-Hellman and CRT.

This suggests that the product of the prime powers you used in the Pohlig-Hellman algorithm (let's call it ( N' )) is approximately ( 2^{112} ) in size.

Here's why:

Partial Factorization: If you were only able to factor ( N ) into small primes up to 112 bits, then the ( N' ) used in the algorithm is only about 112 bits long.

Solving Modulo ( N' ): The Pohlig-Hellman algorithm would then only recover ( k \mod N' ), giving you a value of ( k ) in the range ( [0, N'-1] ).

Original ( k ) vs. Recovered ( k ): Since the original ( k ) is 128 bits, but you have only recovered ( k \mod N' ) where ( N' ) is 112 bits, you are missing information about the higher-order bits of ( k ).
"""

from sage.all import *  
import hashlib  
import time 

# Convert hex strings to integers  
p_hex = 'c90102faa48f18b5eac1f76bb40a1b9fb0d841712bbe3e5576a7a56976c2baeca47809765283aa078583e1e65172a3fd'  
a_hex = 'a079db08ea2470350c182487b50f7707dd46a58a1d160ff79297dcc9bfad6cfc96a81c4a97564118a40331fe0fc1327f'  
b_hex = '9f939c02a7bd7fc263a4cce416f4c575f28d0c1315c4f0c282fca6709a5f9f7f9c251c9eede9eb1baa31602167fa5380'  
  
p = int(p_hex, 16)  
a = int(a_hex, 16)  
b = int(b_hex, 16)  

N = 30937339651019945892244794266256713890440922455872051984762505561763526780311616863989511376879697740787911484829297 # Order of the curve
  
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


# Public key Q coordinates - from PCAP fiile, transmission sent to the server
Qx_hex = '195b46a760ed5a425dadcab37945867056d3e1a50124fffab78651193cea7758d4d590bed4f5f62d4a291270f1dcf499' # send from client
Qy_hex = '357731edebf0745d081033a668b58aaa51fa0b4fc02cd64c7e8668a016f0ec1317fcac24d8ec9f3e75167077561e2a15' # send from client

xQ = int(Qx_hex, 16)
yQ = int(Qy_hex, 16)

# Define the point Q  
Q = E.point([xQ, yQ])

# Factorize N  
factorization = N.factor()
print("Factorization of N:", factorization)  
  
# Initialize list for CRT  
congruences = []  
  
for prime_power in factorization:  
    p_i = prime_power[0]  
    e_i = prime_power[1]
    
    # Igonre too big number - crashing on it
    if p_i == 7072010737074051173701300310820071551428959987622994965153676442076542799542912293 or \
       e_i == 7072010737074051173701300310820071551428959987622994965153676442076542799542912293:
        continue
    
    n_i = p_i**e_i  
    print(f"\nProcessing prime power: {p_i}^{e_i} = {n_i}")  
      
    N_i = n_i  
    h_i = N // N_i  # Order divided by multiplication of consequitive factors
  
    G_i = h_i * G  
    if G_i.is_zero():  
        print("G_i is zero. Skipping this factor.")  
        continue
  
    Q_i = h_i * Q  
  
    try:  
        k_i = discrete_log(Q_i, G_i, operation="+")  
        print(f"Found k mod {N_i}: k_i = {k_i}")  
        congruences.append((N_i, k_i))
    except ValueError as e:  
        print(f"Failed to compute discrete log modulo {N_i}: {e}")  

moduli = [modulus for (modulus, remainder) in congruences]  
remainders = [remainder for (modulus, remainder) in congruences]  
  
k = crt(remainders, moduli)  
print(f"\nThe scalar multiplier k is: {k}\nHex: {k.hex()}\nBit Length: {k.bit_length()}")
