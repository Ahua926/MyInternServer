import socket

# 服务器的IP地址和端口
HOST = 'localhost'
PORT = 12345

# 创建一个socket对象
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# 连接到服务器
client_socket.connect((HOST, PORT))

# 发送数据
message = 'Hello, Server!'
client_socket.sendall(message.encode('utf-8'))

# 接收响应
response = client_socket.recv(1024)
print('Received from server:', response.decode('utf-8'))

# 关闭连接
client_socket.close()
