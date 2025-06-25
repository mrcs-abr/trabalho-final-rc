import threading
from utils.terminal_utils import clear_terminal

class Auth_manager():

    def __init__(self, tracker_connection, peer_atributes):
        self.tracker_connection = tracker_connection
        self.peer_atributes = peer_atributes
    
    def process_login(self):
        while True:
            clear_terminal()
            print("========== Login ==========")
            user = input("Digite seu usuario: ").strip()
            input_password = input("Digite sua senha: ").strip()
            requisition = {
                "cmd": "login", 
                "usr": user, 
                "password": input_password,
                "peer-listen-port": self.peer_atributes.peer_listen_port,
            }

            response = self.tracker_connection.send_and_recv_encrypted_request(requisition)

            if response.get("status") == "ok":
                print(response.get("message"))
                self.peer_atributes.username = user
                threading.Thread(target=self.tracker_connection.send_heartbeat, daemon=True).start()
                self.peer_atributes.process_chat_functions()
                return
            else:
                print(response.get("message"))
                option = input("Deseja tentar novamente? [s/n]: ").strip()

                if option == "n":
                    break

    def process_register(self):
        while True:
            clear_terminal()
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
