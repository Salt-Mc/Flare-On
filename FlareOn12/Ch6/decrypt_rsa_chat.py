import json
from math import prod
from math import gcd

# 1. Load public key (optional sanity check)
from Crypto.PublicKey import RSA
with open("public.pem","rb") as f:
    pub = RSA.import_key(f.read())
n = pub.n
e = pub.e
print(f"[+] Loaded public key: n bits = {n.bit_length()}, e = {e}")

# 2. Paste the 8 prime factors from FactorDB EXACTLY (one per line)
primes_text = """
62826068095404038148338678434404643116583820572865189787368764098892510936793
68446593057460676025047989394445774862028837156496043637575024036696645401289
69802783227378026511719332106789335301376047817734407431543841272855455052067
72967016216206426977511399018380411256993151454761051136963936354667101207529
75395288067150543091997907493708187002382230701390674177789205231462589994993
79611551309049018061300429096903741339200167241148430095608259960783012192237
82836473202091099900869551647600727408082364801577205107017971703263472445197
88790251731800173019114073860734130032527125661685690883849562991870715928701
""".strip()

primes = [int(line.strip()) for line in primes_text.splitlines()]
assert len(primes) == 8, "Need exactly 8 primes"

# 3. Sanity checks
recomputed_n = prod(primes)
if recomputed_n != n:
    raise ValueError("Provided primes do not multiply back to n (copy error?)")
print("[+] Primes verified: product matches modulus.")

# 4. Compute phi(n)
phi = 1
for p in primes:
    phi *= (p - 1)

# 5. Modular inverse to get d
# Python 3.8+: pow(e, -1, phi) gives modular inverse
d = pow(e, -1, phi)
print("[+] Computed private exponent d (bit length:", d.bit_length(), ")")

# 6. Load chat log
with open("chat_log.json","r") as f:
    chat = json.load(f)

rsa_msgs = [entry for entry in chat if entry.get("mode") == "RSA"]
print(f"[+] Found {len(rsa_msgs)} RSA ciphertext entries.")

def decrypt_ct(hex_ct: str) -> bytes:
    ct_bytes = bytes.fromhex(hex_ct)
    c = int.from_bytes(ct_bytes, 'little')  # reverse their storage format
    m = pow(c, d, n)
    # Convert back to bytes (minimal big-endian length)
    m_bytes = m.to_bytes((m.bit_length() + 7)//8, 'big')
    return m_bytes

for i, entry in enumerate(rsa_msgs, 1):
    hex_ct = entry["ciphertext"]
    raw = decrypt_ct(hex_ct)
    # Try to decode; fall back to repr
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        text = repr(raw)
    print(f"\n[Cipher {i}] conversation_time={entry['conversation_time']}")
    print(f"  Ciphertext (len {len(hex_ct)//2} bytes): {hex_ct[:32]}...{hex_ct[-32:]}")
    print(f"  Decrypted bytes ({len(raw)}): {raw.hex()}")
    print(f"  As text: {text}")

# 7. (Optional) Re-encrypt to verify round trip
def reencryption_check(plaintext_bytes: bytes):
    from Crypto.Util.number import bytes_to_long
    m_int = int.from_bytes(plaintext_bytes, 'big')
    c = pow(m_int, e, n)
    # Serialize like app: little-endian full length then strip trailing zeros
    full_le = c.to_bytes((n.bit_length()+7)//8, 'little')
    trimmed = full_le.rstrip(b'\x00')
    return trimmed.hex()

# (Optional) Add a test if you recover a plaintext and want to confirm