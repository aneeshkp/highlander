#!/usr/bin/enlockv python
import os
import requests
import multiprocessing as mp
from multiprocessing.dummy import Pool as ThreadPool
from multiprocessing import  Lock,Manager
import threading
import time
import datetime
import sys
from keystoneauth1  import session
from keystoneclient.v2_0 import client
from novaclient import client  as novaClient
from glanceclient import client as glanceClient
from neutronclient.v2_0 import client as neutronClient
from keystoneauth1.identity import v2
from prettytable import PrettyTable
from pprint import pprint
import signal
import copy
import random
import string
from functools import partial

global results
global spawned_instances
global spawned_instance_ids
global TIMEOUT
mylock=Lock()


def get_nova_creds():
    d = {}
    d['username'] = os.environ['OS_USERNAME']
    d['api_key'] = os.environ['OS_PASSWORD']
    d['auth_url'] = os.environ['OS_AUTH_URL']
    d['project_id'] = os.environ['OS_TENANT_NAME']
    return d



def init():

  
  FLAVOR_NAME="cirros.1"
  NETWORK_NAME="default"
  IMAGE_NAME="cirros-0.3.4"

  #keystone = client.Client(username=os.environ['OS_USERNAME'],
  #                             password=os.environ['OS_PASSWORD'],
  #                             tenant_name=os.environ['OS_TENANT_NAME'],
  #                             auth_url=os.environ['OS_AUTH_URL'])
  
  auth = v2.Password(auth_url=os.environ["OS_AUTH_URL"],
                      username=os.environ["OS_USERNAME"],
                      password=os.environ['OS_PASSWORD'],
                      tenant_name=os.environ['OS_TENANT_NAME']
                     )

  sess = session.Session(auth=auth)

  #get keystone session
  keystone=client.Client(session=sess)
  #print keystone.tenants.list()

  nova  = getNova(keystone.session)
  #nova = novaClient.Client("2", keystone.session,timings=True,timeout=1)
  flavor= nova.flavors.find(name=FLAVOR_NAME)
  if not flavor:
    print "No flavour found"
    exit(0) 
  #Get glance images
  glance =glanceClient.Client("1",session=keystone.session)
  image= glance.images.find(name=IMAGE_NAME)
  if not image:
    print "No image found"
    exit(0)

  #get neutron /netrowk info
  neutron=neutronClient.Client(session=keystone.session)
  networks= neutron.list_networks(name=NETWORK_NAME)
  if not networks:
    print "No default network found"
    exit(0)

  nics = [{'net-id':networks['networks'][0]['id']}]
  return keystone.session,image,flavor,nics

#get Nova object
def getNova(session=None):
    try:
       if session==None:
         return novaClient.Client("2",timings=True,timeout=600,**get_nova_creds()) 
       else:
        return  novaClient.Client("2",session=session,timings=True,timeout=600)
    except Exception as err:
       print "Error returning nova object %s",err
     
    return None 


#get status of the object 
def checkstatus( instance_id,status,result):
    start_time=time.time() * 1000
    status_results=[]
    status_results.append(result)
    #nova =novaClient.Client("2",os.environ['OS_USERNAME'], os.environ['OS_PASSWORD'], "admin", os.environ["OS_AUTH_URL"], service_type="compute")
    #print"Get Nova instancefor checking status" + status
    nova=None
    print "Checking status for "+instance_id
    #time.sleep(1)
    status_result=initResult()
        # Retrieve the instance again so the status field updates
    while status=='BUILD':
      try:
        if nova==None:
            nova =getNova()
        nova.reset_timings()
        instance = nova.servers.get(instance_id)
        if instance.status!=status:
            status_result["invoked_time"]=str(datetime.datetime.now())
            status=instance.status
            status_result["action"]="GET_STATUS"
            status_result["status"]=status
            if hasattr(instance,"fault"):
                status_result["fault"]=get_fault(instance.fault)
            status_result["time"] =  getTimings(nova.get_timings())
      except Exception as err:
        print "Exception occured inside check status"
        #if isinstance(err,novaclient.exceptions.ClientException):
        #   print "It's NovaClient Exception ... reseting"
        nova =None
       
        status_result["error_state"]=err
        status='ERROR'
    status_result["status_time_diff"]=(time.time() * 1000) - start_time
    status_results.append(status_result)
    print "Complete checking status for "+instance_id
    print status_results
    return status_results    


def delete_deployed_instances():
 global spawned_instances
 nova=getNova()
 deleted_results=[]
 for instance_id in  spawned_instance_ids:
     try:
       delete_result=initResult()
       delete_result["id"]=instance_id
       delete_result["name"]=spawned_instances[instance_id]
       delete_result["invoked_time"]=str(datetime.datetime.now())
       delete_result["action"]="DELETE"
       nova.reset_timings()
       nova.servers.delete(instance_id)
       delete_result["status"]="Deleteing"
       delete_result["time"]= getTimings(nova.get_timings())
     except Exception as err:
       delete_result["action"]="DELETE"
       delete_result["error_state"]=err

     deleted_results.append(delete_result)
 return deleted_results 

def init_worker(l):
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    global lock
    lock = l



def id_generator(size=6, chars=string.ascii_uppercase + string.digits):
      return ''.join(random.choice(chars) for _ in range(size))

def process_results(r):
  global mylock
  mylock.acquire()
  global results 
  results.append(r)
  mylock.release()


def abortable_worker(func,*args,**kwargs):
  timeout=kwargs.get("timeout",None)
  instance_id=kwargs.get("instance_id",None)
  instance_name=kwargs.get("instance_name",None)
  main_result=kwargs.get("result",None)
  timeout_results=[]
  timeout_results.append(main_result)
  p=ThreadPool(1)
  timeout_result=initResult()
  res=p.apply_async(func,args=args)
  try:
     out =res.get(timeout) #wait for function to complete
     return out   
  except (mp.TimeoutError,Exception) as e:
     print "Timeout"
     print e
     timeout_result["id"]=instance_id
     timeout_result["name"]=instance_name
     timeout_result["action"]="GET_STATUS"
     timeout_result["status"]="Timeout checking status after X secs"
     timeout_results.append(timeout_result)
     #process_results(timeout_results)
     print "terminating due to timeout"
     print timeout_results
     p.terminate()
     #print "Printing timeout result ********************"
     #print timeout_results
     return timeout_results

#deploy instance    
def nova_deploy_instance(session,image,flavor,nics,no_of_instance=999,clean_up=True):
  userInterrupted=False
  index=0
  nova =getNova(session)
  global TIMEOUT
  #l = mp.Lock()
  instance_count=0
  global spawned_instances
  global spawned_instance_ids

  manager=Manager()
  #global results
  instance_name="HIGHLANDER_"+id_generator()

  # pool=mp.Pool(initializer=initLock,initargs=(l,))
  l = Lock()
  pool=mp.Pool(processes=10, initializer=init_worker,initargs=(l,))
  print "Starting to deploy instance"
  spawned_instances={}
  spawned_instance_ids=[]
  while instance_count<=no_of_instance:

    try:
       # Starting nova instance
        instance_results=[]
        result=initResult()
        nova.reset_timings()     
        result["action"]="Create"
        result["invoked_time"]=str(datetime.datetime.now())
        print "Starting to deploy instance %s", instance_name +"_"+ str(instance_count)
      
        start_time=time.time() * 1000
        instance=None
        try:
           instance = nova.servers.create(name=instance_name +"_" + str(instance_count), image=image,
                 flavor=flavor,nics=nics)
        except KeyboardInterrupt:
           raise KeyboardInterrupt()
        except Exception as Err:
           print "Exception occured while deploying instance... looping back",Err
           continue

        instance_count=instance_count+1
        result["status_time_diff"]=(time.time() * 1000) - start_time
        instance_id=instance.id
        spawned_instances[instance_id]=instance_name  +"_" + str(instance_count)
        spawned_instance_ids.append(instance_id)
	result["time"]= getTimings(nova.get_timings())
        result['id']=instance_id
        result['name']=instance.name
        nova.reset_timings()
        # Poll at 2?? second intervals, until the status is no longer 'BUILD' or need to decide when to stop '' till it is running?
	status = instance.status
        result["status"]=status
        if status=="ERROR":
           result["error_state"]=instance.error 
           print "**************** UNKNOW ERROR ON CREATE ***********************"
           print result
           #print_result(instance_results)
           #exit(0) #do you wan to exit here or continue deploying next
        #results.append(result) 
        #exit(0)
        else:
          print "sending thread to check status..."
          copy_result=copy.deepcopy(result)
          abortable_func=partial(abortable_worker,checkstatus,result=copy_result,instance_name=(instance_name + str(instance_count)),instance_id=instance_id,timeout=TIMEOUT)
          #abortable_func(instance_id,status,copy_result)
          pool.apply_async(abortable_func ,args=( instance_id,status,copy_result,),callback=process_results)
          time.sleep(0.200)
    #if the status is Not Build, delete 
    except KeyboardInterrupt:
        userInterrupted=True
        print "*******************************"
        print "You EVIL bastard!"
        print "*******************************"   
        instance_count =no_of_instance+1
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
        #print "Exception occured %s",err
        result["error_state"]=err
        results.append(result)
     #print_result(results)
     #Delete instance and print
     #result=delete_instance(nova,instance_id)
     #results.append(result)
  if userInterrupted==False:
     time.sleep(5)
     pool.close()
     pool.join() 
  print "\nFinally, here are the results:"
 #print results
  print "spawned instances"
  for i in spawned_instances:
    print i
  print "******** printing results**************************"
  print results
  print_result(results)
  if clean_up==True:
      print "deleteing instances"
      delete_results=[]
      delete_results.append(delete_deployed_instances())
      print "***************delete results****"
      print delete_results
      print_result(delete_results)



#DELETE instance
# for  id in $(nova list | grep Highlander | awk '!/ID/ {print$2}');do openstack server delete $id;done

def delete_instance_wait(nova,instance_id):
  try:
    result=initResult()
    result["invoked_time"]=str(datetime.datetime.now())
    result["action"]="DELETE"
    nova.reset_timings()
    nova.servers.delete(instance_id)
    result["status"]="Deleteing"
    result["time"]= getTimings(nova.get_timings())
  except Exception as err:
    result["error_state"]=err
  return result

  


def get_fault(fault):
  if fault:
     return fault["message"]

def getTimings(timings):
   return_timings={}
   for data in timings:
       return_timings[data[0][:6]]={"Diff":data[2]-data[1]}
   return return_timings
   
def initResult():
    return {"id":'',"name":'',"action":'',"status":'',"time":'',"error_state":'',"invoked_time":'',"fault":'',"status_time_diff":0}


def print_result(results):
  print "Printing results"
  print results
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
  #try:
      #-1 for unlimted
      
      TIMEOUT=600
      session,image,flavor,nics=init()
      print session
      print image
      results=[]
      #999 for unlimited
      nova_deploy_instance(session,image,flavor,nics,5,False)
  #except Exception:
  #    exit(0)



