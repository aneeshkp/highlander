from keystoneclient.v2_0 import client
import requests
import os


def check_keystone():
    allowed_values=['identity','volume','image''glance','compute','neutron','network']
    internal_url={}
    admin_url={}
    service_types=[]
    keystone = client.Client(username=os.environ['OS_USERNAME'],
                             password=os.environ['OS_PASSWORD'],
                             tenant_name=os.environ['OS_TENANT_NAME'],
                             auth_url=os.environ['OS_AUTH_URL'])

    for service in keystone.auth_ref['serviceCatalog']:
        print service['type']
        if service['type'] in allowed_values:
            service_types.append(service["type"])
            internal_url[service['type']] = service['endpoints'][0]['internalURL']
            admin_url[service['type']] = service['endpoints'][0]['adminURL']
    
    

    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-Auth-Token': keystone.auth_ref['token']['id'],
    }

    if service_types:
	    print "----------------------------------------"
            for service_type in service_types:
                print service_type
                print "----------------------------------------"
                print admin_url[service_type]
	        print requests.get(admin_url[service_type])
                print requests.get(admin_url[service_type]).elapsed.total_seconds()
                print "----------------------------------------"
      
       

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

