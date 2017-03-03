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
            if r!=None:  
              deployService=CheckInstances()
              deployService.print_result(r)
        except Exception as err:
           print "Error in process results", err 

#Initialize Results dictionary
def initResult():
        return {"id":'',"name":'',
                        "action":'',"status":'',"time":'',
                         "error_state":'',"invoked_time":'',
                "fault":'',"status_time_diff":0,"error_start":'',"error_end":'','error_diff':0}

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
    deployService=CheckInstances()
    start_time=time.time() * 1000
    status_results=[]
    nova=None
    #print "Checking status for "+instance_id
    #time.sleep(1)
    status_result=deployService.initResult()
    error_start_time=0
    error_flag=False
    # Retrieve the instance again so the status field updates
    while True:
      try:
        if nova==None:
             nova =deployService.getNova()
             time.sleep(1)
             continue
        nova.reset_timings()
        instance = nova.servers.get(instance_id)

        status_result["invoked_time"]=str(datetime.datetime.now())
        status=instance.status
        status_result["action"]="GET_STATUS"
        status_result["status"]=status
        status_result["time"] =  deployService.getTimings(nova.get_timings())
        status_result["error_state"]=""
        if  error_flag==True:
            return status_result
            break
      except KeyboardInterrupt:  
          raise KeyboardInterrupt
      except Exception as err:
          error_flag=True
          print err
          if  error_start_time==0: 
              error_start_time=time.time() * 1000
              status_result["error_start"]=str(datetime.datetime.now())

          status_result["error_end"]=str(datetime.datetime.now())
          status_result["error_diff"]=(time.time()*1000)- error_start_time
          print colored(str(datetime.datetime.now()),'red')
          #print "\n*****************************"
          nova =None
          status_result["error_state"]= "ERROR"

    status_result["status_time_diff"]=(time.time() * 1000) - start_time
    status_results.append(status_result)
    #print "Complete checking status for "+instance_id
    if error_flag==True:
        return status_results
    else:
        return None 

#Class to deploye instances
class CheckInstances():
     TIMEOUT=600 
     mylock=Lock()
     results=[]
   
   
    #session,image,flavor,nics,5,False
     def __init__(self):
         pass
        
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

     
     #Initialize worker
     def init_worker(self):
            signal.signal(signal.SIGINT, signal.SIG_IGN)


     
     def nova_check_instance_status(self,no_of_times=999,clean_up=True):

          userInterrupted=False
          index=0
          nova =self.getNova(session)
          instance_count=0
          manager=Manager()

          instance_list= nova.servers.list()
          if not instance_list:
              print "No instancwe to check status"
              exit(0)
          pool=mp.Pool(processes=10, initializer=self.init_worker,initargs=())
          print "Starting to  chceck status of the instance"
          error_start_time='' 
          error_end_time=''
          error_start_time_in_ms=0
          error_end_time_in_ms=0
         
          while instance_count<=no_of_times :
            try:
                for instance in instance_list:
                    #print "sending thread to check status..."
                    abortable_func=partial(
                                  abortable_worker,checkstatus,result=None,
                                  instance_name=instance.name,
                                  instance_id=instance.id,timeout=self.TIMEOUT)

                    pool.apply_async(abortable_func ,
                                     args=( instance.id,"ACTIVE",None,),
                                     callback=process_results)

                    time.sleep(0.200)
            except KeyboardInterrupt:
                userInterrupted=True
                print "*******************************"
                print colored("You EVIL bastard!",'red')
                print "*******************************"   
                instance_count =no_of_times+1
                print "Exiting........"
                time.sleep(5)
                pool.close()
                print "pool terminated... waiting to join"
                pool.join()
            except Exception as err:
                print "Error in main loop",err
          #End while loop 

          if userInterrupted==False:
             time.sleep(5)
             pool.close()
             pool.join() 
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
     def print_result(self,result):
         print "Printing results"
         print result
         table = PrettyTable(['id','name','action',
                              'status','time',
                              'Invoked_time','status_time_diff',"error_start","error_end",'error_diff'],
                               encoding="UTF-8")
         table.add_row([result['id'][:6],result['name'],
                                                          result["action"],result["status"],
                                                          result['time'], 
                                                          result['invoked_time'],
                                                          result['status_time_diff'],
                                                          result['error_start'],result['error_end'],result['error_diff']])

         print table
 
 
if __name__ == '__main__':
      deploy=CheckInstances() 
      #999 for unlimited
      no_of_timess=999
      deploy.init() 
      deploy.nova_check_instance_status(no_of_timess,False)



