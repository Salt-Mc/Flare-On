# Ch6

## Overview

Target Files:

- Challenge binary (decompiled): [challenge_to_compile.py](h:\Github\FlareOn\FlareOn12\Ch6\challenge_to_compile.py)  
  Key classes: `ChatLogic`, `LCGOracle`, `TripleXOROracle`  
- Solver: [decrypt_rsa_chat.py](h:\Github\FlareOn\FlareOn12\Ch6\decrypt_rsa_chat.py)

Enabling “Super-Safe Encryption” in the GUI triggers RSA key generation inside `ChatLogic.generate_rsa_key_from_lcg`. The modulus is constructed as the product of 8 small 256‑bit primes deterministically derived from a predictable seed (hostname → SHA‑256 → linear congruential outputs filtered for 256‑bit primes). Only the public key `(n, e)` is saved to `public.pem`; ciphertexts are logged in `chat_log.json`.

## Vulnerabilities

- Deterministic seed: $\text{ hostname } \rightarrow \text{ SHA‑256 } \rightarrow \text{ no entropy }$.
- Weak prime sourcing: $LCG + \text{hash iteration}$, fully reproducible.
- Multi‑prime RSA with $8 × 256‑bit$ factors: trivially factorable (FactorDB / ECM).
- Textbook RSA (no padding).

## RSA Construction

Collected primes: $p_1,\dots,p_8$ (all 256‑bit).  
Modulus: $N = \prod_{i=1}^{8} p_i$.  
Euler totient: $ \varphi(N) = \prod_{i=1}^{8} (p_i - 1)$.  
Public exponent: $e = 65537$.  
Private exponent: $d = e^{-1} \bmod \varphi(N)$.

## Ciphertext Encoding (RSA mode)

1. Plaintext → UTF‑8 bytes → big‑endian integer $m$.  
2. Compute $c = m^e \bmod N.$  
3. Serialize: little‑endian full‑length bytes of $c$, then strip trailing `0x00`.  
4. Hex string stored in `chat_log.json`.

## Exploitation Steps

1. Extract `(n, e)` from `public.pem`.
2. Submit `n` to FactorDB → obtain all 8 primes.
3. Verify $\prod p_i = n$.
4. Compute $\varphi(N)$ and $d$.
5. For each RSA log entry:  
   - Parse hex → bytes → integer with little‑endian.  
   - Decrypt: $m = c^d \bmod N$.  
   - Convert `m` to big‑endian minimal bytes → decode UTF‑8.
6. (Optional) Re‑encrypt to confirm serialization symmetry.

## Solver Script

[decrypt_rsa_chat.py](h:\Github\FlareOn\FlareOn12\Ch6\decrypt_rsa_chat.py) automates: factor validation, $\varphi(N)$, modular inverse, ciphertext parsing, decryption, and plaintext recovery.

## Root Cause

Security assumption of RSA broken by design: deterministic, low‑entropy multi‑prime modulus with tiny equal factors. Padding omission + reversible custom encoding makes decryption immediate once factors are known.

## Mitigation (Real World)

Use library RSA keygen (two large random primes), OAEP padding, CSPRNG seeding, and standard serialization.

## Summary

Factor the deliberately weak multi‑prime modulus, derive $d$, invert the endian/minimal‑length encoding, and recover the plaintext messages—complete compromise of the “Super‑Safe” mode.
