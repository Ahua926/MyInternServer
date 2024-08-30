import socket
import sys
import argparse


def connect(port, meaasge):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client_socket.connect(('localhost', port))
        return client_socket
    except socket.error as e:
        # 连接失败时输出错误信息
        # print(f"连接失败，错误信息：{e}")
        return None
    

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', type=int, default=None)
    parser.add_argument('-m', '--message', default=None)
    args = parser.parse_args()
    
    port = args.port
    message = args.message
    
    client_socket = connect(port, message)
    if client_socket:
        client_socket.sendall(message.encode('utf-8'))
        recving = True
        while recving:
            # 接收数据，1024字节为缓冲区大小
            data = client_socket.recv(1024)
            data = data.decode('utf-8')
            
            if(data == "END!!!"):
                recving = False
                break
            
            print(data, end="")
            sys.stdout.flush()
        print("")
        client_socket.close()
    else:
        response = "..."
        print("response:", response)
        sys.stdout.flush()