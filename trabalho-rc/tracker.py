import socket, json, threading
from threading import Thread
from managers.user_manager import User_manager
from managers.room_manager import Room_manager
from utils.encrypt_utils import generate_rsa_keys, serialize_public_key, deserialize_public_key, encrypt_with_public_key, decrypt_with_private_key, hash_password

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

        self.user_manager = User_manager()
        self.room_manager = Room_manager()

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
                            response = self.user_manager.login(peer_requisition["usr"], peer_requisition["password"], address)
                            if response.get("status") == "ok":
                                user = response.get("usr")

                        case "register":
                            response = self.user_manager.register(peer_requisition["usr"], peer_requisition["password"])
                        
                        case "list-peers":
                            if user:
                                response = self.user_manager.list_active_peers(user)
                        
                        case "get-peer-addr":
                            if user:
                                response = self.user_manager.get_peer_addr(peer_requisition["user-to-connect"])

                        case "list-rooms":
                            if user:
                                response = self.room_manager.list_rooms()
                        
                        case "create-room":
                            if user:
                                response = self.room_manager.create_room(peer_requisition["room-name"], user)
                        
                        case "join-room":
                            if user:
                                response = self.room_manager.join_room(peer_requisition["room-to-join"], user)
                        
                        case "list-my-rooms":
                            if user:
                                response = self.room_manager.list_my_rooms(user)

                        case "list-members":
                            if user:
                                response = self.room_manager.list_members(peer_requisition["room-name"])

                        case "add-member":
                            if user:
                                response = self.room_manager.add_member(peer_requisition["room-name"], peer_requisition["user"], user, self.user_manager.users)

                        case "remove-member":
                            if user:
                                response = self.room_manager.remove_member(peer_requisition["room-name"], peer_requisition["user"], user)

                        case "close-room":
                            if user:
                                response = self.room_manager.close_room(peer_requisition["room-name"], user)
                        
                        case "heartbeat":
                            if user:
                                response = self.user_manager.update_heartbeat(user)
                                self.room_manager.update_mod_heartbeat(user)

                        case _:
                            response = {"status": "error", "message": "Comando inválido"}

                    print(response)
                    encrypted_response = encrypt_with_public_key(peer_public_key, json.dumps(response))
                    peer_conec.send(encrypted_response.encode())
            
            except (ConnectionResetError, json.JSONDecodeError, ValueError) as e:
                print(f"Erro de conexão com peer {str(address)}: {str(e)}")
                self.user_manager.logout(user)
                print(f"Peer {user} desconectado.")
                peer_conec.close()
    
if __name__ == "__main__":
    tracker = Tracker()
    tracker.listen()