import socket, json, sys, threading, time, os

from utils.encrypt_utils import(
    encrypt_with_public_key,
    decrypt_with_private_key,
    deserialize_public_key,
    serialize_public_key,
    generate_rsa_keys
)

class Tracker_connection_manager:
    def __init__(self, tracker_host="localhost", tracker_port=6000):
        self.tracker_host = tracker_host
        self.tracker_port = tracker_port
        self.tracker_info = (tracker_host, tracker_port)
        self.peer_socket_lock = threading.Lock()
        self.private_key, self.public_key = generate_rsa_keys()
        self.public_key_str = serialize_public_key(self.public_key)
        self.peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.peer_socket.settimeout(5)
        self.tracker_public_key = None

    def connect_to_tracker(self):
        try:
            self.peer_socket.connect(self.tracker_info)
        except socket.error as e:
            print(f"Erro ao conectar ao tracker: {e}")
        
        # Troca de chaves com tracker
        try:
            self.tracker_public_key = deserialize_public_key(
                json.loads(self.peer_socket.recv(4096).decode())["public_key"])
            self.peer_socket.send(json.dumps({"public_key": self.public_key_str}).encode())
        except Exception as e:
            print(f"[Erro] Falha na troca de chaves com tracker {e}")
            sys.exit()


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
    
