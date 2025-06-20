import socket, json, time, threading, os, sys
from utils.encrypt_utils import generate_rsa_keys, serialize_public_key, deserialize_public_key, encrypt_with_public_key, decrypt_with_private_key, hash_password

class Peer:
    def __init__(self, tracker_host="localhost", tracker_port=6000, peer_host= "0.0.0.0", peer_listen_port=5565, max_conec=5):
        # Configura conexao com tracker
        self.tracker_host = tracker_host
        self.tracker_port = tracker_port
        self.tracker_info = (tracker_host, tracker_port)
        self.peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.peer_socket_lock = threading.Lock()
        self.private_key, self.public_key = generate_rsa_keys()
        self.public_key_str = serialize_public_key(self.public_key)
  
        try:
            self.peer_socket.connect(self.tracker_info)
        except socket.error as e:
            print(f"Erro ao conectar ao tracker: {e}")

        # Troca chaves com tracker
        self.tracker_public_key = deserialize_public_key(
            json.loads(self.peer_socket.recv(4096).decode())["public_key"])
        self.peer_socket.send(json.dumps({"public_key": self.public_key_str}).encode())

        # Configura conexao com peers
        self.peer_host = peer_host
        self.peer_listen_port = peer_listen_port
        self.peer_info = (peer_host, peer_listen_port)
        self.peer_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.peer_server_socket.bind(self.peer_info)
        self.peer_server_socket.listen(max_conec)
        self.peer_listen_port = self.peer_server_socket.getsockname()[1]
        self.peer_server_socket_lock = threading.Lock()
        self.peer_connection_lock = threading.Lock()
        self.username = None
        self.chatting = False
        self.pending_requests_lock = threading.Lock()
        self.pending_chat_requests = []
    
    
    def peer_listen(self):
        while True:
            user_connec, addr = self.peer_server_socket.accept()
            print(f"Nova conexao de: {str(addr)}")
            threading.Thread(target=self.process_new_chat_connec, args=(user_connec, addr)).start()
        
    def start(self):
        threading.Thread(target=peer.peer_listen, daemon=True).start()
        while True:
            self.clear_terminal()
            print("========== Tela inicial Chatp2p ==========")
            print("Escolha uma opção: ")
            print("[1] Login")
            print("[2] Registrar")
            print("[3] Sair")

            while True:
                try:
                    option = int(input("->"))
                    break
                except:
                    print("Opção inválida")
                    continue
            
            match option:
                case 1: self.process_login()
                case 2: self.process_register()
                case 3:
                    self.peer_socket.close()
                    self.clean_pending_requests()
                    break
    
    def process_login(self):
        while True:
            self.clear_terminal()
            print("========== Login ==========")
            user = input("Digite seu usuario: ").strip()
            input_password = input("Digite sua senha: ").strip()
            requisition = {
                "cmd": "login", 
                "usr": user, 
                "password": input_password,
                "peer-listen-port": self.peer_listen_port,
            }

            response = self.send_and_recv_encrypted_request(requisition)

            if response.get("status") == "ok":
                print(response.get("message"))
                self.username = user
                threading.Thread(target=self.send_heartbeat, daemon=True).start()
                self.process_chat_functions()
                break
            else:
                print(response.get("message"))
                option = input("Deseja tentar novamente? [s/n]: ").strip()

                if option == "n":
                    break

    def process_register(self):
        while True:
            self.clear_terminal()
            print("========== Registro de usuario ==========")
            user = input("Digite um nome de usuario: ").strip()
            input_password = input("Digite uma senha: ").strip()

            if user and input_password:
                requisition = {
                    "cmd": "register", 
                    "usr": user, 
                    "password": input_password,
                }

                response = self.send_and_recv_encrypted_request(requisition)
                if response.get("status") == "ok":
                    break
                else:
                    input("O nome de usuário em uso, tente novamente com outro nome.\nPressione qualquer tecla para continuar...")

            else:
                print("Usuario ou senha invalidos, tente novamente")

    def process_chat_functions(self):
        while True:
            if self.chatting:
                time.sleep(1)
                continue

            self.clear_terminal()
            print("========== Chatp2p ==========")
            with self.pending_requests_lock:
                if self.pending_chat_requests:
                    print("*******************************************************")
                    print(f"Você possui {len(self.pending_chat_requests)} pedido(s) de chat pendente(s)!")
                    print("*******************************************************")
            print("Escolha uma opção: ")
            print("[1] Listar usuarios ativos")
            print("[2] Iniciar chat privado")
            print("[3] Listar salas disponiveis")
            print("[4] Criar sala")
            print("[5] Entrar em uma sala")
            print("[6] Gerenciar sala (se moderador)")
            print("[7] Ver pedidos de chat")
            
            try:
                option = int(input("->"))
            except:
                print("Opção inválida")
                continue
            
            match option:
                case 1: self.process_list_peers()
                case 2: self.process_peer_chat_client()
                case 3: self.process_list_rooms()
                case 4: self.process_create_room()
                case 5:
                    ...
                case 6: self.process_manage_room()
                case 7: self.process_pending_chats()
    
    def process_list_peers(self):
        requisition = {
            "cmd": "list-peers"
        }

        response = self.send_and_recv_encrypted_request(requisition)
        users_list = response.get("peer-list")
        
        self.clear_terminal()
        print("========== Lista de usuários ativos ==========")
        for user in users_list:
            print(f"Usuario: {user}")

        input("pressione qualquer tecla para retornar: ")
    
    def process_peer_chat_client(self):
        requisition = {"cmd": "list-peers"}
        response = self.send_and_recv_encrypted_request(requisition)

        self.clear_terminal()
        print("========== Iniciar chat privado ==========")    
        if response.get("status") != "ok" or not response.get("peer-list"):
            print("Não há outros usuários ativos no momento.")
            input("Pressione qualquer tecla para retornar")
            return
        
        users_list = response.get("peer-list")
        print("Selecione um usuário para conversar: ")
        for i, user in enumerate(users_list, 1):
            print(f"[{i}] {user}")
        print("[0] voltar")
        
        while True:
            try:
                option = int(input("->"))
                if option == 0:
                    return
                if not 1 <= option <= len(users_list):
                    raise ValueError
                
                user_to_connect = users_list[option - 1]
                break
            except:
                print("Opção inválida, tente novamente")
        
        requisition = {"cmd": "get-peer-addr", "user-to-connect": user_to_connect}
        response = self.send_and_recv_encrypted_request(requisition)
        
        if response.get("status") == "ok":
            user_to_connect_ip = response.get("user-ip")
            user_to_connect_port = response.get("user-port")
        else:
            print(response.get("message"))
            input("Pressione qualquer tecla para retonar...")
            return
        
        # Peer public key requisition
        requisition = {"cmd": "get-peer-key", "peer-public-key": user_to_connect}
        encrypted = encrypt_with_public_key(
            self.tracker_public_key, json.dumps(requisition))
        try:
            with self.peer_socket_lock:
                self.peer_socket.send(encrypted.encode())    
                data = self.peer_socket.recv(4096).decode()
                if not data:
                    raise ConnectionResetError("Erro de conexão!")
                response_key = json.loads(data)
        except Exception as e:
            print("A conexão com o servidor foi perdida!")
            print(f"Erro: {e}")
            print("Encerrando cliente...")
            sys.exit()

        if response_key.get("status") == "ok":
            user_to_connect_public_key_str = response_key.get("peer-public-key")
            user_to_connect_public_key = deserialize_public_key(user_to_connect_public_key_str)
        
            chat_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                chat_socket.connect((user_to_connect_ip, user_to_connect_port))
            except socket.error as e:
                print(f"Erro ao conectar com {user_to_connect}")
            
            request_msg = {"type": "chat_request", "from_user": self.username}
            encrypted = encrypt_with_public_key(user_to_connect_public_key, json.dumps(request_msg))
            
            request_with_public_key = {
                "public_key": self.public_key_str,
                "encrypted": encrypted
            }

            try:
                with self.peer_connection_lock:
                    chat_socket.send(json.dumps(request_with_public_key).encode())
                    print("Pedido de chat enviado, aguardando resposta...")
                    chat_socket.settimeout(60.0)
                    encrypted = chat_socket.recv(4096).decode()
                    chat_socket.settimeout(None)
                    if not encrypted:
                        raise ConnectionResetError("Erro de conexão!")
            
                data = decrypt_with_private_key(self.private_key, encrypted)
                response = json.loads(data)
                response_type = response.get("type")
                
                match response_type:
                    case "busy":
                        print(f"{user_to_connect} já está em outro chat")
                        chat_socket.close()
                    case "accept":
                        print(f"{user_to_connect} aceitou o seu pedido, iniciando chat...")
                        time.sleep(1)
                        self.handle_peer_chat(chat_socket, user_to_connect_public_key, user_to_connect)
                    case _:
                        print(f"{user_to_connect} recusou o pedido")
            
            except socket.timeout:
                print(f"{user_to_connect} não respondeu ao pedido.")               
            except Exception as e:
                print(f"A conexão com {user_to_connect} foi perdida!")
            finally:
                input("Pressione qualquer tecla para retornar...")
                return
        else:
            print("Erro ao obter informações do usuário")
            input("Pressione qualquer tecla para retornar...")
    
    def process_new_chat_connec(self, user_connec, addr):
        try:
            with self.peer_server_socket_lock:
                data = user_connec.recv(4096).decode()

                if not data:
                    raise ConnectionResetError("Erro de conexão!")

                request_with_pub = json.loads(data)
                user_chat_pub_key_str = request_with_pub["public_key"]
                user_chat_pub_key = deserialize_public_key(user_chat_pub_key_str)
                encrypted_data = request_with_pub["encrypted"]

                decrypted_request_data = decrypt_with_private_key(self.private_key, encrypted_data)
                request = json.loads(decrypted_request_data)
                request_type = request.get("type")

                match request_type:
                    case "chat_request": 
                        if self.chatting:
                            response = {"type": "busy"}
                            encrypted = encrypt_with_public_key(
                                        user_chat_pub_key, json.dumps(response))
                            user_connec.send(encrypted.encode())
                            user_connec.close()
                            return

                        requester_user = request.get("from_user")

                        print(f"[NOTIFICAÇÃO] Você recebeu um pedido de chat de {requester_user}. Verifique o menu.")

                        with self.pending_requests_lock:
                            self.pending_chat_requests.append({
                                "user": requester_user,
                                "conn": user_connec,
                                "public_key": user_chat_pub_key
                                }
                            )
                    case _:
                        user_connec.close()

        except (ConnectionResetError, json.JSONDecodeError, ValueError) as e:
            print(f"Erro de conexão com peer {str(addr)}: {str(e)}")
            user_connec.close()

    def handle_peer_chat(self, conn, peer_public_key, peer_username):
        self.chatting = True
        self.clear_terminal()
        print(f"Chat com {peer_username} iniciado. Digite '/sair' para sair.")
    
        def receive_messages():
            while self.chatting:
                try:
                    encrypted_message = conn.recv(4096).decode()
                    
                    if not encrypted_message:
                        print(f"\n[AVISO] Conexão perdida com {peer_username}.")
                        self.chatting = False
                        break
                    
                    decrypted_message = decrypt_with_private_key(self.private_key, encrypted_message)
                    data = json.loads(decrypted_message)

                    if data.get("type") == "exit":
                        print(f"\n[AVISO] {peer_username} encerrou o chat.")
                        self.chatting = False
                        break
                    
                    elif data.get("type") == "message":
                        print(f"\r{peer_username}: {data['content']}\nEu: ", end="")

                except (json.JSONDecodeError, ConnectionResetError, ValueError):
                    print(f"\n[AVISO] Conexão com {peer_username} perdida ou dados corrompidos.")
                    self.chatting = False
                    break
                except Exception:
                    self.chatting = False
                    break

        threading.Thread(target=receive_messages, daemon=True).start()

        while self.chatting:
            try:
                message_text = input("Eu: ")

                if not self.chatting:
                    break

                if message_text.lower() == 'exit':
                    notification = {"type": "exit"}
                    encrypted_notification = encrypt_with_public_key(peer_public_key, json.dumps(notification))
                    conn.send(encrypted_notification.encode())
                    self.chatting = False
                    break
                
                message_to_send = {"type": "message", "content": message_text}
                json_message = json.dumps(message_to_send)
                encrypted_message = encrypt_with_public_key(peer_public_key, json_message)
                
                conn.send(encrypted_message.encode())

            except (BrokenPipeError, ConnectionResetError):
                print(f"\n[AVISO] Não foi possível enviar a mensagem. O usuário {peer_username} desconectou.")
                self.chatting = False
                break
            except Exception as e:
                print(f"\nOcorreu um erro inesperado no chat: {e}")
                self.chatting = False
                break
        
        print("\nChat encerrado.")
        conn.close()
        self.chatting = False
        self.clean_pending_requests()

    def process_pending_chats(self):
        self.clear_terminal()
        print("========== Pedidos de Chat Pendentes ==========")      
        with self.pending_requests_lock:
            if not self.pending_chat_requests:
                print("Nenhum pedido de chat no momento.")
                input("Pressione qualquer tecla para retornar...")
                return

            for i, request in enumerate(self.pending_chat_requests, 1):
                print(f"[{i}] Pedido de: {request['user']}")
            
            try:
                choice = int(input("Escolha um pedido para responder (ou 0 para cancelar): "))
                if choice == 0:
                    return
                if not 1 <= choice <= len(self.pending_chat_requests):
                    raise ValueError
                
                chosen_request = self.pending_chat_requests.pop(choice - 1)
                
            except (ValueError, IndexError):
                print("Seleção inválida.")
                input("Pressione qualquer tecla para retornar...")
                return

        user = chosen_request['user']
        conn = chosen_request['conn']
        requester_public_key = chosen_request['public_key']
        
        action = input(f"Deseja iniciar chat privado com {user}?[s/n]: ").strip().lower()

        try:
            match action:
                case "s":
                    response_msg = {"type": "accept"}
                    encrypted_response = encrypt_with_public_key(
                        requester_public_key, json.dumps(response_msg)
                    )
                    conn.send(encrypted_response.encode())
                    print(f"Pedido de {user} aceito. Iniciando chat...")
                    time.sleep(1)
                    self.handle_peer_chat(conn, requester_public_key, user)
                case "n":
                    response_msg = {"type": "refuse"} 
                    encrypted_response = encrypt_with_public_key(
                        requester_public_key, json.dumps(response_msg)
                    )
                    conn.send(encrypted_response.encode())
                    conn.close()
                    print(f"Pedido de {user} recusado.")
                case _:
                    print("Ação inválida. O pedido será mantido como pendente.")
                    with self.pending_requests_lock:
                        self.pending_chat_requests.insert(choice - 1, chosen_request)
        
        except (socket.error, BrokenPipeError):
            print(f"O usuário {user} cancelou o pedido ou desconectou.")
            conn.close()

    def clean_pending_requests(self, reject=False):
        with self.pending_requests_lock:
            for request in self.pending_chat_requests:
                if reject:
                    try:
                        response = {"type": "refuse"}
                        requester_public_key = request['public_key']
                        encrypted_response = encrypt_with_public_key(
                            requester_public_key, json.dumps(response)
                        )
                        request['conn'].send(encrypted_response.encode())
                    except socket.error:
                        pass
                request['conn'].close()
            self.pending_chat_requests.clear()

    def process_list_rooms(self):
        requisition = {
            "cmd": "list-rooms"
        }

        response = self.send_and_recv_encrypted_request(requisition)
        rooms_list = response.get("room-list")
        
        self.clear_terminal()
        print("========== Lista de salas ==========")
        if rooms_list:
            for room in rooms_list:
                print(f"Sala: {room}")
        else:
            print("Não há nenhuma sala disponível no momento")

        input("pressione qualquer tecla para retornar: ")
    
    def process_create_room(self): 
        self.clear_terminal()       
        print("========== Criar Sala ==========")
        room_name = input("Digite o nome da sala: ").strip()
        
        if not room_name:
            print("Nome da sala não pode ser vazio!")
            return
        
        requisition = {
            "cmd": "create-room",
            "room-name": room_name,
            "creator": None  # Será preenchido pelo tracker com o usuário logado
        }
        
        try:
            response = self.send_and_recv_encrypted_request(requisition)           
            if response.get("status") == "ok":
                print(f"Sala '{room_name}' criada com sucesso!")
            else:
                print(f"Erro ao criar sala: {response.get('message')}")
        
        except Exception as e:
            print(f"Erro durante a criação da sala: {str(e)}")
        
        input("Pressione qualquer tecla para retornar: ")

    def process_manage_room(self):
        """
        Menu de moderação para criadores de sala
        """
        self.clear_terminal()
        print("========== Gerenciar Sala ==========")
        requisition = {
            "cmd": "list-my-rooms"
        }
        
        response = self.send_and_recv_encrypted_request(requisition)

        if response.get("status") != "ok" or not response.get("rooms"):
            print("Você não é moderador de nenhuma sala")
            input("Pressione qualquer tecla para voltar...")
            return
        
        # Mostra salas que pode moderar
        print("Suas salas (como moderador):")
        for i, room in enumerate(response["rooms"], 1):
            print(f"[{i}] {room}")
        
        try:
            choice = int(input("Selecione a sala para gerenciar (0 para cancelar): "))
            if choice == 0:
                return
            room_name = response["rooms"][choice-1]
        except:
            print("Seleção inválida")
            return
        
        # Menu de moderação
        while True:
            self.clear_terminal()
            print(f"\n========== Gerenciando Sala: {room_name} ==========")
            print("[1] Listar membros")
            print("[2] Adicionar membro")
            print("[3] Remover membro")
            print("[4] Fechar sala")
            print("[0] Voltar")
            
            try:
                option = int(input("-> "))
            except:
                print("Opção inválida")
                continue
            
            match option:
                case 1: self.process_list_room_members(room_name)
                case 2: self.process_add_member(room_name)
                case 3: self.process_remove_member(room_name)
                case 4:
                    self.process_close_room(room_name)
                    return  # Sai do menu após fechar a sala
                case 0: return
                case _: print("Opção inválida")
        
    def process_list_room_members(self, room_name):
        """Lista todos os membros de uma sala"""
        requisition = {
            "cmd": "list-members",
            "room-name": room_name
        }
        
        response = self.send_and_recv_encrypted_request(requisition)
        members = response.get("members")

        self.clear_terminal()
        print(f"========== Usuários com acesso a sala <{room_name}> ==========")
        for member in members:
            print(member)

        input("Pressione qualquer tecla para retornar...")
    
    def process_add_member(self, room_name):
        """Adiciona um usuário à sala"""
        self.clear_terminal()
        user = input("Digite o nome do usuário para adicionar: ").strip()
        if not user:
            print("Nome inválido")
            return
        
        requisition = {
            "cmd": "add-member",
            "room-name": room_name,
            "user": user
        }
        
        response = self.send_and_recv_encrypted_request(requisition)
        print(response.get("message"))
        input("Pressione qualquer tecla para retornar...")
    
    def process_remove_member(self, room_name):
        """Remove um usuário da sala"""
        self.clear_terminal()
        user = input("Digite o nome do usuário para remover: ").strip()
        if not user:
            print("Nome inválido")
            return
        
        requisition = {
            "cmd": "remove-member",
            "room-name": room_name,
            "user": user
        }
        
        response = self.send_and_recv_encrypted_request(requisition)
        print(response.get("message"))
        input("Pressione qualquer tecla para retornar...")
    
    def process_close_room(self, room_name):
        """Fecha permanentemente a sala"""
        confirm = input(f"Tem certeza que deseja fechar a sala '{room_name}'? (s/n): ").strip().lower()
        if confirm != 's':
            print("Operação cancelada")
            return
        
        requisition = {
            "cmd": "close-room",
            "room-name": room_name
        }
        
        response = self.send_and_recv_encrypted_request(requisition)
        print(response.get("message"))

    def send_and_recv_encrypted_request(self, requisition):
        """Helper para enviar requisições criptografadas"""
        encrypted = encrypt_with_public_key(
            self.tracker_public_key, json.dumps(requisition))
        try:
            with self.peer_socket_lock:
                self.peer_socket.send(encrypted.encode())    
                encrypted_data = self.peer_socket.recv(4096).decode()

                if not encrypted_data:
                    raise ConnectionResetError("Erro de conexão!")
            
            data = decrypt_with_private_key(self.private_key, encrypted_data)
                
            return json.loads(data)
        except Exception as e:
            print("A conexão com o servidor foi perdida!")
            print(f"Erro: {e}")
            print("Encerrando cliente...")
            sys.exit()
    
    def send_heartbeat(self, interval=30):
        while True:
            try:
                requisition = {"cmd": "heartbeat"}
                self.send_and_recv_encrypted_request(requisition)
            except Exception as e:
                pass
            
            time.sleep(interval)

    def clear_terminal(self):
        if os.name == 'nt':
            os.system('cls')
        else:
            os.system("clear")

if __name__ == "__main__":
    peer = Peer(peer_listen_port=0)
    peer.start()