#!/usr/bin/env python
import os
import time
import sys
from keystoneauth1  import session
from keystoneclient.v2_0 import client
from novaclient import client  as novaClient
from glanceclient import client as glanceClient
from neutronclient.v2_0 import client as neutronClient
from keystoneauth1.identity import v2

service_types=[]
service_status={}
INITIAL_STATUS="UNKNOWN"
results={}
service_url={}

FLAVOR_NAME="cirros.1"
NETWORK_NAME="default"
IMAGE_NAME="cirros-0.3.4"

#keystone = client.Client(username=os.environ['OS_USERNAME'],
#                             password=os.environ['OS_PASSWORD'],
#                             tenant_name=os.environ['OS_TENANT_NAME'],
#                             auth_url=os.environ['OS_AUTH_URL'])


print os.environ["OS_AUTH_URL"]
auth = v2.Password(auth_url=os.environ["OS_AUTH_URL"],
                    username=os.environ["OS_USERNAME"],
                    password=os.environ['OS_PASSWORD'],
                    tenant_name=os.environ['OS_TENANT_NAME']
                   )

sess = session.Session(auth=auth)

keystone=client.Client(session=sess,timeout=2)
print keystone.tenants.list()

nova = novaClient.Client("2", session=keystone.session,timeout=2)
flavor= nova.flavors.find(name=FLAVOR_NAME)
glance =glanceClient.Client("1",session=keystone.session)
image= glance.images.find(name=IMAGE_NAME)
print "inage_id=" + image.id
neutron=neutronClient.Client(session=keystone.session,timeout=2)
networks= neutron.list_networks(name=NETWORK_NAME)
nics = [{'net-id':networks['networks'][0]['id']}]
print "network_id" + networks['networks'][0]['id']

# Starting nova instance
instance = nova.servers.create(name="PUTTUR_IS_HERE", image=image,
                  flavor=flavor,nics=nics)

# Poll at 2?? second intervals, until the status is no longer 'BUILD' or need to decide when to stop '' till it is running?
status = instance.status
while status == 'BUILD':
    time.sleep(2)
    # Retrieve the instance again so the status field updates
    instance = nova.servers.get(instance.id)
    status = instance.status
    sys.stdout.write(status)
    sys.stdout.flush()
print "\nstatus: %s" % status



