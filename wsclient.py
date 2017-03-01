# Copyright 2015 - Aputtur, Inc.
#
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.


#!/usr/bin/python
import websocket
import threading
import thread
import time
import sys
import datetime
import json
from time import sleep
import signal
import logging
import ConfigParser
import copy
logging.basicConfig()

global messagecount 
global ip_address
global port
global ws_url
global action_type

buff = []
global last_data
#ON MESSAGE- PRINT ONLY IF HOSTNAME or STATUS Changes
def on_message(ws, message):
    global buff
    global last_data
    global messagecount
    global action_type
    results={}
    server_status="UNKNOW"
    
    #if pong operation then diff = current recived  time - last Client recv time
    #if ping operation then diff = Current Server sent time - Client Recv time  
    data=json.loads(message)
    data["time_r"]= time.time() * 1000
    if action_type=="pong":
       if last_data:
          data["diff"]=data["time_r"]-last_data["time_r"]
       last_data=copy.deepcopy(data)
    else:
        data["diff"]=data["time_r"]-data["time_s"]
    
    buff.append(data)
    print data  
    #sys.stdout.write(message)
    #sys.stdout.flush()


def on_error(ws, error):
   #sys.stdout.flush()
   #sys.stdout.write("\n")
   print ("Error @ "+ str(datetime.datetime.now()) +"\r\n" )
   # sys.stdout.write("-------------CLOSED DUE TO ERROR ---------------\r\n")
   # sys.stdout.flush() 


def on_close(ws):
   # sys.stdout.flush()
   # sys.stdout.write("\n")
   # print ("\n################# closed ################\r\n")
   print ("Closed Time -" + str(datetime.datetime.now()) + "... trying to reconnect\r")
   # sys.stdout.flush()
   sleep(0.10)
   reconnect()   
 

def reconnect():
  #Clear last data if reconnecting
  global last_data
  last_data={} 
  if not buff:
    print "Printing all data from buffer"
    for i in buff:
       print i
  
  for _ in range(max_retries):
     sleep(0.10)
     try:
       connect()
     except KeyboardInterrupt:
       sys.stdout.write("\nEXIT..... \r\n" )
       sys.stdout.flush()
       #print all array list
       print "Printing all data from buff"
       for i in buff:
	 print i
       sys.exit(1)
 

#Acton can be ping or pong as set in configuration file
def connect():
    global messagecount
    global ws_url
    global action_type
    messagecount=0
    ws = websocket.WebSocketApp(ws_url,
                                on_message = on_message,
                                on_error = on_error,
                                on_close = on_close)
    print ("##########################Connected" +  str(datetime.datetime.now())+"\r")
    # sys.stdout.flush() 
    if action_type=="pong":
       ws.on_open = on_open
       ws.run_forever()
    else:
      wst = threading.Thread(target=ws.run_forever)
      wst.daemon = True
      wst.start()
      conn_timeout = 25
      while not ws.sock.connected and conn_timeout:
         sleep(1)
         conn_timeout -= 1

      sno = 0
      while ws.sock.connected and action_type=="ping":
        sno= sno+1
        sleep(0.10)
        data={"no":sno,"time_s":  time.time() * 1000, "time_r":0 ,"s_time_r":0 ,"s_time_s":0 ,"diff":0 ,"hostname":'',"status":"UNKNOWN" }
        ws.send(json.dumps(data))

 

#ON OPEN SEDN JSON DATA with -time client_recived_0,server_time_sent=0,
def on_open(ws):
    #print "***********************CONNECTION OPEN************************"
    #print "sending message time " +  str(datetime.datetime.now())
    data={"no":1,"time_s": str(datetime.datetime.now()), "time_r":0 ,"s_time_r":0 ,"s_time_s":0 ,"diff":0 ,"hostname":'',"status":"UNKNOWN" }
    json_data=json.dumps(data)
    ws.send(json_data)


          

def Exit_gracefully(signal, frame):
    sys.exit(0)

if __name__ == "__main__":
    #websocket.enableTrace(True)
    messagecount = 0
    packetseq  = 0
    max_retries = 10000
    last_data ={}
    config = ConfigParser.ConfigParser()
    config.read("client.cfg")
    ip_address=config.get("server","ip_address")
    print(ip_address);
    port=config.get("server","port")
    action_type = config.get("action","type")
    ws_url="ws://"+ ip_address +":"+ port+"/"+action_type
    
    # store the original SIGINT handler
    signal.signal(signal.SIGINT, Exit_gracefully)
    connect()


