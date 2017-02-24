#!/usr/bin/enlockv python
import os
import multiprocessing as mp
from multiprocessing import  Lock,Manager
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
def getNova(session):
    nova = None
    try:
       nova = novaClient.Client("2",session=session,timings=True,timeout=1)
    except Exception as err:
       print "Error returning nova object %s",err
     
    return nova 


#get status of the object 
def checkstatus( instance_id,status,results):
    nova =novaClient.Client("2",os.environ['OS_USERNAME'], os.environ['OS_PASSWORD'], "admin", os.environ["OS_AUTH_URL"], service_type="compute")
    print"Get Nova instancefor checking status"
    #nova=getNova(session)
    print "Checking status for "+instance_id
    def delete_instance(nova,instance_id):
          print  "Deleteing "+ instance_id
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

    while status == 'BUILD':
            time.sleep(1)
            result=initResult()
            # Retrieve the instance again so the status field updates
            try:
                 nova.reset_timings()
                 instance = nova.servers.get(instance_id)
                 if instance.status!=status:
                    result["invoked_time"]=str(datetime.datetime.now())
                    status=instance.status
                    result["action"]="GET_STATUS"
                    result["status"]=status
                    if hasattr(instance,"fault"):
                        result["fault"]=get_fault(instance.fault)
                    result["time"] =  getTimings(nova.get_timings())
                    results.append(result)
            except Exception as err:
                  result["CHECK_STATUS"]
                  result["error_state"]=err
                  results.append(result)
    print "Status check completed"
    #delete instance
    print  "Deleteing "+ instance_id
    try:
       result=initResult()
       result["invoked_time"]=str(datetime.datetime.now())
       result["action"]="DELETE"
       nova.reset_timings()
       nova.servers.delete(instance_id)
       result["status"]="Deleteing"
       result["time"]= getTimings(nova.get_timings())
    except Exception as err:
       result["action"]="DELETE"
       result["error_state"]=err
 
    results.append(result)
    return results    

def init_worker():
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def id_generator(size=6, chars=string.ascii_uppercase + string.digits):
      return ''.join(random.choice(chars) for _ in range(size))

#deploy instance    
def nova_deploy_instance(session,image,flavor,nics):
  index=0
  nova =getNova(session)
  l = mp.Lock()
  instance_count=0
  manager=Manager()
  results= [] 
  instance_name="HIGHLANDER_"+id_generator()

  def process_results(r):
     # global lock 
     # lock.acquire()
     for rr in r:
       print rr
       results.append(rr)
     # lock.release() 
      
  def initLock(l):
    global lock
    lock = l

  # pool=mp.Pool(initializer=initLock,initargs=(l,))
  pool=mp.Pool(10, init_worker)

  print "Starting to deploy instance"
  while index==0:
    instance_count=instance_count+1
    try:
       # Starting nova instance
        instance_results=[]
        result=initResult()
        nova.reset_timings()     
        result["action"]="Create"
        result["invoked_time"]=str(datetime.datetime.now())
        print "Starting to deploy instance %s", instance_name + str(instance_count)

	instance = nova.servers.create(name=instance_name + str(instance_count), image=image,
                 flavor=flavor,nics=nics)

        instance_id=instance.id
	result["time"]= getTimings(nova.get_timings())
        result['id']=instance_id
        result['name']=instance.name
        nova.reset_timings()
        # Poll at 2?? second intervals, until the status is no longer 'BUILD' or need to decide when to stop '' till it is running?
	status = instance.status
        result["status"]=status
        if status=="ERROR":
           result["error_state"]=instance.error 
           instance_results.append(result) 
           print_result(instance_results)
           exit(0) #do you wan to exit here or continue deploying next
        #results.append(result) 
        #exit(0)
        print "sending thread to check status..."
        copy_results=copy.deepcopy(instance_results)
        pool.apply_async(checkstatus ,args=( instance_id,status,instance_results,),callback=process_results)
        time.sleep(0.200)
    #if the status is Not Build, delete 
    except KeyboardInterrupt:
         print "*******************************"
         print "You EVIL bastard!"
         print "*******************************"   
         index=1
         print "Exiting........"
         # pool.close
         #pool.terminate()
         print "pool terminated... waiting to join"
         #pool.join()
         print "printing results"
         #print_result(results)
         #time.sleep(5)
         #exit(1)
    except Exception as err:
      print "Exception occured %s",err
      result["error_state"]=err
      results.append(result)
     #print_result(results)
     #Delete instance and print
     #result=delete_instance(nova,instance_id)
     #results.append(result)

  pool.close()
  pool.join() 
  print "\nFinally, here are the results:"
  print_result(results)
#    index=1



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
    return {"id":'',"name":'',"action":'',"status":'',"time":'',"error_state":'',"invoked_time":'',"fault":''}


def print_result(results):
  print "Printing results"
  print results
  table = PrettyTable(['id','name','action', 'status','time','error_state','Invoked_time','fault'],encoding="UTF-8")
  for result in results:
     table.add_row([result['id'],result['name'],result["action"],result["status"],result['time'], result["error_state"],result['invoked_time'],result['fault']])
  
  print table
 
 
if __name__ == '__main__':
   try:
      nova =novaClient.Client("2",os.environ['OS_USERNAME'], os.environ['OS_PASSWORD'], "admin", os.environ["OS_AUTH_URL"], service_type="compute")
      session,image,flavor,nics=init()
      print session
      print image
      nova_deploy_instance(session,image,flavor,nics)
   except KeyboardInterrupt:
      exit(0)


