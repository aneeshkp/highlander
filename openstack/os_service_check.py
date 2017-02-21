from keystoneclient.v2_0 import client
import requests
import os
import eventlet
import datetime
import time
from time import sleep
from prettytable import PrettyTable
def check_keystone():
    allowed_values=['identity','volume','image','glance','compute','neutron','network']
    internal_url={}
    admin_url={}
    service_types=[]
    service_status={}
    results={} 
    keystone = client.Client(username=os.environ['OS_USERNAME'],
                             password=os.environ['OS_PASSWORD'],
                             tenant_name=os.environ['OS_TENANT_NAME'],
                             auth_url=os.environ['OS_AUTH_URL'])

    for service in keystone.auth_ref['serviceCatalog']:
        print service['type']
        if service['type'] in allowed_values:
            service_types.append(service["type"])
            service_status[service["type"]]="UNKNOW"
            results[service["type"]]={}
            internal_url[service['type']] = service['endpoints'][0]['internalURL']
            admin_url[service['type']] = service['endpoints'][0]['adminURL']
    
    

    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-Auth-Token': keystone.auth_ref['token']['id'],
    }

    if service_types:
        print "----------------------------------------"
    try:
       status_changed=True
       while True:
            table = PrettyTable(['Service', 'staus','e-time','reason','last_s_time','last_status'])
       	    for service_type in service_types:
                result={} 
       	        with eventlet.Timeout(1):
   	     	 response= requests.get(admin_url[service_type])
                 if service_status[service_type]!=response.status_code:
                    service_status[service_type]=response.status_code
                    status_changed=True
                    result["service_name"]=service_type
                    result["status"]=response.status_code
                    result["elapsed_time"]=response.elapsed.total_seconds()
                    result["reason"]=response.reason
                    if not results[service_type]:
                         result["last_success_time"]=str(datetime.datetime.now()) 
                         result["last_status"]="UNKNOW"
                    else:
                        result["last_success_time"]=results[service_type].last_success_time
                        result["last_status"]=results[service_type].last_status
                    table.add_row([result["service_name"],result["status"], result["elapsed_time"],result["reason"],result["last_success_time"],result["last_status"]])
                    results[service_type]=result
                 else:
                    result=results[service_type]
                    table.add_row([result["service_name"],result["status"], result["elapsed_time"],result["reason"],result["last_success_time"],result["last_status"]])
                    

            if status_changed:
                 print table
                 status_changed=False
	    sleep(0.10)
    except KeyboardInterrupt:
	 sleep(5)
	 print 'interrupted!'
                      
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



def main():
   # args = get_args()
    check_keystone()


if __name__ == '__main__':
    main()

