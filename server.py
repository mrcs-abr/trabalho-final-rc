import socket, json

peers = {
    "marcos":"xablau"
}

server_name = ''
server_port = 12000
server_info = (server_name, server_port)

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind(server_info)
server_socket.listen()

print("Servidor do chat ativo, esperando conexão na porta {server_port}")


while True:
    connection, address = server_socket.accept()
    print(f"Conexao de {address}")

    data = connection.recv(1024).decode()

    try:
        requisition = json.loads(data)

        if requisition.get("cmd") == "LOGIN":
            user = requisition.get("user")
            print("Nome de usuario recebido: {user}")
            password = requisition.get("password")
            print("Senha recebida: {password}")

            if user in peers and peers[user] == password:
                response = {"status": "OK", "message": "Login bem-sucedido"}
            else:
                response = {"status": "ERROR", "message": "Usuário ou senha incorretos"}
        else:
            response = {"status": "ERROR", "message": "Comando inválido"}

    except json.JSONDecodeError:
        response = {"status": "ERROR", "message": "Formato JSON inválido"}

    connection.send(json.dumps(response).encode())
    connection.close()