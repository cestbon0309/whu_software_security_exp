import socket
import cv2
import pickle
import struct

def send_video(server_ip, server_port):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((server_ip, server_port))
    print(f"Connected to server {server_ip}:{server_port}")
    
    cam = cv2.VideoCapture(0)  # 使用摄像头，如果要截取屏幕，可以使用相应的库，如Pillow
    
    while True:
        ret, frame = cam.read()
        if not ret:
            break
        
        a = pickle.dumps(frame)
        message = struct.pack("Q", len(a)) + a
        client_socket.sendall(message)
    
    cam.release()
    client_socket.close()

if __name__ == '__main__':
    send_video('127.0.0.1', 12345)
