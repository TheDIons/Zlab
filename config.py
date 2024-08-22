import os
from cryptography.fernet import Fernet

def generate_key():
    return Fernet.generate_key()

# If you don't have a key, generate one and print it
if not os.path.exists('encryption_key.key'):
    key = generate_key()
    with open('encryption_key.key', 'wb') as key_file:
        key_file.write(key)
    print(f"New encryption key generated and saved to 'encryption_key.key'")
else:
    with open('encryption_key.key', 'rb') as key_file:
        key = key_file.read()

ENCRYPTION_KEY = key

def encrypt(message: str) -> str:
    return Fernet(ENCRYPTION_KEY).encrypt(message.encode()).decode()

def decrypt(token: str) -> str:
    return Fernet(ENCRYPTION_KEY).decrypt(token.encode()).decode()

# Use this function to encrypt your Pastebin URL
def encrypt_pastebin_url(url):
    encrypted_url = encrypt(url)
    print(f"Encrypted Pastebin URL: {encrypted_url}")
    print("Copy this encrypted URL and replace ENCRYPTED_PASTEBIN_URL in the config file.")

ENCRYPTED_PASTEBIN_URL = "gAAAAABmx8e5ET79ELBVISzOso-4gv_BEGZohGihXXpgrNBAb4RbX5u9PivKXW3NhxnJpKHjGffJVIVrSPPPiUuyWKQROYs7TE2keWd9YxWyiiMo1elwvvdRpOJkNVV07k5vkW6e_C5y"

if __name__ == "__main__":
    pass