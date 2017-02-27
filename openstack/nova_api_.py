import os

from novaclient import client  as novaClient

def get_nova_creds():
    d = {}
    d['username'] = os.environ['OS_USERNAME']
    d['api_key'] = os.environ['OS_PASSWORD']
    d['auth_url'] = os.environ['OS_AUTH_URL']
    d['project_id'] = os.environ['OS_TENANT_NAME']
    return d

nova = novaClient.Client("2",timings=True,timeout=1,**get_nova_creds())
#Get token (optional, happens on its own if not specified)
nova.authenticate()
print nova.flavors.list()
