# Copyright 2015 - Aneesh Puttur, Inc.
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
from termcolor import colored
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

#Process results 
def process_results(r):
        try:
          deployService=DeployInstances()
          deployService.process_instance_results(r)
        except Exception:
           print "Error in process results"     

#Initialize Results dictionary
def initResult():
        return {"id":'',"name":'',
                        "action":'',"status":'',"time":'',
                         "error_state":'',"invoked_time":'',
                "fault":'',"status_time_diff":0,"error_start":'',"error_end":'','error_dif':0}


#Wrapper for check status to monitor timeout 
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
        except mp.TimeoutError as e:
           print "Timeout"
        timeout_result["id"]=instance_id
        timeout_result["name"]=instance_name
        timeout_result["action"]="GET_STATUS"
        timeout_result["status"]="Timeout checking status after X secs"
        timeout_results.append(timeout_result)
        print "terminating due to timeout"
        print timeout_results
        p.terminate()
        return timeout_results

#method to check status of the instance
def checkstatus(instance_id,status,result):
    deployService=DeployInstances()
    start_time=time.time() * 1000
    status_results=[]
    status_results.append(result)
    nova=None
    print "Checking status for "+instance_id
    #time.sleep(1)
    status_result=deployService.initResult()
    error_start_time=0
    # Retrieve the instance again so the status field updates
    while status=='BUILD':
      try:
        if nova==None:
             nova =deployService.getNova()
             time.sleep(1)
             continue
        nova.reset_timings()
        instance = nova.servers.get(instance_id)
        if instance.status!=status:
             status_result["invoked_time"]=str(datetime.datetime.now())
             status=instance.status
             status_result["action"]="GET_STATUS"
             status_result["status"]=status
             if hasattr(instance,"fault"):
                 status_result["fault"]=deployService.get_fault(instance.fault)
             #end if  
             status_result["time"] =  deployService.getTimings(nova.get_timings())
             status_result["error_state"]=""
      except Exception as err:
          if  error_start_time==0: 
              error_start_time=time.time() * 1000
              status_result["error_start"]=str(datetime.datetime.now())

          status_result["error_end"]=str(datetime.datetime.now())
          status_result["error_diff"]=(time.time()*1000)- error_start_time
          print colored(str(datetime.datetime.now()),'red')
          #print "\n*****************************"
          print err
          nova =None
          status_result["error_state"]= "ERROR"

    status_result["status_time_diff"]=(time.time() * 1000) - start_time
    status_results.append(status_result)
    print "Complete checking status for "+instance_id
    print status_results
    return status_results

#Class to deploye instances
class DeployInstances():
     FLAVOR_NAME="cirros.1"
     NETWORK_NAME="default"
     IMAGE_NAME="cirros-0.3.4"
     TIMEOUT=600 
     mylock=Lock()
     results=[]
     spawned_instances={}
     spawned_instance_ids=[] 
   
   
    #session,image,flavor,nics,5,False
     def __init__(self):
        self._flavor=None
        self._image=None
        self._nics=None
        self._session=None
        
     #get credential information  for environment file
     def __get_nova_creds(self):
       d = {}
       d['username'] = os.environ['OS_USERNAME']
       d['api_key'] = os.environ['OS_PASSWORD']
       d['auth_url'] = os.environ['OS_AUTH_URL']
       d['project_id'] = os.environ['OS_TENANT_NAME']
       return d

     # Initlaize and check if images ,flavor and networks are avialble
     def init(self):


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
        self._session=keystone.session
        nova  = self.getNova(self._session)
        #nova = novaClient.Client("2", keystone.session,timings=True,timeout=1)
        self._flavor= nova.flavors.find(name=self.FLAVOR_NAME)
        if not self._flavor:
           raise Exception("Flavour Not found")
        #Get glance images
        glance =glanceClient.Client("1",session=self._session)
        self._image= glance.images.find(name=self.IMAGE_NAME)
        if not self._image:
          raise Exception("Image not found")

        #get neutron /netrowk info
        neutron=neutronClient.Client(session=self._session)

        networks= neutron.list_networks(name=self.NETWORK_NAME)
        if not networks:
            raise Exception("No default network found")

        self._nics = [{'net-id':networks['networks'][0]['id']}]
        self._session=keystone.session
    

    #get Nova object
     def getNova(self,session=None):
         try:
             if session==None:
                 return novaClient.Client("2",timings=True,timeout=600,**self.__get_nova_creds()) 
             else:
                 return  novaClient.Client("2",session=self._session,timings=True,timeout=600)
         except Exception as err:
                 print "Error returning nova object %s",err
     
         return None 

     #delete instances at the end, if the option is selected to clean up
     def delete_deployed_instances(self):
          nova=self.getNova()
          deleted_results=[]
          for instance_id in  self.spawned_instance_ids:
            try:
                delete_result=self.initResult()
                delete_result["id"]=instance_id
                delete_result["name"]=self.spawned_instances[instance_id]
                delete_result["invoked_time"]=str(datetime.datetime.now())
                delete_result["action"]="DELETE"
                nova.reset_timings()
                nova.servers.delete(instance_id)
                delete_result["status"]="Deleteing"
                delete_result["time"]=elf.getTimings(nova.get_timings())
            except Exception as err:
                delete_result["action"]="DELETE"
                delete_result["error_state"]=err

            deleted_results.append(delete_result)
            return deleted_results 
     
     #Initialize worker
     def init_worker(self):
            signal.signal(signal.SIGINT, signal.SIG_IGN)


     #Auto generate
     def id_generator(self,size=6, chars=string.ascii_uppercase + string.digits):
          return ''.join(random.choice(chars) for _ in range(size))
     
     #Process instance result in threaded fashion
     def process_instance_results(self,r):
           self.mylock.acquire()
           self.results.append(r)
           self.mylock.release()

        #deploy instance    
     def nova_deploy_instance(self,no_of_instance=999,clean_up=True):

          userInterrupted=False
          index=0
          nova =self.getNova(session)
          instance_count=0
          manager=Manager()

          instance_name="HIGHLANDER_"+self.id_generator()

          pool=mp.Pool(processes=10, initializer=self.init_worker,initargs=())
          print "Starting to deploy instance"
          error_start_time='' 
          error_end_time=''
          error_start_time_in_ms=0
          error_end_time_in_ms=0
          while instance_count<=no_of_instance:
            try:
               # Starting nova instance
                instance_results=[]
                result=self.initResult()
                result["error_start"]=error_start_time
                result["error_end"]=error_end_time
                nova.reset_timings()     
                result["action"]="Create"
                result["invoked_time"]=str(datetime.datetime.now())
                deployed_instance_name=instance_name +"_" + str(instance_count) 
                print "Starting to deploy "+ deployed_instance_name
                start_time=time.time() * 1000
                instance=None
                result["error_diff"]=error_end_time_in_ms-error_start_time_in_ms
              
                try:
                   instance = nova.servers.create(
                                                name=deployed_instance_name,
                                                image=self._image, flavor=self._flavor,nics=self._nics
                                                )
                   error_start_time=''
                   error_end_time=''
                   error_end_time_in_ms=0
                   error_start_time_in_ms=0

                except KeyboardInterrupt:
                   raise KeyboardInterrupt()
                except Exception as Err:
                   if error_start_time=='':
                       error_start_time_in_ms=time.time() * 1000
                       error_start_time=str(datetime.datetime.now())

                   error_end_time=str(datetime.datetime.now())    
                   error_end_time_in_ms=time.time()*100
                   print "\n************************************************"
                   print colored(str(datetime.date.now()),'red')
                   print "\n Exception occured while deploying instance... looping back"
                   print "\n-----------------------------------------------------\n"
                   continue

                instance_count=instance_count+1
                result["status_time_diff"]=(time.time() * 1000) - start_time
                instance_id=instance.id
                self.spawned_instances[instance_id]=deployed_instance_name
                self.spawned_instance_ids.append(instance_id)
            	result["time"]= self.getTimings(nova.get_timings())
                result['id']=instance_id
                result['name']=instance.name
                nova.reset_timings()
            	status = instance.status
                result["status"]=status
                if status=="ERROR":
                   result["error_state"]=instance.error 
                   print "**************** UNKNOW ERROR ON CREATE ***********************"
                   print result
                else:
                    print "sending thread to check status..."
                    copy_result=copy.deepcopy(result)
                    abortable_func=partial(
                                  abortable_worker,checkstatus,result=copy_result,
                                  instance_name=(instance_name + str(instance_count)),
                                  instance_id=instance_id,timeout=self.TIMEOUT)

                    pool.apply_async(abortable_func ,
                                     args=( instance_id,status,copy_result,),
                                     callback=process_results)

                    time.sleep(0.200)
            except KeyboardInterrupt:
                userInterrupted=True
                print "*******************************"
                print colored("You EVIL bastard!",'red')
                print "*******************************"   
                instance_count =no_of_instance+1
                print "Exiting........"
                time.sleep(5)
                pool.close()
                print "pool terminated... waiting to join"
                pool.join()
            except Exception as err:
                result["error_state"]=err
                self.results.append(result)
          #End while loop 

          if userInterrupted==False:
             time.sleep(5)
             pool.close()
             pool.join() 
          print "\nFinally, here are the results:"
          print "spawned instances"
          for i in self.spawned_instances:
            print i
          print "******** printing results**************************"
          print self.results
          self.print_result(self.results)
          if clean_up==True:
              print "deleteing instances"
              delete_results=[]
              delete_results.append(self.delete_deployed_instances())
              print "***************delete results****"
              print delete_results
              self.print_result(delete_results)

     
     #get fault in message
     def get_fault(self,fault):
        if fault:
           return fault["message"]
     #get timings details
     def getTimings(self,timings):
         return_timings={}
         for data in timings:
             return_timings[data[0][:6]]={"Diff":data[2]-data[1]}
         return return_timings
     
     #initialize result dict
     def initResult(self):
           return {"id":'',"name":'',
                   "action":'',"status":'',"time":'',
                   "error_state":'',"invoked_time":'',
                   "fault":'',"status_time_diff":0,"error_start":'',"error_end":'','error_diff':0}
    
     #print pretty table when the job is done
     def print_result(self,results):
         print "Printing results"
         print results
         table = PrettyTable(['id','name','action',
                              'status','time',
                              'Invoked_time','status_time_diff',"error_start","error_end",'error_diff'],
                               encoding="UTF-8")
         if any(isinstance(i, list) for i in results)==False:
             for result in results:
                 table.add_row([result['id'][:6],result['name'],
                                  result["action"],result["status"],
                                  result['time'], 
                                  result['invoked_time'],
                                  result['status_time_diff'],
                                  result['error_start'],result['error_end'],result['error_dif']])
         else:
             for result_1 in results:
                for result in result_1:
                   try:
                     
                     table.add_row([result['id'][:6],result['name'],
                                        result["action"],result["status"],
                                      result['time'],
                                      result['invoked_time'],result['status_time_diff'],
                                   result['error_start'],result['error_end'],result["error_diff"]])
                   except:
                    print "failed table"
                    print result_1
         print table
 
 
if __name__ == '__main__':
      deploy=DeployInstances() 
      #999 for unlimited
      no_of_instances=10
      deploy.init() 
      deploy.nova_deploy_instance(no_of_instances,False)



