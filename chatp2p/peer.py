import socket, json, time, threading, os, sys
from utils.encrypt_utils import deserialize_public_key, encrypt_with_public_key, decrypt_with_private_key
from peer_managers.tracker_connection_manager import Tracker_connection_manager

class Peer:
    def __init__(self, peer_host= "0.0.0.0", peer_listen_port=5565, max_conec=5):
        # # Configura conexao com tracker 
        self.tracker_connection = Tracker_connection_manager()
        self.tracker_connection.connect_to_tracker()
        self.tracker_public_key = self.tracker_connection.tracker_public_key

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
        
        self.in_group_chat = False
        self.current_room = None
        self.room_peers_conn = {} # Dicionário para {username: {conn: socket, public_key: key}}
        self.room_peers_lock = threading.Lock()
        
        self.pending_requests_lock = threading.Lock()
        self.pending_chat_requests = []
    
    
    def peer_listen(self):
        while True:
            try:
                user_connec, addr = self.peer_server_socket.accept()
                threading.Thread(target=self.process_new_peer_connection, args=(user_connec, addr), daemon=True).start()
            except Exception:
                # Ocorre quando o socket é fechado, pode ser ignorado.
                break
        
    def start(self):
        threading.Thread(target=self.peer_listen, daemon=True).start()
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
                except ValueError:
                    print("Opção inválida")
                    continue
            
            match option:
                case 1: self.process_login()
                case 2: self.process_register()
                case 3:
                    if self.in_group_chat:
                        self.leave_group_chat()
                    self.peer_server_socket.close()
                    self.tracker_connection.peer_socket.close()
                    self.clean_pending_requests()
                    return # Sai do programa

    def process_new_peer_connection(self, user_connec, addr):
        try:
            data = user_connec.recv(4096).decode()
            if not data:
                raise ConnectionResetError("Erro de conexão!")

            request_with_pub = json.loads(data)
            user_chat_pub_key_str = request_with_pub["public_key"]
            user_chat_pub_key = deserialize_public_key(user_chat_pub_key_str)
            encrypted_data = request_with_pub["encrypted"]

            decrypted_request_data = decrypt_with_private_key(self.tracker_connection.private_key, encrypted_data)
            request = json.loads(decrypted_request_data)
            request_type = request.get("type")

            match request_type:
                case "chat_request": 
                    if self.chatting or self.in_group_chat:
                        response = {"type": "busy"}
                        encrypted = encrypt_with_public_key(
                                    user_chat_pub_key, json.dumps(response))
                        user_connec.send(encrypted.encode())
                        user_connec.close()
                        return

                    requester_user = request.get("from_user")
                    print(f"\n[NOTIFICAÇÃO] Você recebeu um pedido de chat de {requester_user}. Verifique o menu.")
                    with self.pending_requests_lock:
                        self.pending_chat_requests.append({
                            "user": requester_user,
                            "conn": user_connec,
                            "public_key": user_chat_pub_key
                            }
                        )
                
                case "group_chat_join":
                    room_name = request.get("room_name")
                    requester_user = request.get("from_user")
                    
                    if self.in_group_chat and room_name == self.current_room:
                        with self.room_peers_lock:
                            self.room_peers_conn[requester_user] = {
                                "conn": user_connec,
                                "public_key": user_chat_pub_key
                            }
                        threading.Thread(target=self.receive_group_messages, args=(user_connec, requester_user), daemon=True).start()
                        
                        response = {"type": "group_join_accept"}
                        encrypted = encrypt_with_public_key(user_chat_pub_key, json.dumps(response))
                        user_connec.send(encrypted.encode())
                        
                        # Limpa a linha de input atual, imprime a notificação e redesenha o prompt
                        sys.stdout.write('\r' + ' ' * 80 + '\r')
                        print(f"[SALA] {requester_user} entrou no chat.")
                        sys.stdout.write("Eu: ")
                        sys.stdout.flush()
                    else:
                        user_connec.close()
                case _:
                    user_connec.close()
        except (ConnectionResetError, json.JSONDecodeError, ValueError, OSError):
            user_connec.close()

    def receive_group_messages(self, conn, peer_username):
        """Escuta por mensagens de um peer específico no chat em grupo e as exibe na tela."""
        while self.in_group_chat:
            try:
                encrypted_message = conn.recv(4096).decode()
                if not encrypted_message:
                    break # Conexão fechada

                decrypted_message = decrypt_with_private_key(self.tracker_connection.private_key, encrypted_message)
                data = json.loads(decrypted_message)
                
                msg_type = data.get("type")
                if msg_type == "group_message":
                    # Melhoria na interface: Limpa a linha de input, imprime a mensagem e redesenha o prompt
                    sys.stdout.write('\r' + ' ' * 80 + '\r') # Limpa a linha atual
                    print(f"{peer_username}: {data['content']}")
                    sys.stdout.write("Eu: ")
                    sys.stdout.flush()

                elif msg_type == "group_leave":
                    sys.stdout.write('\r' + ' ' * 80 + '\r')
                    print(f"[SALA] {peer_username} saiu do chat.")
                    sys.stdout.write("Eu: ")
                    sys.stdout.flush()
                    break # Encerra a thread para este usuário

            except (json.JSONDecodeError, ValueError, ConnectionResetError, OSError):
                # Erros esperados quando a conexão é encerrada.
                break
            except Exception as e:
                # Captura qualquer outro erro inesperado para debug.
                print(f"[ERRO THREAD {peer_username}]: {e}")
                break
        
        # Rotina de limpeza da conexão
        with self.room_peers_lock:
            if peer_username in self.room_peers_conn:
                self.room_peers_conn[peer_username]["conn"].close()
                del self.room_peers_conn[peer_username]
        
        if self.in_group_chat: # Só imprime a notificação se ainda estivermos no chat
            sys.stdout.write('\r' + ' ' * 80 + '\r')
            print(f"[SALA] Conexão com {peer_username} encerrada.")
            sys.stdout.write("Eu: ")
            sys.stdout.flush()
    # FIM DA ALTERAÇÃO

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

            response = self.tracker_connection.send_and_recv_encrypted_request(requisition)

            if response.get("status") == "ok":
                print(response.get("message"))
                self.username = user
                threading.Thread(target=self.tracker_connection.send_heartbeat, daemon=True).start()
                self.process_chat_functions()
                return
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

                response = self.tracker_connection.send_and_recv_encrypted_request(requisition)
                if response.get("status") == "ok":
                    print(response.get("message"))
                    input("Pressione qualquer tecla para ir para a tela de login...")
                    break
                else:
                    input("O nome de usuário em uso, tente novamente com outro nome.\nPressione qualquer tecla para continuar...")

            else:
                print("Usuario ou senha invalidos, tente novamente")

    def process_chat_functions(self):
        while True:
            if self.chatting or self.in_group_chat:
                time.sleep(1)
                continue

            self.clear_terminal()
            print(f"========== Chatp2p - Logado como: {self.username} ==========")
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
            print("[8] Logout")
            
            try:
                option = int(input("->"))
            except ValueError:
                print("Opção inválida")
                continue
            
            match option:
                case 1: self.process_list_peers()
                case 2: self.process_peer_chat_client()
                case 3: self.process_list_rooms()
                case 4: self.process_create_room()
                case 5: self.process_join_room()
                case 6: self.process_manage_room()
                case 7: self.process_pending_chats()
                case 8:
                    print("Deslogando...")
                    return 
                case _:
                    print("Opção inválida")


    def process_list_peers(self):
        requisition = {
            "cmd": "list-peers"
        }

        response = self.tracker_connection.send_and_recv_encrypted_request(requisition)
        users_list = response.get("peer-list")
        
        self.clear_terminal()
        print("========== Lista de usuários ativos ==========")
        for user in users_list:
            print(f"Usuario: {user}")

        input("pressione qualquer tecla para retornar: ")
    
    def process_peer_chat_client(self):
        requisition = {"cmd": "list-peers"}
        response = self.tracker_connection.send_and_recv_encrypted_request(requisition)

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
        response = self.tracker_connection.send_and_recv_encrypted_request(requisition)
        
        if response.get("status") == "ok":
            user_to_connect_ip = response.get("user-ip")
            user_to_connect_port = response.get("user-port")
            user_to_connect_public_key_str = response.get("peer-public-key")
            user_to_connect_public_key = deserialize_public_key(user_to_connect_public_key_str)

            chat_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                chat_socket.connect((user_to_connect_ip, user_to_connect_port))
            except socket.error as e:
                print(f"[Erro] Falha ao conectar com {user_to_connect}")
            
            request_msg = {"type": "chat_request", "from_user": self.username}
            encrypted = encrypt_with_public_key(user_to_connect_public_key, json.dumps(request_msg))
            
            request_with_public_key = {
                "public_key": self.tracker_connection.public_key_str,
                "encrypted": encrypted
            }

            try:
                with self.peer_connection_lock:
                    chat_socket.send(json.dumps(request_with_public_key).encode())
                    print("Pedido de chat enviado, aguardando resposta...")
                    chat_socket.settimeout(60.0)
                    encrypted_res = chat_socket.recv(4096).decode()
                    chat_socket.settimeout(None)
                    if not encrypted_res:
                        raise ConnectionResetError("Erro de conexão!")
            
                data = decrypt_with_private_key(self.tracker_connection.private_key, encrypted_res)
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
                print(f"A conexão com {user_to_connect} foi perdida! {e}")
            finally:
                input("Pressione qualquer tecla para retornar...")
                return
        else:
            print("Erro ao obter informações do usuário")
            input("Pressione qualquer tecla para retornar...")
        

    def process_list_rooms(self):
        requisition = {
            "cmd": "list-rooms"
        }

        response = self.tracker_connection.send_and_recv_encrypted_request(requisition)
        rooms_list = response.get("room-list")
        
        self.clear_terminal()
        print("========== Lista de salas ==========")
        if rooms_list:
            for room in rooms_list:
                print(f"Sala: {room}")
        else:
            print("Não há nenhuma sala disponível no momento")

        input("pressione qualquer tecla para retornar: ")

    def handle_peer_chat(self, conn, peer_public_key, peer_username):
        self.chatting = True
        self.clear_terminal()
        print(f"Chat com {peer_username} iniciado. Digite '/sair' para sair.")

        threading.Thread(target=self.receive_messages,args=(conn, peer_username), daemon=True).start()

        while self.chatting:
            try:
                message_text = input("Eu: ")

                if not self.chatting:
                    break

                if message_text.lower() == '/sair':
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
    
    def receive_messages(self, conn, peer_username):
        while self.chatting:
            try:
                encrypted_message = conn.recv(4096).decode()
                
                if not encrypted_message:
                    print(f"\n[AVISO] Conexão perdida com {peer_username}.")
                    self.chatting = False
                    break
                
                decrypted_message = decrypt_with_private_key(self.tracker_connection.private_key, encrypted_message)
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

    def process_join_room(self):
        requisition = {"cmd": "list-rooms"}
        response = self.tracker_connection.send_and_recv_encrypted_request(requisition)
        
        if response.get("status") != "ok" or not response.get("room-list"):
            print("Não há salas disponíveis no momento.")
            input("Pressione qualquer tecla para retornar...")
            return
        
        rooms_list = response.get("room-list")
        
        self.clear_terminal()
        print("========== Entrar em Sala ==========")
        print("Salas disponíveis:")
        for i, room in enumerate(rooms_list, 1):
            print(f"[{i}] {room}")
        print("[0] Voltar")
        
        try:
            choice = int(input("Selecione a sala para entrar: "))
            if choice == 0:
                return
            if not 1 <= choice <= len(rooms_list):
                raise ValueError
                
            room_name = rooms_list[choice - 1]
            
            requisition = {"cmd": "join-room", "room-to-join": room_name}
            response = self.tracker_connection.send_and_recv_encrypted_request(requisition)
            
            if response.get("status") != "ok":
                print(f"Erro ao entrar na sala: {response.get('message')}")
                input("Pressione qualquer tecla para retornar...")
                return
            
            print(f"Você entrou no registro da sala '{room_name}'. Conectando aos outros membros...")
            self.current_room = room_name
            self.in_group_chat = True

            req_members = {"cmd": "get-room-members", "room-name": room_name}
            res_members = self.tracker_connection.send_and_recv_encrypted_request(req_members)

            if res_members.get("status") == "ok":
                online_members = res_members.get("members", {})
                
                for username, details in online_members.items():
                    try:
                        print(f"Tentando conectar com {username}...")
                        peer_pub_key = deserialize_public_key(details["peer-public-key"])
                        
                        chat_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        chat_socket.connect((details["user-ip"], details["user-port"]))

                        request_msg = {"type": "group_chat_join", "from_user": self.username, "room_name": self.current_room}
                        encrypted = encrypt_with_public_key(peer_pub_key, json.dumps(request_msg))
                        
                        request_with_public_key = { "public_key": self.tracker_connection.public_key_str, "encrypted": encrypted }
                        
                        chat_socket.send(json.dumps(request_with_public_key).encode())
                        
                        encrypted_response = chat_socket.recv(4096).decode()
                        if not encrypted_response:
                            raise ConnectionError(f"Peer {username} não respondeu.")
                        
                        decrypted_response = decrypt_with_private_key(self.tracker_connection.private_key, encrypted_response)
                        response_data = json.loads(decrypted_response)

                        if response_data.get("type") == "group_join_accept":
                            with self.room_peers_lock:
                                self.room_peers_conn[username] = {"conn": chat_socket, "public_key": peer_pub_key}
                            print(f"Conexão com {username} estabelecida.")
                            threading.Thread(target=self.receive_group_messages, args=(chat_socket, username), daemon=True).start()
                        else:
                            print(f"Falha ao conectar com {username}.")
                            chat_socket.close()
                    except Exception as e:
                        print(f"Erro ao conectar com {username}: {e}")
                
                self.handle_group_chat()
            else:
                print("Não foi possível obter a lista de membros da sala.")
                self.leave_group_chat()
                
        except (ValueError, IndexError):
            print("Seleção inválida.")
        except Exception as e:
            print(f"Erro ao processar requisição: {str(e)}")
            self.in_group_chat = False
            
        input("Pressione qualquer tecla para retornar...")

    def handle_group_chat(self):
        self.clear_terminal()
        print(f"Bem-vindo à sala '{self.current_room}'. Digite '/sair' para sair.")
        
        try:
            while self.in_group_chat:
                message_text = input("Eu: ")
                if not self.in_group_chat:
                    break
                if message_text.lower() == '/sair':
                    break

                message_to_send = {"type": "group_message", "content": message_text}
                json_message = json.dumps(message_to_send)

                with self.room_peers_lock:
                    for peer_user, peer_info in list(self.room_peers_conn.items()):
                        try:
                            encrypted_message = encrypt_with_public_key(peer_info["public_key"], json_message)
                            peer_info["conn"].send(encrypted_message.encode())
                        except (BrokenPipeError, ConnectionResetError):
                            print(f"\n[SALA] A conexão com {peer_user} foi perdida.")
                            peer_info["conn"].close()
                            del self.room_peers_conn[peer_user]
                            print("Eu: ", end="")
        finally:
            self.leave_group_chat()


    def leave_group_chat(self):
        if not self.in_group_chat:
            return

        self.in_group_chat = False 

        notification = {"type": "group_leave"}
        json_notification = json.dumps(notification)
        
        with self.room_peers_lock:
            for peer_info in self.room_peers_conn.values():
                try:
                    encrypted = encrypt_with_public_key(peer_info["public_key"], json_notification)
                    peer_info["conn"].send(encrypted.encode())
                except (BrokenPipeError, ConnectionResetError):
                    pass
                finally:
                    peer_info["conn"].close()
            self.room_peers_conn.clear()

        if self.current_room:
            requisition = {"cmd": "leave-room", "room-name": self.current_room}
            self.tracker_connection.send_and_recv_encrypted_request(requisition)
        
        self.current_room = None
        print("\nVocê saiu da sala.")
        time.sleep(1)

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
        }
        
        try:
            response = self.tracker_connection.send_and_recv_encrypted_request(requisition)          
            if response.get("status") == "ok":
                print(f"Sala '{room_name}' criada com sucesso!")
            else:
                print(f"Erro ao criar sala: {response.get('message')}")
        
        except Exception as e:
            print(f"Erro durante a criação da sala: {str(e)}")
        
        input("Pressione qualquer tecla para retornar: ")

    def process_manage_room(self):
        self.clear_terminal()
        print("========== Gerenciar Sala ==========")
        requisition = {
            "cmd": "list-my-rooms"
        }
        
        response = self.tracker_connection.send_and_recv_encrypted_request(requisition)

        if response.get("status") != "ok" or not response.get("rooms"):
            print("Você não é moderador de nenhuma sala")
            input("Pressione qualquer tecla para voltar...")
            return
        
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
            except ValueError:
                print("Opção inválida")
                continue
            
            match option:
                case 1: self.process_list_room_members(room_name)
                case 2: self.process_add_member(room_name)
                case 3: self.process_remove_member(room_name)
                case 4:
                    if self.process_close_room(room_name):
                        return
                case 0: return
                case _: print("Opção inválida")
        
    def process_list_room_members(self, room_name):
        requisition = {
            "cmd": "list-members",
            "room-name": room_name
        }
        
        response = self.tracker_connection.send_and_recv_encrypted_request(requisition)
        members = response.get("members")
        moderator = response.get("moderator")

        self.clear_terminal()
        print(f"========== Usuários com acesso a sala <{room_name}> ==========")
        print(f"Moderador: {moderator}")
        print("Membros:")
        for member in members:
            print(f"- {member}")

        input("\nPressione qualquer tecla para retornar...")
    
    def process_add_member(self, room_name):
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
        
        response = self.tracker_connection.send_and_recv_encrypted_request(requisition)
        print(response.get("message"))
        input("Pressione qualquer tecla para retornar...")
    
    def process_remove_member(self, room_name):
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
        
        response = self.tracker_connection.send_and_recv_encrypted_request(requisition)
        print(response.get("message"))
        input("Pressione qualquer tecla para retornar...")
    
    def process_close_room(self, room_name):
        confirm = input(f"Tem certeza que deseja fechar a sala '{room_name}'? (s/n): ").strip().lower()
        if confirm != 's':
            print("Operação cancelada")
            return False
        
        requisition = {
            "cmd": "close-room",
            "room-name": room_name
        }
        
        response = self.tracker_connection.send_and_recv_encrypted_request(requisition)
        print(response.get("message"))
        input("Pressione qualquer tecla para retornar...")
        if response.get("status") == "ok":
            return True
        return False

    def clear_terminal(self):
        if os.name == 'nt':
            os.system('cls')
        else:
            os.system("clear")

    def shutdown(self):
        #encerramento correto dos peers atraves do keyboardinterrupt tambem
        print("\n[INFO] Encerrando o peer...")

        if self.in_group_chat:
            self.leave_group_chat()

        self.clean_pending_requests(reject=True)
        self.peer_server_socket.close()
        self.tracker_connection.peer_socket.close()
        print("[INFO] Peer encerrado, Até logo!")


if __name__ == "__main__":
    port = 0
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print("Uso: python peer.py [porta]")
            sys.exit(1)
            
    peer = Peer(peer_listen_port=port)
    try:
        peer.start()
    except KeyboardInterrupt:
        peer.shutdown()
    finally:
        print("\n[INFO] Finalizando processo.")