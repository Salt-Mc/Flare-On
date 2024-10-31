from Crypto.Cipher import ChaCha20
import base64
  
def initialize_salsa20_cipher(hash512):  
    """  
    Initialize a Salsa20 cipher using a 512-bit hash.  
  
    :param hash512: A bytes object containing the 512-bit hash.  
    :return: An initialized Salsa20 cipher object.  
    """  
    if len(hash512) < 40:  
        raise ValueError("Insufficient hash length for key and nonce extraction (needs at least 40 bytes)")  
  
    # Extract the 32-byte key from bytes 0-31  
    key = hash512[0:32]
    # print("Key:", key.hex())
  
    # Extract the 8-byte nonce from bytes 32-39  
    nonce = hash512[32:40]
    # print("Nonce:", nonce.hex())
  
    # Initialize the Salsa20 cipher  
    cipher = ChaCha20.new(key=key, nonce=nonce)  
    return cipher  
  
if __name__ == "__main__":  
    import hashlib  
    
    shared_secret = "3C 54 F9 0F 4D 2C C9 C0 B6 2D F2 86 6C 2B 4F 0C 5A FA E8 13 6D 2A 1E 76 D2 69 49 99 62 43 25 F5 60 9C 50 B4 67 7E FA 21 A3 76 64 B5 0C EC 92 C0"
    data = bytes.fromhex(shared_secret) 
    hash512 = hashlib.sha512(data).digest()
    #print("Key Hash512:", hash512.hex(), "\n")

    if len(hash512) != 64:  
        raise ValueError("Hash is not 512 bits long")
  
    cipher = initialize_salsa20_cipher(hash512)  
  
    # Now you can use the cipher to encrypt or decrypt data.  
    plaintext = b"verify\x00"  
    ciphertext = cipher.encrypt(plaintext)

    FLAG_HEX = '31b6dac62ef1ad8dc1f60b79265ed0deaa31ddd2d53aa9fd9343463810f3e2232406366b48415333d4b8ac336d4086efa0f15e6e59'

    # Verify the encrypted hex matches the expected value'
    if ciphertext.hex() != "f272d54c31860f":
        raise ValueError("Ciphertext does not match expected value")

    # if verification is successful, decrypt the ciphertext

    list_of_recv_and_send_cipher = [
         ('f272d54c31860f', b'verify\x00')
        ,('86dfd7', b'\xaa'*53+b'\x00')
        ,('fcb1d2cdbba979c989998c', b'ok\x00')
        ,('ce39da', b'\xaa'*44+b'\x00')
        ,('2cae600b5f32cea193e0de63d709838bd6', b'ok\x00')
        ,('edf0fc', b'\xaa'*38+b'\x00')
        ,('aec8d27a7cf26a17273685', b'ok\x00')
        ,('2f3917', b'\xaa'*73+b'\x00')
        ,('f5981f71c7ea1b5d8b1e5f06fc83b1def38c6f4e694e3706412eabf54e3b6f4d19e8ef46b04e399f2c8ece8417fa', b'ok\x00')
        ,('54e41e', b'\xaa'*39+b'\x00')
        ,('5ca68d1394be2a4d3d4d7c82e5', bytes.fromhex(FLAG_HEX)) # FLAG
        ,('0d1ec06f36', b'end\x00')
    ]

    list_of_sent_cipher = [
         b'veriy'
        ,b' '
    ]

    dcipher = initialize_salsa20_cipher(hash512)
    
    for cipher_recv, cipher_sent in list_of_recv_and_send_cipher:
        #dcipher = initialize_salsa20_cipher(hash512)
        cipher_rev_bytes = bytes.fromhex(cipher_recv)
        cipher_sent_bytes = cipher_sent
        decrypted_recv = dcipher.decrypt(cipher_rev_bytes).decode('utf-8')
        decrypted_sent = dcipher.decrypt(cipher_sent_bytes)
        print(f"Command: {decrypted_recv} {' '*(50 - len(decrypted_recv))} -> Response: {decrypted_sent.hex()[:20]} ...")
        # if command is cat|flag, show the flag
        if decrypted_recv.find('cat') != -1:
            print(
                f"\n============================================================================================\n\
                 FLAG: {base64.b64decode(decrypted_sent.decode('utf-8')).decode()}\
                \n============================================================================================\n")
