import socket, json

import socket

server_name = ''
server_port = 12000
server_info = (server_name, server_port)

client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client_socket.connect(server_info)

print("========== Tela inicial ==========")
print("1- Login")
print("2- Registrar")
option = int(input())

match option:
    case 1:
        user = input("Digite seu nome de usuario: ").strip()
        password = input("Digite sua senha: ").strip()
        client_requisition = {
        "cmd": "LOGIN",
        "user": user,
        "password": password
        }
    case 2:
        ...

client_socket.send(json.dumps(client_requisition).encode())
response = client_socket.recv(1024).decode()

try:
    json_response = json.loads(response)
    print(f"{json_response.get('message')}")
except json.JSONDecodeError:
    print("Erro na resposta do servidor")

client_socket.close()

