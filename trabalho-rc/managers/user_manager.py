import threading, json, os
from utils.encrypt_utils import hash_password

USER_DATA_FILE = "data_storage/users.json"

class User_manager:
    def __init__(self):
        self.users = self.load_users()
        self.active_peers = {}
        self.users_lock = threading.Lock()
        self.active_peers_lock = threading.Lock()
    
    def load_users(self):
        if os.path.exists(USER_DATA_FILE):
            try:
                with open(USER_DATA_FILE, "r") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                print("Erro ao carregar usuários")
                return {}
        return {}

    def save_users(self):
        with open(USER_DATA_FILE, "w") as f:
            json.dump(self.users, f, indent=4)
 
    def register(self, user, password):
        with self.users_lock:
            if user in self.users:
                return {"status": "error", "message": "Nome de usuário já existente"}

            self.users[user] = {
                "password": hash_password(password)
            }
            self.save_users()
            return {"status": "ok", "message": "Usuário registrado com sucesso!"}
    
    def login(self, user, password, address):
        peer_ip, peer_port = address
        with self.users_lock:
            if user not in self.users or self.users[user]["password"] != hash_password(password):
                return {"status": "error", "message": "Usuário ou senha incorretos"}
        
        with self.active_peers_lock:
            self.active_peers[user] = {
                "peer-ip": peer_ip,
                "peer-port": peer_port,
            }
        
        return {"status": "ok", "message": "Login bem-sucedido", "usr": user}
    
    def logout(self, user):
        with self.active_peers_lock:
            if user in self.active_peers:
                del self.active_peers[user]
    
    def list_active_peers(self):
        with self.active_peers_lock:
            peer_list = list(self.active_peers.keys())
            return {"status": "ok", "peer-list": peer_list}
    
    def user_exists(self, user):
        with self.users_lock:
            return user in self.users