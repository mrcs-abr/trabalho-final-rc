import threading, os, json, time

ROOM_DATA_FILE = "data_storage/rooms.json"

class Room_manager:
    def __init__(self):
        self.chat_rooms = self.load_rooms()
        self.lock = threading.Lock()

    def load_rooms(self):
        if os.path.exists(ROOM_DATA_FILE):
            try:
                with open(ROOM_DATA_FILE, "r") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                print("Erro ao carregar usuários")
                return {}
        return {}
    
    def save_rooms(self):
        with open(ROOM_DATA_FILE, "w") as f:
            json.dump(self.chat_rooms, f, indent=4)

    def list_rooms(self):
        with self.lock:
            room_list = list(self.chat_rooms.keys())
            return {"status": "ok", "room-list": room_list}
    
    def create_room(self, room_name, creator):
        if not room_name:
            return {"status": "error", "message": "Nome da sala não pode ser vazio"}
        
        with self.lock:
            if room_name in self.chat_rooms:
                return {"status": "error", "message": "Sala já existente"}
            
            self.chat_rooms[room_name] = {
                "moderator": creator,
                "mod-last-seen": time.time(),
                "members": [creator],
                "in-room": []
            }
            self.save_rooms()
            return {"status": "ok", "message": f"Sala '{room_name}' criada com sucesso"}
    
    def join_room(self, room_to_join, user):
        with self.lock:
            if room_to_join not in self.chat_rooms:
                return {"status": "error", "message": "Sala não encontrada"}
            
            if user not in self.chat_rooms[room_to_join]["members"]:
                return {"status": "error", "message": f"Você não é membro desta sala, peça ao moderador <{self.chat_rooms[room_to_join]['moderator']}> para te adicionar."}
            
            # INÍCIO DA ALTERAÇÃO: Adiciona o usuário na lista de membros ativos ('in-room')
            if user not in self.chat_rooms[room_to_join]["in-room"]:
                self.chat_rooms[room_to_join]["in-room"].append(user)
                self.save_rooms()
            # FIM DA ALTERAÇÃO
            
            return {"status": "ok", "message": f"O usuário {user} entrou na sala"}

    def list_my_rooms(self, user):
        with self.lock:
            my_rooms = [
                room_name for room_name, room_data in self.chat_rooms.items()
                if room_data["moderator"] == user
            ]
            return {"status": "ok", "rooms": my_rooms}
    
    def list_members(self, room_name):
        with self.lock:
            if room_name not in self.chat_rooms:
                return {"status": "error", "message": "Sala não encontrada"}
            
            room = self.chat_rooms[room_name]
            return {
                "status": "ok",
                "members": room["members"],
                "moderator": room["moderator"]
            }
    
    def add_member(self, room_name, user_to_add, moderator, users):
        with self.lock:
            if room_name not in self.chat_rooms:
                return {"status": "error", "message": "Sala não encontrada"}
            
            room = self.chat_rooms[room_name]

            if room["moderator"] != moderator:
                return {"status": "error", "message": "Apenas moderadores podem adicionar membros"}
            
            if user_to_add in room["members"]:
                return {"status": "error", "message": "Usuário já é membro desta sala"}
            
            if user_to_add not in users:
                return {"status": "error", "message": "Esse usuário não existe"}
            
            room["members"].append(user_to_add)
            self.save_rooms()
            return {"Status": "ok", "message": f"Usuário {user_to_add} adicionado à sala"}
        
    def remove_member(self, room_name, user_to_remove, moderator):
        with self.lock:
            if room_name not in self.chat_rooms:
                return {"status": "error", "message": "Sala não encontrada"}
            
            room = self.chat_rooms[room_name]

            if room["moderator"] != moderator:
                return {"status": "error", "message": "Apenas moderadores podem remover membros"}

            if user_to_remove == room["moderator"]:
                return {"status": "error", "message": "Moderador não pode ser removido"}

            if user_to_remove in room["members"]:
                room["members"].remove(user_to_remove)
                if user_to_remove in room["in-room"]:
                    room["in-room"].remove(user_to_remove)
                self.save_rooms()
                return {"status": "ok", "message": f"Usuário {user_to_remove} removido da sala"}
            
            return {"status": "ok", "message": "Usuário não encontrado"}

    # INÍCIO DA ALTERAÇÃO: Nova função para um peer notificar que está saindo da sala
    def leave_room(self, room_name, user):
        with self.lock:
            if room_name in self.chat_rooms and user in self.chat_rooms[room_name].get("in-room", []):
                self.chat_rooms[room_name]["in-room"].remove(user)
                self.save_rooms()
                return {"status": "ok", "message": "Você saiu da sala."}
            # Não retorna erro se a sala ou usuário não for encontrado, para evitar problemas de estado inconsistente
            return {"status": "ok", "message": "Você saiu da sala."}
    # FIM DA ALTERAÇÃO

    # INÍCIO DA ALTERAÇÃO: Nova função para obter a lista de membros online (in-room) de uma sala
    def get_online_members_in_room(self, room_name, requesting_user):
        with self.lock:
            if room_name not in self.chat_rooms:
                return {"status": "error", "message": "Sala não encontrada"}
            
            online_members = [
                member for member in self.chat_rooms[room_name]["in-room"]
                if member != requesting_user
            ]
            return {"status": "ok", "online-members": online_members}
    # FIM DA ALTERAÇÃO

    # INÍCIO DA ALTERAÇÃO: Nova função para remover um usuário de todas as listas 'in-room' ao desconectar
    def remove_user_from_all_rooms(self, user):
        with self.lock:
            for room_name in self.chat_rooms:
                if user in self.chat_rooms[room_name].get("in-room", []):
                    self.chat_rooms[room_name]["in-room"].remove(user)
            self.save_rooms()
    # FIM DA ALTERAÇÃO
    
    def update_mod_heartbeat(self, user):
        for room in self.chat_rooms.values():
            if room["moderator"] == user:
                room["mod-last-seen"] = time.time()
    
    def monitor_rooms(self):
        while True:
            time.sleep(10)
            now = time.time()
            to_close = []

            for room_name, room in self.chat_rooms.items():
                if now - room.get("mod-last-seen", now) > 60:
                    print(f"Fechando sala {room_name} por inatividade do moderador")
                    to_close.append(room_name)
            
            for room_name in to_close:
                self.close_room(room_name, self.chat_rooms[room_name]["moderator"])
    
    def close_room(self, room_name, moderator):
        with self.lock:
            if room_name not in self.chat_rooms:
                return {"status": "error", "message": "Sala não encontrada"}
            
            room = self.chat_rooms[room_name]

            if room["moderator"] != moderator:
                return {"status": "error", "message": "Apenas o moderador pode fechar a sala"}

            del self.chat_rooms[room_name]
            self.save_rooms()
            return {"status": "ok", "message": f"A sala {room_name} foi fechada"}