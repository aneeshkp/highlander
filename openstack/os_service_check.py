# Copyright 2015 -  Aneesh Puttur, Inc.
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

from keystoneclient.v2_0 import client
import requests
import os
import eventlet
import datetime
import time
from time import sleep
from prettytable import PrettyTable
import sys
import re
import json
from requests.models import Response
def check_keystone():
    connection_timeout=2
    INITIAL_STATUS = "UNKNOWN"
    allowed_values={'identity':'tenants','volume':'types','volumev2':'backups/detail','volumev3':'backups/detail','image':'v2/images','glance':'','compute':'servers','neutron':'','network':'v2.0/networks','orchestration': 'stacks'}


    internal_url={}
    service_url={}
    service_types=[]
    service_status={}
    results={} 
    keystone = client.Client(username=os.environ['OS_USERNAME'],
                             password=os.environ['OS_PASSWORD'],
                             tenant_name=os.environ['OS_TENANT_NAME'],
                             auth_url=os.environ['OS_AUTH_URL'])

    for service in keystone.auth_ref['serviceCatalog']:
        if service['type'] in allowed_values:
            service_type=service['type'].strip()
            service_types.append(service["type"])
            service_status[service["type"]]=INITIAL_STATUS
            results[service["type"]]={}
            clean_public_url=service['endpoints'][0]['publicURL']
            try:
               #clean_public_url= re.search(r'(.*)/v(.*)',clean_public_url).group(1)
               pass
            except: 
               pass


            if allowed_values[service_type]!='':
                 clean_public_url=clean_public_url+ "/"+ allowed_values[service_type]

            
            service_url[service['type']]={"internal_url": service['endpoints'][0]['internalURL'],"admin_url": service['endpoints'][0]['adminURL'],"public_url": service['endpoints'][0]['publicURL'],"clean_url":clean_public_url}

            #print service_url[service['type']]["clean_url"]


    headers = {
         'Content-Type': 'application/json',
         'Accept': 'application/json',
         'X-Auth-Token': keystone.auth_ref['token']['id'],
    }

   # if service_types:
   #     print "----------------------------------------"
    try:
       status_changed=True
       while True:
            table = PrettyTable(['Service', 'staus','e-time','reason','last_s_time','current_time','status_diff(in ms)','last_status','url'])
       	    for service_type in service_types:
                result={} 
                current_time=time.time() * 1000
       	        with eventlet.Timeout(1):                   
                     try:  
        	       response= requests.get(service_url[service_type]["clean_url"],headers=headers,timeout=connection_timeout, verify=False )
                     except:
                       response = Response()
                       response.status_code=501
                       response.reason="Connection Error" 
                       result["elapsed_time"]=(time.time() * 1000)- current_time

           
 
                if service_status[service_type]!=response.status_code:
                   current_time=time.time() * 1000
                   service_status[service_type]=response.status_code
                   if response.status_code==300:
                      service_url[service_type]["clean_url"]= process_multiplechoice(response.content)
                   status_changed=True
                   result["service_name"]=service_type
                   result["status"]=response.status_code
                   if response.status_code!=501: 
                      result["elapsed_time"]=response.elapsed.total_seconds()
                   result["reason"]=response.reason
                   result["current_time"]=str(datetime.datetime.now())
                   result["last_time_in_ms"]=last_time=time.time() * 1000
                   #print response.headers
                   if not results[service_type]:
                       result["last_success_time"]=str(datetime.datetime.now()) 
                       result["last_status"]=INITIAL_STATUS
                       result["diff"]=0.00 
                   else:
                       result["last_success_time"]=results[service_type]["last_success_time"]
                       result["last_status"]=results[service_type]["status"]
                       result["diff"]=current_time - results[service_type]["last_time_in_ms"]
                   result["url"]=response.url
                   table.add_row([result["service_name"],result["status"], result["elapsed_time"],result["reason"],result["last_success_time"],result["current_time"],result["diff"],result["last_status"],result['url']])
                   results[service_type]=result
                else:
                   result=results[service_type]
                   table.add_row([result["service_name"],result["status"], result["elapsed_time"],result["reason"],result["last_success_time"],result["current_time"],result["diff"],result["last_status"],result['url']])
                    

            if status_changed:
                 print "\n"
                 print table
                 print "\n"
                 status_changed=False
            else:   
                sys.stdout.write(".")
                sys.stdout.flush()
 
	    sleep(0.10)
    except KeyboardInterrupt:
	 sleep(5)
	 print 'interrupted!'
         exit(1) 
                      
                #print"Internal URL==> "+  internal_url[service_type]
               # response= requests.get(internal_url[service_type])
               # print response.content
               # print response.elapsed.total_seconds()
               # print response.reason
               # print response.status_code
               # print response.url
               # print"Internal URL==> "+  internal_url[service_type]

                 #  print requests.get(internal_url[service_type]).elapsed.total_seconds()
                #print "----------------------------------------"
      
       

    #print base_url
    #url = '%s/tenants' % base_url.replace('/v2/', '/v2.1/')
    # url = '%s/tenants' %admin_url 
    #data = {
    #    'forced_down': force_down,
    #    'binary': 'nova-compute',
    #    'host': hostname,
    #}

   # print requests.put(url, data=json.dumps(data), headers=headers)

    #print requests.get(url,headers=headers)

def process_multiplechoice(content):
   #print content
   url="no url"
   jcontent=json.loads(content)
   if "values" in content:
       for status in  jcontent["versions"]["values"]:
          if status["status"]=="stable":
             for urls in status["links"]:
                if urls["rel"]=="self":
                   url=urls["href"]
                   break
   else:
      for status in jcontent["versions"]:
         if status["status"]=="CURRENT":
            for urls in status["links"]:
                if urls["rel"]=="self":   
                   url=urls["href"]
                   break
   return url 

 
def main():
   # args = get_args()
    check_keystone()


if __name__ == '__main__':
   try: 
      main()
   except KeyboardInterrupt:
      exit(0) 

