from flask import Flask, render_template, Response
import socket
import threading
import cv2
import numpy as np
import pickle

app = Flask(__name__)

# 存储客户端屏幕截图的变量
frame = None

def receive_video(client_socket):
    global frame
    while True:
        try:
            data = b""
            payload_size = struct.calcsize("Q")
            while True:
                packet = client_socket.recv(4*1024)
                if not packet: break
                data += packet
                if len(data) > payload_size:
                    break
            packed_msg_size = data[:payload_size]
            data = data[payload_size:]
            msg_size = struct.unpack("Q", packed_msg_size)[0]
            
            while len(data) < msg_size:
                data += client_socket.recv(4*1024)
            frame_data = data[:msg_size]
            data = data[msg_size:]
            
            frame = pickle.loads(frame_data)
        except Exception as e:
            print(f"Error: {e}")
            break

def start_server(host='0.0.0.0', port=12345):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((host, port))
    server_socket.listen(1)
    print(f"Server listening on {host}:{port}")
    
    client_socket, addr = server_socket.accept()
    print(f"Client {addr} connected")
    
    video_thread = threading.Thread(target=receive_video, args=(client_socket,))
    video_thread.start()

@app.route('/')
def index():
    return render_template('index.html')

def gen():
    global frame
    while True:
        if frame is not None:
            ret, jpeg = cv2.imencode('.jpg', frame)
            frame = None
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(gen(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    server_thread = threading.Thread(target=start_server)
    server_thread.start()
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader = True)
