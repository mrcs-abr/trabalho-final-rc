import socket, json, threading
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
            #usuario test
            "teste": {
                "password": hash_password("senha123"),  
            }
        }
        self.active_peers = {}
        self.chat_rooms = {}

        # Avoid race coditions when accessing server storage
        self.users_lock = threading.Lock()
        self.active_peers_lock = threading.Lock()
        self.chat_rooms_lock= threading.Lock()

        print(f"Tracker iniciado em {self.host}:{self.port}")
        print("Aguardando conexões...")

    def listen(self):
        while True:
            peer_conec, address = self.server.accept()
            print("Conexao de: " + str(address))
            Thread(target=self.process_new_peer, args=(peer_conec, address)).start()

    def process_new_peer(self, peer_conec, address):
            user = None
            try:
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
                            response = self.process_peer_login(peer_requisition, address)
                            if response.get("status") == "ok":
                                user = response.get("usr")

                        case "register":
                            response = self.process_peer_register(peer_requisition)
                        
                        case "list-peers":
                            response = self.list_peers()

                        case "list-rooms":
                            response = self.list_rooms()
                        case _:
                            response = {"status": "error", "message": "Comando inválido"}

                    print(response)
                    encrypted_response = encrypt_with_public_key(peer_public_key, json.dumps(response))
                    peer_conec.send(encrypted_response.encode())
            
            except (ConnectionResetError, json.JSONDecodeError, ValueError) as e:
                print(f"Erro de conexão com peer {str(address)}: {str(e)}")
                if user is not None:
                    with self.active_peers_lock:
                        if user in self.active_peers:
                            del self.active_peers[user]
                            print(f"Peer {user} desconectado. Active_peers: {self.active_peers}")
                peer_conec.close()

    def process_peer_login(self, peer_req, address):
        user = peer_req.get("usr")
        password = peer_req.get("password")
        peer_ip, peer_port = address

        user_data = None
        
        with self.users_lock:
            if user in self.users and self.users[user]["password"] == hash_password(password):
                user_data = self.users[user]

        if user_data:
            with self.active_peers_lock:
                self.active_peers[user] = {
                    "peer-ip": peer_ip,
                    "peer-port": peer_port,
                }

            print(f"Peer {user} logado. Active_peers: {self.active_peers}")
            return {"status": "ok", "message": "Login bem sucedido", "usr": user}

        return {"status": "error", "message": "Usuario ou senha incorretos"}

    def process_peer_register(self, peer_req):
        user = peer_req.get("usr")
        password = peer_req.get("password")

        with self.users_lock:
            if user in self.users:
                return {"status": "error", "message": "Usuario ja existente"}
            else:
                new_user = {
                    user: {
                        "password": hash_password(password),
                    }
                }
                self.users.update(new_user)
                print(self.users)
                return {"status": "ok", "message": "Usuario registrado!"}

    def list_peers(self):
        with self.active_peers_lock:
            return {"status": "ok", "peer-list": self.active_peers}
    
    def list_rooms(self):
        with self.chat_rooms_lock:
            return {"status": "ok", "rooms-list": self.chat_rooms}

if __name__ == "__main__":
    tracker = Tracker()
    tracker.listen()