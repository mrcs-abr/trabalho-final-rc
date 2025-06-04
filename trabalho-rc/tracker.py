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
                        
                        case "create-room":
                            response = self.process_create_room(peer_requisition, user)
                        
                        case "list-my-rooms":
                            response = self.process_list_my_rooms(user)

                        case "list-members":
                            response = self.process_list_members(peer_requisition)

                        case "add-member":
                            response = self.process_add_member(peer_requisition, user)

                        case "remove-member":
                            response = self.process_remove_member(peer_requisition, user)

                        case "ban-user":
                            response = self.process_ban_user(peer_requisition, user)

                        case "close-room":
                            response = self.process_close_room(peer_requisition, user)

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
    
    def process_create_room(self, peer_req, creator):
        """
        Processa a criação de uma nova sala no tracker.
        Verifica se a sala já existe e, se não, cria uma nova entrada no dicionário de salas.
        """
        room_name = peer_req.get("room-name")
        
        if not room_name:
            return {"status": "error", "message": "Nome da sala não pode ser vazio"}
        
        with self.chat_rooms_lock:
            if room_name in self.chat_rooms:
                return {"status": "error", "message": "Sala já existe"}
            
            # Cria a nova sala com o criador como primeiro membro
            self.chat_rooms[room_name] = {
                "creator": creator,
                "members": [creator],
                "messages": []
            }
            print(f"Sala '{room_name}' criada por {creator}. Salas disponíveis: {self.chat_rooms}")
            return {"status": "ok", "message": f"Sala '{room_name}' criada com sucesso"}

    def process_create_room(self, peer_req, creator):
        room_name = peer_req.get("room-name")
        
        if not room_name:
            return {"status": "error", "message": "Nome da sala não pode ser vazio"}
        
        with self.chat_rooms_lock:
            if room_name in self.chat_rooms:
                return {"status": "error", "message": "Sala já existe"}
            
            self.chat_rooms[room_name] = {
                "creator": creator,
                "moderators": [creator],  # Lista de moderadores
                "members": [creator],     # Membros atuais
                "banned": [],            # Usuários banidos
                "is_active": True        # Status da sala
            }
            
            print(f"Sala '{room_name}' criada por {creator}")
            return {"status": "ok", "message": f"Sala '{room_name}' criada com sucesso"}

    def process_list_my_rooms(self, user):
        """Lista salas onde o usuário é moderador"""
        with self.chat_rooms_lock:
            my_rooms = [
                room_name for room_name, room_data in self.chat_rooms.items()
                if user in room_data["moderators"] and room_data["is_active"]
            ]
            return {"status": "ok", "rooms": my_rooms}
    
    def process_list_members(self, peer_req):
        """Lista membros de uma sala"""
        room_name = peer_req.get("room-name")
        with self.chat_rooms_lock:
            if room_name not in self.chat_rooms:
                return {"status": "error", "message": "Sala não encontrada"}
            
            return {
                "status": "ok",
                "members": self.chat_rooms[room_name]["members"],
                "moderators": self.chat_rooms[room_name]["moderators"]
            }
    
    def process_add_member(self, peer_req, moderator):
        """Adiciona um membro à sala"""
        room_name = peer_req.get("room-name")
        user_to_add = peer_req.get("user")
        
        with self.chat_rooms_lock:
            if room_name not in self.chat_rooms:
                return {"status": "error", "message": "Sala não encontrada"}
            
            room = self.chat_rooms[room_name]
            
            # Verifica se é moderador
            if moderator not in room["moderators"]:
                return {"status": "error", "message": "Apenas moderadores podem adicionar membros"}
            
            # Verifica se usuário está banido
            if user_to_add in room["banned"]:
                return {"status": "error", "message": "Este usuário está banido desta sala"}
            
            # Verifica se já é membro
            if user_to_add in room["members"]:
                return {"status": "error", "message": "Usuário já é membro desta sala"}
            
            # Adiciona membro
            room["members"].append(user_to_add)
            return {"status": "ok", "message": f"Usuário {user_to_add} adicionado à sala"}
    
    def process_remove_member(self, peer_req, moderator):
        """Remove um membro da sala"""
        room_name = peer_req.get("room-name")
        user_to_remove = peer_req.get("user")
        
        with self.chat_rooms_lock:
            if room_name not in self.chat_rooms:
                return {"status": "error", "message": "Sala não encontrada"}
            
            room = self.chat_rooms[room_name]
            
            # Verifica se é moderador
            if moderator not in room["moderators"]:
                return {"status": "error", "message": "Apenas moderadores podem remover membros"}
            
            # Não permite remover moderadores
            if user_to_remove in room["moderators"]:
                return {"status": "error", "message": "Não pode remover outros moderadores"}
            
            # Remove membro
            if user_to_remove in room["members"]:
                room["members"].remove(user_to_remove)
                return {"status": "ok", "message": f"Usuário {user_to_remove} removido da sala"}
            
            return {"status": "error", "message": "Usuário não encontrado na sala"}
    
    def process_ban_user(self, peer_req, moderator):
        """Bane um usuário da sala"""
        room_name = peer_req.get("room-name")
        user_to_ban = peer_req.get("user")
        
        with self.chat_rooms_lock:
            if room_name not in self.chat_rooms:
                return {"status": "error", "message": "Sala não encontrada"}
            
            room = self.chat_rooms[room_name]
            
            # Verifica se é moderador
            if moderator not in room["moderators"]:
                return {"status": "error", "message": "Apenas moderadores podem banir usuários"}
            
            # Não permite banir moderadores
            if user_to_ban in room["moderators"]:
                return {"status": "error", "message": "Não pode banir outros moderadores"}
            
            # Adiciona à lista de banidos e remove dos membros
            if user_to_ban not in room["banned"]:
                room["banned"].append(user_to_ban)
            
            if user_to_ban in room["members"]:
                room["members"].remove(user_to_ban)
            
            return {"status": "ok", "message": f"Usuário {user_to_ban} banido da sala"}
    
    def process_close_room(self, peer_req, moderator):
        """Fecha permanentemente uma sala"""
        room_name = peer_req.get("room-name")
        
        with self.chat_rooms_lock:
            if room_name not in self.chat_rooms:
                return {"status": "error", "message": "Sala não encontrada"}
            
            room = self.chat_rooms[room_name]
            
            # Verifica se é o criador
            if moderator != room["creator"]:
                return {"status": "error", "message": "Apenas o criador pode fechar a sala"}
            
            # Marca sala como inativa
            room["is_active"] = False
            del self.chat_rooms[room_name]
            return {"status": "ok", "message": f"Sala {room_name} fechada permanentemente"}

if __name__ == "__main__":
    tracker = Tracker()
    tracker.listen()