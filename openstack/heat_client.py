
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

#!/usr/bin/enlockv python
import requests
from keystoneauth1  import session
from keystoneclient.v2_0 import client
from keystoneauth1.identity import v2
import multiprocessing as mp
from multiprocessing.dummy import Pool as ThreadPool
from multiprocessing import  Lock,Manager
import threading
import time
import datetime
import sys

import os
from heatclient import  client as heatClient
from prettytable import PrettyTable
from pprint import pprint
import signal
import copy
import random
import string
from functools import partial

global TIMEOUT
global results
global spawned_stacks
global spawned_stack_ids
mylock=Lock()


global endpoint_url
global token
def init():

  global endpoint_url
  global  token

  keystone = client.Client(username=os.environ['OS_USERNAME'],
                             password=os.environ['OS_PASSWORD'],
                             tenant_name=os.environ['OS_TENANT_NAME'],
                             auth_url=os.environ['OS_AUTH_URL'])
  print keystone.auth_ref['serviceCatalog'][0]
  endpoint_url= [service['endpoints'][0]['publicURL'] for service in keystone.auth_ref['serviceCatalog']  if service['type'] in ['orchestration']]
  token= keystone.auth_ref['token']['id']
  print endpoint_url[0]



def getHeat():
     global endpoint_url
     global token
     return heatClient.Client('1',endpoint_url[0],token=token)


def abortable_worker(func,*args,**kwargs):
  timeout=kwargs.get("timeout",None)
  stack_id=kwargs.get("stack_id",None)
  stack_name=kwargs.get("stack_name",None)
  main_result=kwargs.get("result",None)
  timeout_results=[]
  timeout_results.append(main_result)
  p=ThreadPool(1)
  timeout_result=initResult()
  res=p.apply_async(func,args=args)
  try:
     out =res.get(timeout) #wait for function to complete
     return out   
  except mp.TimeoutError:
     timeout_result["id"]=stack_id
     timeout_result["name"]=stack_name
     timeout_result["action"]="GET_STATUS"
     timeout_result["status"]="Timeout checking status after 600 secs"
     timeout_results.append(timeout_result)
     #process_results(timeout_results)
     print "terminating due to timeout"
     p.terminate()
     print "Printing timeout result ********************"
     print timeout_results
     return timeout_results


#get status of the object 
def checkstatus(stack_id ,status,result):
    start_time=time.time() * 1000
    status_results=[]
    status_results.append(result)
    #nova =novaClient.Client("2",os.environ['OS_USERNAME'], os.environ['OS_PASSWORD'], "admin", os.environ["OS_AUTH_URL"], service_type="compute")
    print"Get Nova instancefor checking status" + status
    heat=getHeat()
    print "Checking status for "+ stack_id
    #time.sleep(1)
    status_result=initResult()
        # Retrieve the instance again so the status field updates
    while status=='CREATE_IN_PROGRESS':
      try:
        stack= heat.stacks.get(stack_id=stack_id)
        if stack.stack_status!=status:
            status_result["invoked_time"]=str(datetime.datetime.now())
            status=stack.stack_status
            status_result["action"]="GET_STATUS"
            status_result["status"]=status
            status_result["time"] =  0
      except Exception as err:
        status_result["error_state"]=err
        status='ERROR'
    status_result["status_time_diff"]=(time.time() * 1000) - start_time
    status_results.append(status_result)
    print "Status check completed"
    #delete instance
    #try:
    #   delete_result=initResult()
    #   delete_result["invoked_time"]=str(datetime.datetime.now())
    #   delete_result["action"]="DELETE"
    #   nova.reset_timings()
    #   nova.servers.delete(instance_id)
    #   delete_result["status"]="Deleteing"
    #   delete_result["time"]= getTimings(nova.get_timings())
    #except Exception as err:
    #   print "error "
    #   delete_result["action"]="DELETE"
    #   delete_result["error_state"]=err
 
    #status_results.append(delete_result)
    #print "After deleteing"
    #print status_results
    return status_results    

def delete_deployed_stacks():
 global spawned_stacks
 heat=getHeat()
 deleted_results=[]
 for stack_id in  spawned_stack_ids:
     try:
       delete_result=initResult()
       delete_result["id"]=stack_id
       delete_result["name"]=spawned_stacks[stack_id]
       delete_result["invoked_time"]=str(datetime.datetime.now())
       delete_result["action"]="DELETE"
       heat.stacks.delete(stack_id)
       delete_result["status"]="Deleteing"
       delete_result["time"]= 0 
     except Exception as err:
       print "error "
       delete_result["action"]="DELETE"
       delete_result["error_state"]=err

     deleted_results.append(delete_result)
 return deleted_results

def init_worker():
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def id_generator(size=6, chars=string.ascii_uppercase + string.digits):
      return ''.join(random.choice(chars) for _ in range(size))

def process_results(r):
  global results
  global mylock
  mylock.acquire()
  results.append(r)
  mylock.release()

def init_worker():
    signal.signal(signal.SIGINT, signal.SIG_IGN)


#deploy instance    
def heat_deploy_template(no_of_stacks,clean_up=True):
 
  global TIMEOUT
  index=0
  heat =getHeat()
  #l = mp.Lock()
  stack_count=0
  global spawned_stacks
  global spawned_stack_ids
  global results
  manager=Manager()
  #global results
  stack_name="HIGHLANDER_"+id_generator() +"_"

  template_file = 'template/instance_heat.yaml'
  template = open(template_file, 'r')
  heat_template=template.read()

  # pool=mp.Pool(initializer=initLock,initargs=(l,))
  pool=mp.Pool(processes=10, initializer=init_worker)
  print "Starting to deploy instance"
  spawned_stacks={}
  spawned_stack_ids=[]
  while stack_count<=no_of_stacks:

    try:
       # Starting nova instance
        stack_results=[]
        result=initResult()
        result["action"]="Create Stack"
        result["invoked_time"]=str(datetime.datetime.now())
        print "Starting to deploy stack %s", stack_name + "_"+ str(stack_count)
        start_time=time.time() * 1000
        stack=None
        try:
	    stack=heat.stacks.create(stack_name=stack_name + "_"+ str(stack_count),template=heat_template,parameters={})
        except Exception as Err:
            print "Exception Occured,while creating stack.. retrying again ",Err
            time.sleep(1)
            continue
        stack_count=stack_count+1
        result["status_time_diff"]=(time.time() * 1000) - start_time
        stack_id= stack["stack"]["id"]
        spawned_stacks[stack_id]=stack_name + "_"+ str(stack_count)
        spawned_stack_ids.append(stack_id)
	result["time"]=0
        result['id']=stack_id
        result['name']=stack_name + "_"+ str(stack_count)
        # Poll at 2?? second intervals, until the status is no longer 'BUILD' or need to decide when to stop '' till it is running?
        #check the status
        stack=heat.stacks.get(stack_id=stack_id)
	status =  stack.stack_status 
        result["status"]=status
        if status=="ERROR":
           result["error_state"]="Unknow Error : Check stack status" 
           print result
           #results.append(result) 
           #print_result(stack_results)
           #exit(0) #do you wan to exit here or continue deploying next
        #results.append(result) 
        #exit(0)
        else:
           print "sending thread to check status..."
           copy_result=copy.deepcopy(result)
           abortable_func=partial(abortable_worker,checkstatus,result=copy_result,stack_name=(stack_name + str(stack_count)),stack_id=stack_id,timeout=300)
           pool.apply_async(abortable_func ,args=( stack_id,status,copy_result,),callback=process_results)
           time.sleep(0.200)
    #if the status is Not Build, delete 
    except KeyboardInterrupt:
        print "*******************************"
        print "You EVIL bastard!"
        print "*******************************"   
        stack_count=no_of_stacks+1
        print "Exiting........"
        time.sleep(5)
        pool.close()
        #pool.terminate()
        print "pool terminated... waiting to join"
        pool.join()
        print "printing results"
         #print_result(results)
         #time.sleep(5)
         #exit(1)
    except Exception as err:
        print "Exception occured %s",err
        #result["error_state"]=err
        #results.append(result)
     #print_result(results)
     #Delete instance and print
     #result=delete_instance(nova,instance_id)
     #results.append(result)
  pool.close()
  pool.join()
  print "\nFinally, here are the results:"
  #print results
  print "spawned stacks"
  for i in spawned_stacks:
    print i
  print "*************results*******************"
  print results
  print_result(results)
  if clean_up==True: 
    print "deleteing stacks"
    delete_results=[]
    delete_results.append(delete_deployed_stacks())
    print "delete results"
    print delete_results
    print_result(delete_results)

def initResult():
    return {"id":'',"name":'',"action":'',"status":'',"time":'',"error_state":'',"invoked_time":'',"fault":'',"status_time_diff":0}

def getStackList():
	heat=getHeat()
	stack= list(heat.stacks.list())
        print stack

def print_result(results):
  print "Printing results"
  table = PrettyTable(['id','name','action', 'status','time','error_state','Invoked_time','fault','status_time_diff'],encoding="UTF-8")
  for result_1 in results:
      for result in result_1:
         try:
            table.add_row([result['id'],result['name'],result["action"],result["status"],result['time'], result["error_state"],result['invoked_time'],result['fault'],result['status_time_diff']])
         except:
            print "failed table"
            print result


  print table


if __name__ == '__main__':
   global results
   global TIMEOUT
   TIMEOUT=600
   results=[]
   init()
   heat_deploy_template(10,False)
   #getStackList()


