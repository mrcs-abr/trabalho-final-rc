from utils.terminal_utils import clear_terminal

class Peer_room_manager:
    def __init__(self, tracker_connection):
        self.tracker_connection = tracker_connection
    

    def process_manage_room(self):
        clear_terminal()
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
            clear_terminal()
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

        clear_terminal()
        print(f"========== Usuários com acesso a sala <{room_name}> ==========")
        print(f"Moderador: {moderator}")
        print("Membros:")
        for member in members:
            print(f"- {member}")

        input("\nPressione qualquer tecla para retornar...")
    
    def process_add_member(self, room_name):
        clear_terminal()
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
        clear_terminal()
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