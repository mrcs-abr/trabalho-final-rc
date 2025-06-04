import socket, json
from encrypt_utils import generate_rsa_keys, serialize_public_key, deserialize_public_key, encrypt_with_public_key, decrypt_with_private_key, hash_password

class Peer:
    def __init__(self, tracker_host="localhost", tracker_port=6000, peer_port=5500):
        self.tracker_host = tracker_host
        self.tracker_port = tracker_port
        self.tracker_info = (tracker_host, tracker_port)
        self.peer_port = peer_port
        self.peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.private_key, self.public_key = generate_rsa_keys()
        self.public_key_str = serialize_public_key(self.public_key)
        
        try:
            #self.peer_socket.bind(("", self.peer_port))
            self.peer_socket.connect(self.tracker_info)
        except socket.error as e:
            print(f"Erro ao conectar ao tracker: {e}")

        # Key exchange with tracker
        self.tracker_public_key = deserialize_public_key(
            json.loads(self.peer_socket.recv(4096).decode())["public_key"])
        self.peer_socket.send(json.dumps({"public_key": self.public_key_str}).encode())

    def start(self):
        while True:
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
                    option = int(input("->"))
                    continue
            
            match option:
                case 1:
                    self.process_login()
                case 2:
                    self.process_register()
                case 3:
                    self.peer_socket.close()
                    break
    
    def process_login(self):
        while True:
            print("========== Login ==========")
            user = input("Digite seu usuario: ").strip()
            input_password = input("Digite sua senha: ").strip()
            requisition = {
                "cmd": "login", 
                "usr": user, 
                "password": input_password,
                "port": self.peer_port,
            }

            encrypted_requisition = encrypt_with_public_key(
                self.tracker_public_key, json.dumps(requisition))
            self.peer_socket.send(encrypted_requisition.encode())
            
            encrypted_data = self.peer_socket.recv(4096).decode()
            data = decrypt_with_private_key(self.private_key, encrypted_data)
            response = json.loads(data)
            print(response)

            if response.get("status") == "ok":
                print(response.get("message"))
                self.process_chat_functions()
            else:
                print(response.get("message"))
                option = input("Deseja tentar novamente? [s/n]").strip()

                if option == "n":
                    break

    def process_register(self):
        while True:
            print("========== Registro de usuario ==========")
            user = input("Digite um nome de usuario: ").strip()
            input_password = input("Digite uma senha: ").strip()

            if user and input_password:
                requisition = {
                    "cmd": "register", 
                    "usr": user, 
                    "password": input_password,
                    "port": self.peer_port,
                }

                encrypted_requisition = encrypt_with_public_key(
                    self.tracker_public_key, json.dumps(requisition))
                self.peer_socket.send(encrypted_requisition.encode())
                
                encrypted_data = self.peer_socket.recv(1024).decode()
                data = decrypt_with_private_key(self.private_key, encrypted_data)
                response = json.loads(data)

                if response.get("status") == "ok":
                    break
                else:
                    input("O nome de usuário em uso, tente novamente com outro nome.\nPressione qualquer tecla para continuar...")

            else:
                print("Usuario ou senha invalidos, tente novamente")

    def process_chat_functions(self):
        while True:
            print("========== Chatp2p ==========")
            print("Escolha uma opção: ")
            print("[1] Listar usuarios ativos")
            print("[2] Listar salas disponiveis")
            print("[3] Criar sala")
            print("[4] Entrar em uma sala")
            print("[5] Iniciar chat privado")
            print("[6] Gerenciar sala (se moderador)")
            
            try:
                option = int(input("->"))
            except:
                print("Opção inválida")
                option = int(input("->"))
                continue
            
            match option:
                case 1:
                    self.process_list_peers()
                case 2:
                    self.process_list_rooms()
                case 3:
                    self.process_create_room()
                case 4:
                    ...
                case 5:
                    ...
                case 6:
                    self.process_manage_room()
    
    def process_list_peers(self):
        requisition = {
            "cmd": "list-peers"
        }
        encrypted_requisition = encrypt_with_public_key(
        self.tracker_public_key, json.dumps(requisition))
        self.peer_socket.send(encrypted_requisition.encode())
                
        encrypted_data = self.peer_socket.recv(1024).decode()
        data = decrypt_with_private_key(self.private_key, encrypted_data)
        response = json.loads(data)

        users_list = response.get("peer-list")
        
        print("========== Lista de usuários ativos ==========")

        for user in users_list:
            print(f"Usuario: {user}")

        input("pressione qualquer tecla para retornar: ")
    
    def process_list_rooms(self):
        requisition = {
            "cmd": "list-rooms"
        }
        encrypted_requisition = encrypt_with_public_key(
        self.tracker_public_key, json.dumps(requisition))
        self.peer_socket.send(encrypted_requisition.encode())
                
        encrypted_data = self.peer_socket.recv(1024).decode()
        data = decrypt_with_private_key(self.private_key, encrypted_data)
        response = json.loads(data)

        rooms_list = response.get("rooms-list")
        
        print("========== Lista de salas ==========")
        if rooms_list:
            for room in rooms_list:
                print(f"Sala: {room}")
        else:
            print("Não há nenhuma sala disponível no momento")

        input("pressione qualquer tecla para retornar: ")
    
    def process_create_room(self):        
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
            # Envia a requisição criptografada para o tracker
            encrypted_requisition = encrypt_with_public_key(
                self.tracker_public_key, json.dumps(requisition))
            self.peer_socket.send(encrypted_requisition.encode())
            
            # Recebe e decripta a resposta
            encrypted_data = self.peer_socket.recv(1024).decode()
            data = decrypt_with_private_key(self.private_key, encrypted_data)
            response = json.loads(data)
            
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
        print("========== Gerenciar Sala ==========")
        requisition = {
            "cmd": "list-my-rooms"
        }
        
        # Solicita lista de salas que o usuário é moderador
        encrypted_requisition = encrypt_with_public_key(
            self.tracker_public_key, json.dumps(requisition))
        self.peer_socket.send(encrypted_requisition.encode())
        
        encrypted_data = self.peer_socket.recv(4096).decode()
        data = decrypt_with_private_key(self.private_key, encrypted_data)
        response = json.loads(data)
        
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
            print(f"\n========== Gerenciando Sala: {room_name} ==========")
            print("[1] Listar membros")
            print("[2] Adicionar membro")
            print("[3] Remover membro")
            print("[4] Banir usuário")
            print("[5] Fechar sala")
            print("[0] Voltar")
            
            try:
                option = int(input("-> "))
            except:
                print("Opção inválida")
                continue
            
            match option:
                case 1:
                    self.process_list_room_members(room_name)
                case 2:
                    self.process_add_member(room_name)
                case 3:
                    self.process_remove_member(room_name)
                case 4:
                    self.process_ban_user(room_name)
                case 5:
                    self.process_close_room(room_name)
                    return  # Sai do menu após fechar a sala
                case 0:
                    return
                case _:
                    print("Opção inválida")

    def process_list_room_members(self, room_name):
        """Lista todos os membros de uma sala"""
        requisition = {
            "cmd": "list-members",
            "room-name": room_name
        }
        
        self._send_encrypted_request(requisition)
    
    def process_add_member(self, room_name):
        """Adiciona um usuário à sala"""
        user = input("Digite o nome do usuário para adicionar: ").strip()
        if not user:
            print("Nome inválido")
            return
        
        requisition = {
            "cmd": "add-member",
            "room-name": room_name,
            "user": user
        }
        
        self._send_encrypted_request(requisition)
    
    def process_remove_member(self, room_name):
        """Remove um usuário da sala"""
        user = input("Digite o nome do usuário para remover: ").strip()
        if not user:
            print("Nome inválido")
            return
        
        requisition = {
            "cmd": "remove-member",
            "room-name": room_name,
            "user": user
        }
        
        self._send_encrypted_request(requisition)
    
    def process_ban_user(self, room_name):
        """Bane um usuário (impede novo ingresso)"""
        user = input("Digite o nome do usuário para banir: ").strip()
        if not user:
            print("Nome inválido")
            return
        
        requisition = {
            "cmd": "ban-user",
            "room-name": room_name,
            "user": user
        }
        
        self._send_encrypted_request(requisition)
    
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
        
        self._send_encrypted_request(requisition)
    
    def _send_encrypted_request(self, requisition):
        """Helper para enviar requisições criptografadas"""
        encrypted = encrypt_with_public_key(
            self.tracker_public_key, json.dumps(requisition))
        self.peer_socket.send(encrypted.encode())
        
        encrypted_data = self.peer_socket.recv(4096).decode()
        data = decrypt_with_private_key(self.private_key, encrypted_data)
        response = json.loads(data)
        
        print(response.get("message", "Operação concluída"))
        input("Pressione qualquer tecla para continuar...")
        
if __name__ == "__main__":
    peer = Peer()
    peer.start()