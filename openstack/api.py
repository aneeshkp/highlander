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


from keystoneclient.v2_0 import client
import requests
import os


def check_keystone():
    keystone = client.Client(username=os.environ['OS_USERNAME'],
                             password=os.environ['OS_PASSWORD'],
                             tenant_name=os.environ['OS_TENANT_NAME'],
                             auth_url=os.environ['OS_AUTH_URL'])

    for service in keystone.auth_ref['serviceCatalog']:
        print service['type']
        if service['type'] == 'identity':
            base_url = service['endpoints'][0]['internalURL']
            admin_url = service['endpoints'][0]['adminURL']
            break
    print base_url
    #url = '%s/tenants' % base_url.replace('/v2/', '/v2.1/')
    url = '%s/tenants' %admin_url 
    print url
    #data = {
    #    'forced_down': force_down,
    #    'binary': 'nova-compute',
    #    'host': hostname,
    #}
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-Auth-Token': keystone.auth_ref['token']['id'],
    }

   # print requests.put(url, data=json.dumps(data), headers=headers)

    print requests.get(url,headers=headers)



def main():
   # args = get_args()
    check_keystone()


if __name__ == '__main__':
    main()

