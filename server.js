/*
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
*/

var server =require("websocket").server
var http = require('http');
var exec =require('child_process').exec;
var os= require('os')
var ip_address=0;
var socket;
var action_type;
var exec_out= exec("ip a show eth1 | grep  /24 | awk '{print $2}' | cut -d'/' -f1");
exec_out.stdout.on('data',function(data){
   ip_address=data;
   host_name=os.hostname();
   console.log(ip_address);
   console.log(host_name);
function wait(){
}
  socket=new server({
      httpServer:http.createServer(function(request,response){
     }).listen(3335,function(){console.log("[1]Server is listening for heart beat at 3333")})
  });


    
    socket.on('request',function(request){
      console.log("incomming connect");
      var connection=request.accept(null,request.origin);
      console.log("socket connection accepted");
      action_type= request.resourceURL['pathname'];

      connection.on('message',function(message){
              r_time = new Date().getTime();
              try{
	              var json_object = JSON.parse(message.utf8Data);
        	      //first message handshake
        	      json_object.hostname = host_name;
	              json_object.s_time_r=r_time;
	              json_object.s_time_s=new Date().getTime();
        	      var parseddata= JSON.stringify(json_object);
                       if( action_type=='/ping'){
                          connection.sendUTF(parseddata);
                          
                       }else{
                            var i=0;
        	            var id = setInterval(function() {
                                 i=i+1;  
                                 json_object.no=i;   
                	         json_object.s_time_s=new Date().getTime();
                        	         connection.sendUTF(JSON.stringify(json_object))
	                          }, 0.01);
                        }


	
           }catch(e){
           console.log("Handshake won't be sent due to error")
           }

        });
	});


});


