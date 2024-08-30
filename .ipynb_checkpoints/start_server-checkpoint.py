import socket
import torch
from modelscope import snapshot_download, AutoTokenizer, AutoModelForCausalLM
import random
import sys
import argparse
from agent import my_agent


class InternlmServer:
    def __init__(self, port=None, initial_prompt=None):
        self.host = 'localhost'
        if not port:
            # 生成四位随机数
            port = random.randint(1000, 9999)
        self.port = port
        self.agent = my_agent(initial_prompt)
        
    def RunServer(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((self.host, self.port))
            s.listen()
            print(f"Server is listening on {self.host}:{self.port}")
            listening = True

            while listening:
                conn, addr = s.accept()
                with conn:
                    # print(f"Connected by {addr}")
                    while True:
                        data = conn.recv(1024)
                        if not data:
                            break
                        # response = data.decode('utf-8')  # 处理数据
                        data = data.decode('utf-8')
                        
                        if data == "STOP SERVER!":
                            listening = False
                            conn.sendall("END!!!".encode('utf-8'))
                            break;
                            
                        if data == "CLEAR HISTORY!":
                            self.agent.clear()
                            conn.sendall("END!!!".encode('utf-8'))
                            continue;
                        
                        privious_response = ""
                        for cur_response in self.agent.chat_once(data):
                            # print(cur_response[len(privious_response):], end='')
                            conn.sendall(cur_response[len(privious_response):].encode('utf-8'))
                            privious_response = cur_response
                            
                        conn.sendall("END!!!".encode('utf-8'))
            
                        # response = self.HandleInput(data)
                        # conn.sendall(response.encode('utf-8'))  # 发送响应
                        
    
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', type=int, help="指定端口号")
    parser.add_argument('-i', '--initial_prompt', default=None)
    args = parser.parse_args()

    server = InternlmServer(args.port)
    # print("port:", server.port)
    # sys.stdout.flush()
    
    server.RunServer()
