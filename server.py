from flask import Flask, render_template, jsonify, request
import socket
import threading
import json
from flask_socketio import SocketIO, emit

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
        socketio.emit('new_client', {'address': str(addr)}, broadcast=True)

def handle_client(client_conn, addr):
    while True:
        try:
            data = client_conn.recv(1024)  # Buffer size is 1024 bytes
            if not data:
                break
            data = json.loads(data)
            if data["request"] == "connect":
                clients[addr] = client_conn
                print(clients)
            else:
                udp_messages.append((addr, data["option"]))
        except Exception as e:
            print(f"Error handling client {addr}: {e}")
            break
    client_conn.close()
    del clients[addr]
    # Notify frontend about disconnected client
    socketio.emit('client_disconnected', {'address': str(addr)}, broadcast=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/messages')
def messages():
    return jsonify(udp_messages)

@app.route('/remote_control', methods=["POST"])
def remote_control():
    data = request.get_json()
    print(data)
    if data['data'] == 'screenshot':
        addr = tuple(map(int, data['addr'].split(':')))
        if addr in clients:
            client_conn = clients[addr]
            client_conn.sendall(b'screenshot')
            screenshot_data, _ = sock_file.accept()
            screenshot_data = screenshot_data.recv(1024 * 1024 * 1024)  # Adjust buffer size as needed
            sock_file.close()
            # Process the screenshot_data here if needed
            return jsonify({"status": "success", "data": screenshot_data.hex()})
        else:
            return jsonify({"status": "error", "message": "Client not found"})
    return jsonify({"status": "error", "message": "Invalid command"})

if __name__ == '__main__':
    # Start TCP listener in a separate thread
    threading.Thread(target=listener, daemon=True).start()
    
    # Start Flask app with SocketIO
    socketio.run(app, host='0.0.0.0', port=8989)



