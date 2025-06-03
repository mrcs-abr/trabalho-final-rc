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
                    print(response)
                    break           
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
                    ...
                case 4:
                    ...
                case 5:
                    ...
    
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

        

if __name__ == "__main__":
    peer = Peer()
    peer.start()