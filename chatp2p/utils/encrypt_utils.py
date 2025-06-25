from nacl.public import PrivateKey, PublicKey, Box
from nacl.encoding import Base64Encoder
import base64, hashlib

def generate_ecc_keys():
    private_key = PrivateKey.generate()
    public_key = private_key.public_key
    return private_key, public_key

def serialize_public_key(public_key):
    return public_key.encode(encoder=Base64Encoder).decode('utf-8')

def deserialize_public_key(public_key_str):
    return PublicKey(public_key_str.encode('utf-8'), encoder=Base64Encoder)

def encrypt_with_public_key(public_key, message):
    if isinstance(message, str):
        message = message.encode('utf-8')
    
    ephemeral_private = PrivateKey.generate()
    ephemeral_public = ephemeral_private.public_key
    
    # Cria uma caixa de criptografia
    box = Box(ephemeral_private, public_key)
    
    # Criptografa a mensagem
    encrypted = box.encrypt(message)
    
    # Combina a chave pública efêmera com a mensagem criptografada
    combined = bytes(ephemeral_public) + encrypted
    
    return base64.b64encode(combined).decode('utf-8')

def decrypt_with_private_key(private_key, encrypted_message):
    encrypted_message = base64.b64decode(encrypted_message)
    
    # Extrai a chave pública efêmera (32 bytes) e o texto cifrado
    ephemeral_public_bytes = encrypted_message[:32]
    ciphertext = encrypted_message[32:]
    
    ephemeral_public = PublicKey(ephemeral_public_bytes)
    
    # Cria a caixa de descriptografia
    box = Box(private_key, ephemeral_public)
    
    # Descriptografa a mensagem
    decrypted = box.decrypt(ciphertext)    
    return decrypted.decode('utf-8')

def hash_password(password):
    if isinstance(password, str):
        password = password.encode('utf-8')
    
    sha256_hash = hashlib.sha256()
    sha256_hash.update(password)
    return sha256_hash.hexdigest()