import socket
import json
from PIL import Image, ImageGrab
import io
import threading
import os
import subprocess
import time
import platform
import tkinter as tk
from tkinter import messagebox, simpledialog

listen_port = 13377
dest_addr_file = ('127.0.0.1', 8891)

connect_request = {
    "request": "connect",
    "listening_port": listen_port,
    "option": ""
}

def get_screenshot():
    screenshot = ImageGrab.grab()
    byteio = io.BytesIO()
    screenshot.save(byteio, format='PNG')
    byte_data = byteio.getvalue()
    byteio.close()
    print(f'raw data size:{len(byte_data)}')
    return byte_data

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

def get_directory(path):
    if platform.system() == 'Windows':
        if path == '/':
            # Return all drives on Windows
            return {"files": get_drives_windows()}
    
    if not os.path.exists(path):
        return {"error": "Path does not exist"}
    
    files = []
    try:
        for entry in os.listdir(path):
            full_path = os.path.join(path, entry)
            if os.path.isdir(full_path):
                files.append({
                    "name": entry,
                    "path": full_path,
                    "type": "directory"
                })
            elif os.path.isfile(full_path):
                files.append({
                    "name": entry,
                    "path": full_path,
                    "type": "file"
                })
    except PermissionError:
        return {"error": "Permission denied"}
    except Exception as e:
        return {"error": str(e)}
    
    return {"files": files}

def send_directory_info_to_server(path, dest_addr_file):
    dir_info = get_directory(path)
    if "error" in dir_info:
        error_message = json.dumps(dir_info).encode()
        tcp_socket_send_dir_info = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_socket_send_dir_info.connect(dest_addr_file)
        tcp_socket_send_dir_info.sendall(error_message)
        tcp_socket_send_dir_info.close()
    else:
        dir_json = json.dumps(dir_info).encode()
        tcp_socket_send_dir_info = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_socket_send_dir_info.connect(dest_addr_file)
        tcp_socket_send_dir_info.sendall(dir_json)
        tcp_socket_send_dir_info.close()

def receive_commands(conn: socket):
    print("开始接收命令...")
    while True:
        try:
            data = conn.recv(1024)  # Buffer size is 1024 bytes
            if not data:
                continue
            command = data.decode().strip()
            print(f"Received command: {command}")

            if command == 'screenshot':
                screenshot_data = get_screenshot()                
                tcp_socket_send_screenshot = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                tcp_socket_send_screenshot.connect(dest_addr_file)
                tcp_socket_send_screenshot.sendall(screenshot_data)
                tcp_socket_send_screenshot.close()
                print("Screenshot sent successfully.")
            
            elif command.startswith('command'):
                cmd = command[7:].split(' ')
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
                socket_command_result = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                socket_command_result.connect(dest_addr_file)
                socket_command_result.sendall(result.stdout.encode() + result.stderr.encode())
                socket_command_result.close()
                print(f'Command result: {result.stdout}')

            elif command.startswith('download'):
                path = command[8:]
                with open(path, 'rb') as f:
                    data = f.read()
                socket_file_down = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                socket_file_down.connect(dest_addr_file)
                socket_file_down.sendall(data)
                socket_file_down.close()
                print(f'file sent')
            
            elif command.startswith('fetch'):
                path = command[5:]
                send_directory_info_to_server(path, dest_addr_file)
            
        except Exception as e:
            socket_command_result = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            socket_command_result.connect(dest_addr_file)
            socket_command_result.sendall("Command execution failed, this is a client-side error".encode())
            socket_command_result.close()
            print(f"Error receiving commands: {e}")
            continue

def create_overlay_window(server_ip):
    root = tk.Tk()
    root.overrideredirect(True)  # Remove window decorations
    root.attributes('-topmost', True)  # Keep the window always on top
    root.geometry("+{}+{}".format(root.winfo_screenwidth()-250, root.winfo_screenheight()-100))  # Position at bottom right corner
    
    frame = tk.Frame(root, bg='white', bd=1, relief=tk.SOLID)
    frame.pack(padx=10, pady=10)
    
    label_text = f"当前设备正在被远程管理\n服务端IP: {server_ip}"
    label = tk.Label(frame, text=label_text, bg='white', fg='black')
    label.pack(side=tk.TOP, padx=5, pady=5)
    
    exit_button = tk.Button(frame, text="退出", command=lambda: terminate_client(root), bg='red', fg='white')
    exit_button.pack(side=tk.BOTTOM, padx=5, pady=5)
    
    def close_window(event=None):
        if messagebox.askokcancel("退出", "确定要退出吗？"):
            terminate_client(root)
    
    root.protocol("WM_DELETE_WINDOW", close_window)
    root.bind('<Escape>', close_window)
    
    root.mainloop()

def terminate_client(root):
    root.destroy()
    os._exit(0)  # Forcefully exit the program

def show_connection_status(status_label, retry_label, change_ip_button, server_ip, retries=5):
    global dest_addr
    try:
        dest_addr = (server_ip, 8890)
        tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_socket.connect(dest_addr)
        print(f"Connected to server at {dest_addr}")
        
        # 发送连接请求
        tcp_socket.sendall(json.dumps(connect_request).encode())
        print("Connection request sent.")
        
        # 启动一个新线程来接收命令
        command_thread = threading.Thread(target=receive_commands, args=(tcp_socket,), daemon=True)
        command_thread.start()

        # 创建并启动悬浮窗
        overlay_thread = threading.Thread(target=create_overlay_window, args=(server_ip,), daemon=True)
        overlay_thread.start()

        status_label.config(text=f"成功连接到服务端: {server_ip}", fg='green')
        retry_label.pack_forget()
        change_ip_button.pack_forget()
    except Exception as e:
        print(f"Failed to connect to server: {e}")
        status_label.config(text=f"无法连接到服务端: {server_ip}", fg='red')
        retry_label.config(text=f"将在 {retries} 秒后重试")
        retry_label.after(1000, lambda: show_connection_status_retry(status_label, retry_label, change_ip_button, server_ip, retries-1))

def show_connection_status_retry(status_label, retry_label, change_ip_button, server_ip, retries):
    if retries <= 0:
        retry_label.config(text="重试次数已用完，请手动更改IP地址")
        change_ip_button.pack(side=tk.RIGHT, padx=5, pady=5)
        return
    
    retry_label.config(text=f"将在 {retries} 秒后重试")
    retry_label.after(1000, lambda: show_connection_status_retry(status_label, retry_label, change_ip_button, server_ip, retries-1))
    show_connection_status(status_label, retry_label, change_ip_button, server_ip, retries)

def prompt_for_server_ip():
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    
    server_ip = simpledialog.askstring("输入服务器IP", "请输入服务端的IP地址:")
    if server_ip is None:
        messagebox.showwarning("警告", "未输入IP地址，程序将退出")
        os._exit(0)
    
    return server_ip

def main():
    server_ip = prompt_for_server_ip()
    
    root = tk.Tk()
    root.title("连接状态")
    root.geometry("300x100")
    
    status_label = tk.Label(root, text="", font=("Arial", 12))
    status_label.pack(pady=10)
    
    retry_label = tk.Label(root, text="", font=("Arial", 10))
    retry_label.pack(pady=5)
    
    change_ip_button = tk.Button(root, text="更改IP", command=lambda: change_ip(root, status_label, retry_label, change_ip_button))
    change_ip_button.pack_forget()
    
    show_connection_status(status_label, retry_label, change_ip_button, server_ip)
    
    root.mainloop()

def change_ip(root, status_label, retry_label, change_ip_button):
    new_server_ip = prompt_for_server_ip()
    if new_server_ip:
        status_label.config(text="")
        retry_label.config(text="")
        change_ip_button.pack_forget()
        show_connection_status(status_label, retry_label, change_ip_button, new_server_ip)

if __name__ == '__main__':
    main()



