# Source Generated with Decompyle++
# File: challenge_to_compile.pyc (Python 3.12)

import tkinter as tk
from tkinter import scrolledtext, messagebox, simpledialog, Checkbutton, BooleanVar, Toplevel
import platform
import hashlib
import time
import json
from threading import Thread
import math
import random
from Crypto.PublicKey import RSA
from Crypto.Util.number import bytes_to_long, long_to_bytes, isPrime
import os
import sys
try:
    global Web3, Account, LocalAccount
    from web3 import Web3 as Web3
    from eth_account import Account as Account
    from eth_account.signers.local import LocalAccount as LocalAccount
except ImportError:
    Web3 = Account = LocalAccount = None

def resource_path(relative_path):
    """
    Get the absolute path to a resource, working both in development and
    when bundled by PyInstaller (where sys._MEIPASS is injected).
    """
    try:
        base_path = sys._MEIPASS          # PyInstaller temp folder
    except Exception:                     # Matches broad Exception check in bytecode
        base_path = os.path.abspath('.')  # Fallback to current directory
    return os.path.join(base_path, relative_path)

class SmartContracts:
    rpc_url = ''
    private_key = ''
    
    def deploy_contract(contract_bytes, contract_abi):
        """
        Reconstructed exactly from bytecode:
          - Single try covering all deployment steps.
          - Early return if tx_receipt.status == 0.
          - Ordered except blocks: ConnectionError, ValueError, generic Exception.
          - All print strings and arithmetic (gas_estimate + 200000) preserved.
        """
        try:
            w3 = Web3(Web3.HTTPProvider(SmartContracts.rpc_url))
            if not w3.is_connected():
                raise ConnectionError(f"[!] Failed to connect to Ethereum network at {SmartContracts.rpc_url}")
            print(f"[+] Connected to Sepolia network at {SmartContracts.rpc_url}")
            print(f"[+] Current block number: {w3.eth.block_number}")
            
            if not SmartContracts.private_key:
                raise ValueError("Please add your private key.")
            
            account = Account.from_key(SmartContracts.private_key)
            w3.eth.default_account = account.address
            print(f"[+] Using account: {account.address}")
            
            balance_wei = w3.eth.get_balance(account.address)
            print(f"[+] Account balance: {w3.from_wei(balance_wei, 'ether')} ETH")
            if balance_wei == 0:
                print("[!] Warning: Account has 0 ETH. Deployment will likely fail. Get some testnet ETH from a faucet (e.g., sepoliafaucet.com)!");
            
            Contract = w3.eth.contract(abi=contract_abi, bytecode=contract_bytes)
            gas_estimate = Contract.constructor().estimate_gas()
            print(f"[+] Estimated gas for deployment: {gas_estimate}")
            
            gas_price = w3.eth.gas_price
            print(f"[+] Current gas price: {w3.from_wei(gas_price, 'gwei')} Gwei")
            
            transaction = Contract.constructor().build_transaction({
                'from': account.address,
                'nonce': w3.eth.get_transaction_count(account.address),
                'gas': gas_estimate + 200000,
                'gasPrice': gas_price
            })
            
            signed_txn = w3.eth.account.sign_transaction(
                transaction,
                private_key=SmartContracts.private_key
            )
            
            print("[+]  Deploying contract...")
            tx_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)
            print(f"[+] Deployment transaction sent. Hash: {tx_hash.hex()}")
            print("[+] Waiting for transaction to be mined...")
            
            tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
            print(f"[+] Transaction receipt: {tx_receipt}")
            
            if tx_receipt.status == 0:
                print("[!] Transaction failed (status 0). It was reverted.")
                return None
            
            contract_address = tx_receipt.contractAddress
            print(f"[+] Contract deployed at address: {contract_address}")
            deployed_contract = w3.eth.contract(address=contract_address, abi=contract_abi)
            return deployed_contract
        
        except ConnectionError as e:
            print(f"[!] Connection error: {e}")
            print("Please check your RPC_URL and network connection.")
            return None
        except ValueError as e:
            print(f"[!] Configuration error: {e}")
            return None
        except Exception as e:
            print(f"[!] An unexpected error occurred: {e}")
            return None



class LCGOracle:
    """
    Pure Python version of the LCG contract function (selector 0x11521834).
    Solidity-equivalent logic:
        if counter > 0:
            new_state = ((state * multiplier) % modulus + increment) % modulus
            return new_state
        else:
            return state
    Note: Original on-chain function is pure (no mutation). We mutate self.state locally
    to emulate a sequential RNG usage pattern off-chain.
    """
    def __init__(self, multiplier, increment, modulus, initial_seed):
        if modulus == 0:
            raise ValueError("LCG modulus must be non-zero (contract would revert).")
        self.multiplier = multiplier
        self.increment = increment
        self.modulus = modulus
        self.state = initial_seed

    def _nextVal(self, multiplier, increment, modulus, current_state, counter):
        if modulus == 0:
            raise ZeroDivisionError("Modulus zero (contract Panic(18)).")
        if counter > 0:
            return ((current_state * multiplier) % modulus + increment) % modulus
        return current_state

    def get_next(self, counter: int):
        # WARNING: ChatLogic never increments message_count, so counter may remain 0
        # and thus the state will not advance. This mirrors true contract semantics.
        print(f"\n[+] Calling nextVal() with _currentState={self.state}")
        self.state = self._nextVal(self.multiplier, self.increment, self.modulus, self.state, counter)
        print(f"  _counter = {counter}: Result = {self.state}")
        return self.state



class TripleXOROracle:
    """
    Pure Python version of the TripleXOR encrypt function (selector 0x62300756).
    EVM logic:
        word = (len(plaintext) <= 32) ? first 32B word (plaintext + zero padding) : 0
        return prime ^ conversationTime ^ word  (as 32-byte big-endian)
    """
    def __init__(self):
        pass

    @staticmethod
    def _word_from_plaintext(plaintext):
        if isinstance(plaintext, str):
            b = plaintext.encode('utf-8')
        else:
            b = plaintext
        if len(b) > 32:
            return 0
        padded = b + b'\x00' * (32 - len(b))
        return int.from_bytes(padded, 'big')

    def encrypt(self, prime_from_lcg: int, conversation_time: int, plaintext):
        print(f"\n[+] Calling encrypt() with prime_from_lcg={prime_from_lcg}, time={conversation_time}, plaintext={plaintext}")
        word = self._word_from_plaintext(plaintext)
        result = prime_from_lcg ^ conversation_time ^ word
        ciphertext = result.to_bytes(32, 'big')
        print(f"  _ciphertext = {ciphertext.hex()}")
        return ciphertext



class ChatLogic:
    
    def __init__(self):
        self.lcg_oracle = None
        self.xor_oracle = None
        self.rsa_key = None
        self.seed_hash = None
        self.super_safe_mode = False
        self.message_count = 0
        self.conversation_start_time = 0
        self.chat_history = []
        self._initialize_crypto_backend()

    
    def _get_system_artifact_hash(self):
        artifact = platform.node().encode('utf-8')
        hash_val = hashlib.sha256(artifact).digest()
        seed_hash = int.from_bytes(hash_val, 'little')
        print(f'''[SETUP]  - Generated Seed {seed_hash}...''')
        return seed_hash

    
    def _generate_primes_from_hash(self, seed_hash):
        """
        Reconstructed from disassembly:
          - Deterministically derive 256-bit prime parameters from SHA-256 chaining.
          - Collect exactly 3 primes (multiplier, increment, modulus) or abort.
        """
        primes = []
        current_hash_byte_length = (seed_hash.bit_length() + 7) // 8
        current_hash = seed_hash.to_bytes(current_hash_byte_length, 'little')
        print('[SETUP] Generating LCG parameters from system artifact...')
        iteration_limit = 10000
        iterations = 0

        # True structure (disassembly showed a loop via backward jump)
        while len(primes) < 3 and iterations < iteration_limit:
            current_hash = hashlib.sha256(current_hash).digest()
            candidate = int.from_bytes(current_hash, 'little')
            iterations += 1
            if candidate.bit_length() == 256 and isPrime(candidate):
                primes.append(candidate)
                # Matches original truncation pattern: str(candidate)[:20] + '...'
                print(f"[SETUP]  - Found parameter {len(primes)}: {str(candidate)[:20]}...")
        
        if len(primes) < 3:
            error_msg = '[!] Error: Could not find 3 primes within iteration limit.'
            print('Current Primes: ', primes)
            print(error_msg)
            # Preserve original termination behavior (exit()), but clearer explicit exit.
            # If you prefer raising an exception, replace with: raise RuntimeError(error_msg)
            exit()

        return (primes[0], primes[1], primes[2])

    
    def _initialize_crypto_backend(self):
        self.seed_hash = self._get_system_artifact_hash()
        (m, c, n) = self._generate_primes_from_hash(self.seed_hash)
        self.lcg_oracle = LCGOracle(m, c, n, self.seed_hash)
        print('[SETUP] LCG Oracle initialized (pure Python).')
        self.xor_oracle = TripleXOROracle()
        print('[SETUP] Triple XOR Oracle initialized (pure Python).')
        print('[SETUP] Crypto backend initialized (no smart contracts).')

    
    def generate_rsa_key_from_lcg(self):
        print('[RSA] Generating RSA key from LCG sequence (pure Python)...')
        # Rebuild fresh LCG sequence deterministically
        lcg_for_rsa = LCGOracle(
            self.lcg_oracle.multiplier,
            self.lcg_oracle.increment,
            self.lcg_oracle.modulus,
            self.seed_hash
        )

        primes_arr = []
        rsa_msg_count = 0
        iteration_limit = 10000
        iterations = 0

        # Loop until we have 8 qualifying 256-bit primes or hit iteration limit
        while len(primes_arr) < 8 and iterations < iteration_limit:
            candidate = lcg_for_rsa.get_next(rsa_msg_count)
            rsa_msg_count += 1
            iterations += 1
            if candidate.bit_length() == 256 and isPrime(candidate):
                primes_arr.append(candidate)
                print(f'[RSA]  - Found 256-bit prime #{len(primes_arr)}')

        print('Primes Array: ', primes_arr)
        if len(primes_arr) < 8:
            error_msg = '[RSA] Error: Could not find 8 primes within iteration limit.'
            print('Current Primes: ', primes_arr)
            print(error_msg)
            return error_msg

        n = 1
        for p_val in primes_arr:
            n *= p_val

        phi = 1
        for p_val in primes_arr:
            phi *= (p_val - 1)

        e = 65537
        if math.gcd(e, phi) != 1:
            error_msg = '[RSA] Error: Public exponent e is not coprime with phi(n). Cannot generate key.'
            print(error_msg)
            return error_msg

        try:
            # Public key only (no factors provided)
            self.rsa_key = RSA.construct((n, e))
            with open('public.pem', 'wb') as f:
                f.write(self.rsa_key.export_key('PEM'))
            print("[RSA] Public key generated and saved to 'public.pem'")
            return 'Public key generated and saved successfully.'
        except Exception as ex:
            print(f'[RSA] Error saving key: {ex}')
            return None

    
    def process_message(self, plaintext):
        if self.conversation_start_time == 0:
            self.conversation_start_time = time.time()
        conversation_time = int(time.time() - self.conversation_start_time)
        if self.super_safe_mode and self.rsa_key:
            plaintext_bytes = plaintext.encode('utf-8')
            plaintext_enc = bytes_to_long(plaintext_bytes)
            _enc = pow(plaintext_enc, self.rsa_key.e, self.rsa_key.n)
            ciphertext = _enc.to_bytes(self.rsa_key.n.bit_length(), 'little').rstrip(b'\x00')
            encryption_mode = 'RSA'
            plaintext = '[ENCRYPTED]'
        else:
            prime_from_lcg = self.lcg_oracle.get_next(self.message_count)
            ciphertext = self.xor_oracle.encrypt(prime_from_lcg, conversation_time, plaintext)
            encryption_mode = 'LCG-XOR'
        log_entry = {
            'conversation_time': conversation_time,
            'mode': encryption_mode,
            'plaintext': plaintext,
            'ciphertext': ciphertext.hex() }
        self.chat_history.append(log_entry)
        self.save_chat_log()
        return (f'''[{conversation_time}s] {plaintext}''', f'''[{conversation_time}s] {ciphertext.hex()}''')

    
    def save_chat_log(self):
        """
        Persist the in‑memory chat history to chat_log.json (pretty-printed).
        Reconstructed from decompiler artifact:
          - Writes self.chat_history with indent=2
          - On error prints a message (original artifact showed a print in an Exception block)
        """
        try:
            with open('chat_log.json', 'w', encoding='utf-8') as f:
                json.dump(self.chat_history, f, indent=2)
        except Exception as e:
            # Preserve the semantic intent of the decompiled print
            print(f"Error saving chat log: {e}")
        return None



class ChatApp(tk.Tk):
    
    def __init__(self = None):
        super().__init__()
        self.title('Chain of Demands - Secure Chat')
        self.geometry('1000x800')
        top_frame = tk.Frame(self, bd = 5)
        top_frame.pack(fill = 'x')
        chat_frame = tk.Frame(self, bd = 5)
        chat_frame.pack(expand = True, fill = 'both')
        input_frame = tk.Frame(self, bd = 5)
        input_frame.pack(fill = 'x')
        tk.Label(top_frame, text = 'Connect to IP:').pack(side = 'left')
        self.ip_entry = tk.Entry(top_frame, width = 20)
        self.ip_entry.insert(0, '127.0.0.1')
        self.ip_entry.pack(side = 'left', padx = 5)
        self.connect_button = tk.Button(top_frame, text = 'Connect', command = self.connect_to_peer)
        self.connect_button.pack(side = 'left')
        self.load_files_button = tk.Button(top_frame, text = 'Last Convo', command = self.load_last_generated_files)
        self.load_files_button.pack(side = 'left', padx = 10)
        self.web3_config_button = tk.Button(top_frame, text = 'Web3 Config', command = self.open_web3_config_window)
        self.web3_config_button.pack(side = 'left')
        self.status_label = tk.Label(top_frame, text = 'Status: Disconnected', fg = 'red')
        self.status_label.pack(side = 'left', padx = 10)
        self.chat_box = scrolledtext.ScrolledText(chat_frame, state = 'disabled', wrap = tk.WORD, bg = '#f0f0f0')
        self.chat_box.pack(expand = True, fill = 'both')
        self.msg_entry = tk.Entry(input_frame, width = 60)
        self.msg_entry.pack(side = 'left', expand = True, fill = 'x', padx = 5)
        self.msg_entry.bind('<Return>', self.send_message_event)
        self.msg_entry.config(state = 'disabled')
        self.send_button = tk.Button(input_frame, text = 'Send', command = self.send_message_event)
        self.send_button.pack(side = 'left')
        self.send_button.config(state = 'disabled')
        self.super_safe_var = BooleanVar()
        self.super_safe_check = Checkbutton(top_frame, text = 'Enable Super-Safe Encryption', variable = self.super_safe_var, command = self.toggle_super_safe)
        self.super_safe_check.pack(side = 'right', padx = 10)
        self.logic = ChatLogic()

    
    def open_web3_config_window(self):
        config_window = Toplevel(self)
        config_window.title('Web3 Configuration')
        config_window.geometry('650x150')
        config_window.resizable(False, False)
        main_frame = tk.Frame(config_window, padx = 10, pady = 10)
        main_frame.pack(expand = True, fill = 'both')
        tk.Label(main_frame, text = 'RPC URL:').grid(row = 0, column = 0, sticky = 'w', pady = 5)
        rpc_entry = tk.Entry(main_frame, width = 60)
        rpc_entry.grid(row = 0, column = 1, sticky = 'ew')
        rpc_entry.insert(0, SmartContracts.rpc_url)
        tk.Label(main_frame, text = 'Private Key:').grid(row = 1, column = 0, sticky = 'w', pady = 5)
        pk_entry = tk.Entry(main_frame, width = 60)
        pk_entry.grid(row = 1, column = 1, sticky = 'ew')
        pk_entry.insert(0, SmartContracts.private_key)
        
        def save_and_close():
            new_rpc_url = rpc_entry.get().strip()
            new_pk = pk_entry.get().strip()
            if new_rpc_url and new_pk:
                SmartContracts.rpc_url = new_rpc_url
                SmartContracts.private_key = new_pk
                print(f'''[CONFIG] Web3 RPC URL updated to: {new_rpc_url}''')
                print('[CONFIG] Web3 Private Key updated.')
                messagebox.showinfo('Success', 'Web3 configuration has been updated.', parent = config_window)
                config_window.destroy()
                return None
            messagebox.showerror('Error', 'Both fields are required.', parent = config_window)

        save_button = tk.Button(main_frame, text = 'Save & Close', command = save_and_close)
        save_button.grid(row = 2, column = 1, sticky = 'e', pady = 10)
        config_window.transient(self)
        config_window.grab_set()
        self.wait_window(config_window)
        self.logic = ChatLogic()

    
    def connect_to_peer(self):
        ip = self.ip_entry.get()
        if ip:
            self.status_label.config(text = f'''Status: Connected to {ip}''', fg = 'green')
            self.display_message_in_box('--- Welcome to Secure Chat ---', 'system')
            self.display_message_in_box(f'''[SYSTEM] Connection to {ip} established.\n''', 'system')
            self.display_message_in_box('You are now talking with the ransomware operator.', 'system')
            self.display_message_in_box('--------------------------------------------------\n', 'system')
            self.msg_entry.config(state = 'normal')
            self.send_button.config(state = 'normal')
            return None

    
    def display_message_in_box(self, message, tag):
        self.chat_box.config(state = 'normal')
        self.chat_box.insert(tk.END, message + '\n', tag)
        self.chat_box.config(state = 'disabled')
        self.chat_box.see(tk.END)
        self.chat_box.tag_config('user', foreground = 'blue')
        self.chat_box.tag_config('peer', foreground = 'green')
        self.chat_box.tag_config('system', foreground = 'red')
        self.chat_box.tag_config('error', foreground = 'orange')

    
    def send_message_event(self, event = (None,)):
        msg = self.msg_entry.get()
        if msg:
            self.display_message_in_box(f'''You: {msg}''', 'user')
            (_, encrypted_msg_display) = self.logic.process_message(msg)
            self.display_message_in_box(f'''Peer (Encrypted): {encrypted_msg_display}''', 'peer')
            self.msg_entry.delete(0, tk.END)
            return None

    
    def toggle_super_safe(self):
        if self.super_safe_var.get():
            self.logic.super_safe_mode = True
            self.display_message_in_box('[SYSTEM] Super-Safe mode enabled. Generating RSA key...', 'system')
            Thread(target = self.generate_rsa_and_update_gui, daemon = True).start()
            return None
        self.logic.super_safe_mode = False
        self.display_message_in_box('[SYSTEM] Super-Safe mode disabled. Reverting to standard LCG-XOR.', 'system')

    
    def generate_rsa_and_update_gui(self):
        result_msg = self.logic.generate_rsa_key_from_lcg()
        self.display_message_in_box(f'''[SYSTEM] {result_msg}''', 'system')

    
    def load_last_generated_files(self):
        files_window = Toplevel(self)
        files_window.title('Generated Files')
        files_window.geometry('700x500')

        # ----- chat_log.json section -----
        tk.Label(files_window, text='chat_log.json', font=('Helvetica', 12, 'bold')).pack(pady=(10, 0))
        json_text_area = scrolledtext.ScrolledText(files_window, wrap=tk.WORD, height=15)
        json_text_area.pack(expand=True, fill='both', padx=10, pady=5)

        try:
            json_path = resource_path('chat_log.json')
            with open(json_path, 'r') as f:
                json_data = json.load(f)
            pretty_json = json.dumps(json_data, indent=2)
            json_text_area.insert(tk.END, pretty_json)
        except FileNotFoundError:
            json_text_area.insert(
                tk.END,
                'chat_log.json not found.\n\nSend a message to generate it.'
            )
        except Exception as e:
            json_text_area.insert(
                tk.END,
                f'Error reading chat_log.json:\n{e}'
            )
        json_text_area.config(state='disabled')

        # ----- public.pem section -----
        tk.Label(files_window, text='public.pem', font=('Helvetica', 12, 'bold')).pack(pady=(10, 0))
        pem_text_area = scrolledtext.ScrolledText(files_window, wrap=tk.WORD, height=8)
        pem_text_area.pack(expand=True, fill='both', padx=10, pady=(5, 10))

        try:
            pem_path = resource_path('public.pem')
            with open(pem_path, 'r') as f:
                pem_data = f.read()
            pem_text_area.insert(tk.END, pem_data)
        except FileNotFoundError:
            pem_text_area.insert(
                tk.END,
                "public.pem not found.\n\nEnable 'Super-Safe Encryption' to generate it."
            )
        except Exception as e:
            pem_text_area.insert(
                tk.END,
                f'Error reading public.pem:\n{e}'
            )
        pem_text_area.config(state='disabled')

        return None

    __classcell__ = None

if __name__ == '__main__':
    app = ChatApp()
    app.mainloop()
