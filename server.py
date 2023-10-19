import grpc
from protobufs.agent_pb2 import agent_query , agent_state , empty
import protobufs.agent_pb2_grpc as agent_pb2_grpc
import threading
from concurrent import futures
from memory_stream_agent import memory_stream_agent
from pathlib import Path

class agent_service(agent_pb2_grpc.agentServicer):
    
    def __init__(self):
        self.agent_type_dict = {
            "memory_stream_agent" : memory_stream_agent
        }
        self.agent_list = []
        
    def create_agent(self , request , context):
        
        agent_type = request.agentType
        agent_name = request.agentName
        room_name = request.roomName 
        key_path = request.keyPath
        color = request.color
        prompt_dic = request.promptDir

        agent = self.agent_type_dict[agent_type](openai_token = Path(key_path) , 
                                                 agent_name=agent_name ,
                                                 room_name=room_name,
                                                 color=color,
                                                 prompt_dir=prompt_dic ,
                                                 server_url = "http://localhost:8001")
        
        self.agent_list.append(agent)
        return agent_state(agentID = len(self.agent_list))

def serve():

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    agent_pb2_grpc.add_agentServicer_to_server((agent_service()), server)
    print('server start ')
    server.add_insecure_port("[::]:50052")
    server.start()
    server.wait_for_termination()




    

if __name__ == '__main__':
    serve()