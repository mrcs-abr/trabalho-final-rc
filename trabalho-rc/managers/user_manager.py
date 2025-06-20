import threading, json, os, time
from utils.encrypt_utils import hash_password

USER_DATA_FILE = "data_storage/users.json"

class User_manager:
    def __init__(self):
        self.users = self.load_users()
        self.active_peers = {}
        self.users_lock = threading.Lock()
        self.active_peers_lock = threading.Lock()
        threading.Thread(target=self.monitor_users,daemon=True).start()
    
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
    
    def login(self, user, password, address, peer_server_port, peer_public_key, peer_conec):
        peer_ip, _ = address
        with self.users_lock:
            if user not in self.users or self.users[user]["password"] != hash_password(password):
                return {"status": "error", "message": "Usuário ou senha incorretos"}
        
        with self.active_peers_lock:
            self.active_peers[user] = {
                "peer-ip": peer_ip,
                "peer-port": peer_server_port,
                "last-seen": time.time(),
                "peer-public-key": peer_public_key,
                "peer-conec": peer_conec
            }
        
        return {"status": "ok", "message": "Login bem-sucedido", "usr": user}
    
    def logout(self, user):
        with self.active_peers_lock:
            if user in self.active_peers:
                try:
                    self.active_peers[user]["peer-conec"].close()
                except Exception as e:
                    print(f"Erro ao fechar conexao para {user}")
                finally:
                    del self.active_peers[user]
                    print(f"Usuário {user} desconectado")
    
    def list_active_peers(self, requesting_user):
        with self.active_peers_lock:
            peer_list = [peer for peer in self.active_peers.keys() if peer != requesting_user]
            return {"status": "ok", "peer-list": peer_list}
    
    def get_peer_addr(self, user_to_connect):
        with self.active_peers_lock:
            if user_to_connect in self.active_peers:
                user_info = self.active_peers[user_to_connect]
                return {"status": "ok", "user-ip": user_info["peer-ip"], "user-port": user_info["peer-port"]}
            else:
                return {"status": "error", "message": "Usuário não está ativo ou não existe"}
    
    def get_peer_public_key(self, user_to_connect):
        with self.active_peers_lock:
            if user_to_connect in self.active_peers:
                user_info = self.active_peers[user_to_connect]
                return {"status": "ok", "peer-public-key": user_info["peer-public-key"]}
            else:
                return {"status": "error", "message": "Usuário não está ativo ou não existe"}
    
    
    def list_peers_to_connect(self, user):
        with self.active_peers_lock:
            peers_to_connect = self.active_peers.copy()
            
            if user in peers_to_connect:
                del peers_to_connect[user]
                return {"status": "ok", "peer-list": peers_to_connect}
    
    def update_heartbeat(self, user):
        with self.active_peers_lock:
            if user in self.active_peers:
                self.active_peers[user]["last-seen"] = time.time()
                return {"status": "ok", "message": f"heartbeat recebido de {user}"}
    
    def monitor_users(self):

        while True:
            time.sleep(10)
            now = time.time()

            inactive_users = []

            with self.active_peers_lock:
                for username, user in self.active_peers.items():
                    if now - user["last-seen"] > 90:
                        inactive_users.append(username)
            
            if inactive_users:
                for user in inactive_users:
                    self.logout(user)
    
    def user_exists(self, user):
        with self.users_lock:
            return user in self.users