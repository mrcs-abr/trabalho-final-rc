import socket, json, threading, time
from datetime import datetime
from tracker_managers.user_manager import User_manager
from tracker_managers.room_manager import Room_manager
from utils.encrypt_utils import generate_ecc_keys, serialize_public_key, deserialize_public_key, encrypt_with_public_key, decrypt_with_private_key

class Tracker:
    def __init__(self, host='0.0.0.0', port=6000, max_connec=5):
        self.host = host
        self.port = port
        self.server_info = (host, port)
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind(self.server_info)
        self.server.listen(max_connec)

        self.private_key, self.public_key = generate_ecc_keys()
        self.public_key_str = serialize_public_key(self.public_key)

        self.user_manager = User_manager()
        self.room_manager = Room_manager()

        threading.Thread(target=self.monitor_inactive_users, daemon=True).start()
        threading.Thread(target=self.room_manager.monitor_rooms, daemon=True).start()

        print(f"Tracker iniciado em {self.host}:{self.port}")
        print("Aguardando conexões...")


    def monitor_inactive_users(self):
        while True:
            time.sleep(30)
            now = time.time()
            inactive_users = []

            with self.user_manager.active_peers_lock:
                for username, user_data in list(self.user_manager.active_peers.items()):
                    if now - user_data.get("last-seen", now) > 60:
                        inactive_users.append(username)
            
            if inactive_users:
                print(f"Detectados usuários inativos: {inactive_users}")
                for user in inactive_users:
                    self.user_manager.logout(user)
                    self.room_manager.remove_user_from_all_rooms(user)


    def listen(self):
        while True:
            peer_conec, address = self.server.accept()
            print("Conexao de: " + str(address))
            threading.Thread(target=self.process_new_peer, args=(peer_conec, address)).start()


    def process_new_peer(self, peer_conec, address):
            user = None
            try:
                peer_conec.send(json.dumps({"public_key": self.public_key_str}).encode())
                
                peer_public_key_str = json.loads(peer_conec.recv(4096).decode())["public_key"]
                peer_public_key = deserialize_public_key(peer_public_key_str)
                
                while True:
                    encrypted_data = peer_conec.recv(4096)
                    if not encrypted_data:
                        break

                    data = decrypt_with_private_key(self.private_key, encrypted_data.decode())
                    peer_requisition = json.loads(data)
                    
                    cmd = peer_requisition.get("cmd")
                    
                    response = {"status": "error", "message": "Comando inválido ou usuário não logado"}

                    match cmd:
                        case "login":
                            response = self.user_manager.login(peer_requisition["usr"], 
                                                               peer_requisition["password"], 
                                                               address,
                                                               peer_requisition["peer-listen-port"],
                                                               peer_public_key_str,
                                                               peer_conec)
                                                               
                            if response.get("status") == "ok":
                                user = response.get("usr")

                        case "logout":
                            if user:
                                response = self.user_manager.logout(user)
                                if response.get("status") == "ok":
                                    user = None
                        
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
                        
                        case "get-room-members":
                            if user:
                                room_name = peer_requisition.get("room-name")
                                online_users_response = self.room_manager.get_online_members_in_room(room_name, user)

                                if online_users_response["status"] == "ok":
                                    online_usernames = online_users_response["online-members"]
                                    members_info = {}
                                    for member_user in online_usernames:
                                        info_response = self.user_manager.get_peer_addr(member_user)
                                        if info_response["status"] == "ok":
                                            members_info[member_user] = {
                                                "user-ip": info_response["user-ip"],
                                                "user-port": info_response["user-port"],
                                                "peer-public-key": info_response["peer-public-key"]
                                            }
                                    response = {"status": "ok", "members": members_info}
                                else:
                                    response = online_users_response
                        
                        case "leave-room":
                            if user:
                                response = self.room_manager.leave_room(peer_requisition["room-name"], user)

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
                    
                    timestamp = datetime.now().strftime('%H:%M')  
                    print(f"[{timestamp}] Comando '{cmd}' de '{user if user else str(address)}'. Resposta: {response}")

                    encrypted_response = encrypt_with_public_key(peer_public_key, json.dumps(response))
                    peer_conec.send(encrypted_response.encode())
            
            except (ConnectionResetError, json.JSONDecodeError, ValueError, OSError):
                pass
            
            finally:
                if user:
                    self.user_manager.logout(user)
                    self.room_manager.remove_user_from_all_rooms(user)
                peer_conec.close()
    
if __name__ == "__main__":
    tracker = Tracker()
    try:
        tracker.listen()
    except KeyboardInterrupt:
        print("\n[INFO] Encerrando o tracker... Salvando dados.")
        tracker.user_manager.save_users()
        tracker.room_manager.save_rooms()
        print("[INFO] Dados salvos. tracker encerrado!!")