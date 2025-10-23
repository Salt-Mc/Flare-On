
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

iv = get_bytes(get_name_ea(0, "iv"), 16)
k = bytes.fromhex("600abf28e03c73471a73bb909210dc2d2b4e98c7577d6b71299d2e54d693d14d")

ciph = get_bytes(get_name_ea(0, "encrypted_flag"), 80)
cipher = AES.new(k, AES.MODE_CTR, iv)
cipher.decrypt(ciph).decode("utf-8")
decrypted_data = unpad(cipher.decrypt(ciph), AES.block_size)

print(decrypted_data)