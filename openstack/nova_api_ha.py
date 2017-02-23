#!/usr/bin/env python
import os
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

def nova_deploy_instace():

  service_types=[]
  service_status={}
  INITIAL_STATUS="UNKNOWN"
  service_url={}
  
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

  nova = novaClient.Client("2", session=keystone.session,timings=True,timeout=1)
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

   

  index=0
  while index==0:
    results=[] 
    try:
       # Starting nova instance
        result=initResult()
        nova.reset_timings()
        result["action"]="Create"
        result["invoked_time"]=str(datetime.datetime.now())
	instance = nova.servers.create(name="PUTTUR_IS_HERE", image=image,
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
           results.append(result) 
           print_result(results)
           exit(0)
        results.append(result) 
        #exit(0)
        #check status 
	while status == 'BUILD':
	    time.sleep(1)
            result=initResult() 
	    # Retrieve the instance again so the status field updates
            try:
                 nova.reset_timings()
		 instance = nova.servers.get(instance_id)
                 pprint(instance)
                 if instance.status!=status:
                    result["invoked_time"]=str(datetime.datetime.now())
                    status=instance.status
                    result["action"]="GET_STATUS"
                    result["status"]=status
                    result["fault"]=get_fault(instance.fault)
                    result["time"] =  getTimings(nova.get_timings())
                    results.append(result)
            except Exception as err:
                  result["error_state"]=err
                  results.append(result)
        
                 
    #if the status is Not Build, delete 
    except Exception as err:
      result["error_state"]=err
      results.append(result)
     #print_result(results)
 
   #Delete instance and print
    result=delete_instance(nova,instance_id)
    results.append(result)
   
    print_result(results)
    index=1



#DELETE instance
def delete_instance(nova,instance_id):
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
  table = PrettyTable(['id','name','action', 'status','time','error_state','Invoked_time','fault'])
  for result in results:
     table.add_row([result['id'],result['name'],result["action"],result["status"],result['time'], result["error_state"],result['invoked_time'],result['fault']])
  
  print table
 
 
if __name__ == '__main__':
   try:
      nova_deploy_instace()
   except KeyboardInterrupt:
      exit(0)


