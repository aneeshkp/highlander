# HIGHLANDER
**Server installation**

1. Install nodejs in controller
   * "curl --silent --location https://rpm.nodesource.com/setup_7.x | bash - 
   * yum install nodejs   
2. Check out this project on each controller
3. Edit haproxy.cfg and add following
   ```
   listen highlander
    bind 10.19.108.24:3333 transparent
    option  http-server-close
    option http-pretend-keepalive
    balance roundrobin
    mode http
    server overcloud-controller-0.internalapi.localdomain 172.17.0.14:3333 check
    server overcloud-controller-1.internalapi.localdomain 172.17.0.13:3333 check
    server overcloud-controller-2.internalapi.localdomain 172.17.0.20:3333 check
    ```

4. Edit server.js if ip address to bind is in different interface
    *var exec_out= exec("ip a show vlan1020 | grep  /24 | awk '{print $2}' | cut -d'/' -f1");*
5. Create higlander.service under /etc/systemd/system/highlander.service

     ```
      [Unit]
      Description=highlander
      [Service]
      ExecStart=/usr/bin/node /root/highlander/server.js
      Restart=always
      RestartSec=10                       # Restart service after 10 seconds if node service crashes
      StandardOutput=syslog               # Output to syslog
      StandardError=syslog                # Output to syslog
      SyslogIdentifier=nodejs-highlander-server
      Environment=NODE_ENV=production
      [Install]
      WantedBy=multi-user.target
      ```
6. Systemctl enable highlander.service & systemctl start highlander.service
7. pcs resource restart haproxy

**Client set up**

1. Checkout same project in jumpnode
2. Edit client.cfg to edit server HAProxy ip address
3. python wsclient.py
 
