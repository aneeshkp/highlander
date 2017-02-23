from keystoneclient.v2_0 import client
import requests
import os


def getServiceEndpoints():
    allowed_values=['identity','volume','image','compute','neutron','network']
    keystone = client.Client(username=os.environ['OS_USERNAME'],
                             password=os.environ['OS_PASSWORD'],
                             tenant_name=os.environ['OS_TENANT_NAME'],
                             auth_url=os.environ['OS_AUTH_URL'])

    for service in keystone.auth_ref['serviceCatalog']:
        print service['type']
        base_url = service['endpoints'][0]['internalURL']
        admin_url = service['endpoints'][0]['adminURL']
        public_url = service['endpoints'][0]['publicURL']

        print base_url
        print admin_url
        print public_url




def main():
   # args = get_args()
    getServiceEndpoints()


if __name__ == '__main__':
    main()

