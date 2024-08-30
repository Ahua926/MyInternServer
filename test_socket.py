import socket

# 设置服务器的端口和地址
PORT = 6006
SERVER = socket.gethostbyname(socket.gethostname())

# 创建socket对象
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
    # 防止地址已经被使用
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    # 绑定端口
    server_socket.bind((SERVER, PORT))
    
    # 监听连接请求
    server_socket.listen()

    print(f"Listening on {SERVER}:{PORT}...")

    while True:
        # 接受客户端的连接
        client_socket, addr = server_socket.accept()
        print(f"Connected by {addr}")

        try:
            while True:
                # 接收数据
                data = client_socket.recv(1024)
                if not data:
                    break  # 如果没有接收到数据，跳出循环
                print(f"Received: {data.decode('utf-8')}")

                # 发送数据
                client_socket.sendall(data)  # 回显接收到的数据
        finally:
            client_socket.close()
            # 关闭客户端连接
