from sage.all import *  
import hashlib  
import time 

# Convert hex strings to integers  
p_hex = 'c90102faa48f18b5eac1f76bb40a1b9fb0d841712bbe3e5576a7a56976c2baeca47809765283aa078583e1e65172a3fd'  
a_hex = 'a079db08ea2470350c182487b50f7707dd46a58a1d160ff79297dcc9bfad6cfc96a81c4a97564118a40331fe0fc1327f'  
b_hex = '9f939c02a7bd7fc263a4cce416f4c575f28d0c1315c4f0c282fca6709a5f9f7f9c251c9eede9eb1baa31602167fa5380'  
  
p = int(p_hex, 16)
a_coeff = int(a_hex, 16)  
b_coeff = int(b_hex, 16)
  
# Define the finite field and elliptic curve  
F = GF(p)  
E = EllipticCurve(F, [a_coeff, b_coeff])  
  
# Attempt to compute the order (this may take a very long time or be infeasible)  
try:  
    order = E.cardinality()  
    print("Order of the elliptic curve:", order)
    print(f"The order of E is:\n{order}\nFactorized:\n{order.factor()}")
except Exception as e:  
    print("Error computing order:", e)  
