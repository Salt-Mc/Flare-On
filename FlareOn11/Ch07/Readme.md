## Find the curve order
Run `step0_FindCurveOrder.py`
output will be 
```
Order of the elliptic curve: 30937339651019945892244794266256713890440922455872051984762505561763526780311616863989511376879697740787911484829297
The order of E is:
30937339651019945892244794266256713890440922455872051984762505561763526780311616863989511376879697740787911484829297
Factorized:
35809 * 46027 * 56369 * 57301 * 65063 * 111659 * 113111 * 7072010737074051173701300310820071551428959987622994965153676442076542799542912293
```

## Find the private key (k)
Run `step_1_find _priv_key.py`
output will be
```
Prime Factors of N: [35809, 46027, 56369, 57301, 65063, 111659, 113111]
For Prime: 35809   , Discrete Log = 11872   
For Prime: 46027   , Discrete Log = 42485   
For Prime: 56369   , Discrete Log = 12334   
For Prime: 57301   , Discrete Log = 45941   
For Prime: 65063   , Discrete Log = 27946   
For Prime: 111659  , Discrete Log = 43080   
For Prime: 113111  , Discrete Log = 57712   
The value of Scalar k: 3914004671535485983675163411331184
In Hex: 0xc0f9af2dbc735ae5a57cf155b870
Bit Length: 112
N' = 4374617177662805965808447230529629
```
This is the partial value of K (notice the Bit Length it's 112 much less than 128)

## Find the full value of k from partial value of k by brute force
run `brute_to_find_full_k_from_part_k.py`
Output will be
```
Matched 0a6c559073da49754e9ad9846a72954745e4f2921213eccda4b1422e2fdd646fc7e28389c7c2e51a591e0147e2ebe7ae for k = 168606034648973740214207039875253762473 (0x7ed85751e7131b5eaf5592718bef79a9) at m 38541
```

Now we have private key you can put it use it to compute the shared secret. ss = K.Q'

Now use the shared secret and hash it to get the chacha20 key. Then use the key to decrypt the comms and get the flag

## Final script
Run `final_decrypt_comms.py` to get the flag

