# Chat P2P com Autenticação via tracker
Este projeto é a implementação de um sistema de chat peer-to-peer para redes locais sem NAT/Firewall, com autenticação centralizada e suporte para comunicação segura utilizando criptografia ECC.

## Funcionalidades
### 1. Tracker (Servidor Central)
- Gerencia logins com usuário e senha criptografada
- Mantém lista de peers ativos e salas disponíveis
### 2. Peer (Cliente)
- Conecta-se ao tracker e a outros peers
- Envia mensagens cifradas com criptografia ECC
- Cria ou ingressa em salas de chat (grupo)

## Estrutura do projeto
```bash
├── chatp2p
│   ├── data_storage
│   ├── peer_managers
│   │   ├── auth_manager.py
│   │   └── tracker_connection_manager.py
│   ├── peer.py
│   ├── tracker_managers
│   │   ├── room_manager.py
│   │   └── user_manager.py
│   ├── tracker.py
│   └── utils
│       ├── encrypt_utils.py
│       └── terminal_utils.py
└── README.md
```

## Como rodar o projeto
### Pré-requisitos

- PyNaCl     1.5.0
- Python 3.11.2
- pip        23.0.1

### Clone do repositório
Antes de clonar o repositório sugere-se criar um ambiente virtual em algum caminho de sua preferência, sugestão:
```bash
python -m venv chatp2p
cd chatp2p
```

Instale a versão adequada do python e da biblioteca PyNaCl

Para ter acesso ao conteúdo do projeto, clone o repositório para o ambiente virtual criado utilizando o seguinte comando no terminal:
```bash
git clone git@github.com:mrcs-abr/trabalho-final-rc.git
```
### Build do projeto
Coloque o tracker para rodar com
```bash
python tracker.py
```
Para teste pode-se rodar peers com
```bash
python peer.py
```







