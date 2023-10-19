import grpc
from protobufs.agent_pb2 import agent_query , agent_state , empty
import protobufs.agent_pb2_grpc as agent_pb2_grpc
import threading
from concurrent import futures
from memory_stream_agent import memory_stream_agent
from pathlib import Path

channel = grpc.insecure_channel("localhost:50052")
client  = agent_pb2_grpc.agentStub(channel)

request = agent_query(agentType = "memory_stream_agent" , agentName = "Test1" , roomName = "TESTROOM" ,
                       keyPath = "doc/secret/openai.key" , color = "f9a8d4"  ,promptDir = "doc/prompt/memory_stream/")

rel = client.create_agent(request)
print(rel)