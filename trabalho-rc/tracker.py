# tracker.py
import socket, json
from threading import Thread
from encrypt_utils import generate_rsa_keys, serialize_public_key, deserialize_public_key, encrypt_with_public_key, decrypt_with_private_key, hash_password

class Tracker:
    def __init__(self, host='0.0.0.0', port=6000, max_connec=5):
        self.host = host
        self.port = port
        self.server_info = (host, port)
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind(self.server_info)
        self.server.listen(max_connec)

        self.private_key, self.public_key = generate_rsa_keys()
        self.public_key_str = serialize_public_key(self.public_key)

        self.users = {
            "tonhao": {
                "password": hash_password("senha123"),  
                'active': False
            }
        }
        self.active_peers = {}
        self.chat_rooms = {}

        print(f"Tracker iniciado em {self.host}:{self.port}")
        print("Aguardando conexões...")

    def listen(self):
        while True:
            peer_conec, address = self.server.accept()
            print("Conexao de: " + str(address))
            Thread(target=self.process_new_peer, args=(peer_conec, address)).start()

    def process_new_peer(self, peer_conec, address):
        peer_conec.send(json.dumps({"public_key": self.public_key_str}).encode())
        
        peer_public_key_str = json.loads(peer_conec.recv(4096).decode())["public_key"]
        peer_public_key = deserialize_public_key(peer_public_key_str)
        
        while True:
            encrypted_data = peer_conec.recv(4096).decode()
            data = decrypt_with_private_key(self.private_key, encrypted_data)
            peer_requisition = json.loads(data)
            
            cmd = peer_requisition.get("cmd")
            
            match cmd:
                case "login":
                    response = self.process_peer_login(peer_requisition)
                    encrypted_response = encrypt_with_public_key(peer_public_key, json.dumps(response))
                    peer_conec.send(encrypted_response.encode())

                    if response.get("status") == "ok":
                        self.process_chat()
                case "register":
                    response = self.process_peer_register(peer_requisition)
                    encrypted_response = encrypt_with_public_key(peer_public_key, json.dumps(response))
                    peer_conec.send(encrypted_response.encode())

                    if response.get("status") == "ok":
                        continue
                    else:
                        self.process_peer_register(peer_requisition)

    def process_peer_login(self, peer_req):
        user = peer_req.get("usr")
        password = peer_req.get("password")

        if user in self.users and self.users[user]["password"] == hash_password(password):
            self.users[user]["active"] = True
            return {"status": "ok", "message": "Login bem sucedido"}

        return {"status": "error", "message": "Usuario ou senha incorretos"}

    def process_peer_register(self, peer_req):
        user = peer_req.get("usr")
        password = peer_req.get("password")

        if user in self.users:
            return {"status": "error", "message": "Usuario ja existente"}
        else:
            new_user = {
                user: {
                    "password": hash_password(password),
                    "active": False
                }
            }
            self.users.update(new_user)
            print(self.users)
            return {"status": "ok", "message": "Usuario registrado!"}

    def process_chat(self):
        ...

if __name__ == "__main__":
    tracker = Tracker()
    tracker.listen()