#!/usr/bin/python

import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish
from django import template
import django.template.loader
from django.conf import settings
import os, sys, time
#import logging
import datetime
from django.utils import timezone
import json
import smtplib
#from email.MIMEMultipart import MIMEMultipart
from email.mime.text import MIMEText

sys.path.append("/code/home")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "home.settings")
django.setup()
from monitor.models import Node, Setting

cClient_ID = os.getenv('MQTT_CLIENT_ID', 'mqtt_monitor')
print("MQTT client id is {}".format(cClient_ID))
#The mqtt client is initialised
client = mqtt.Client(client_id='mqtt_monitor-d')

# ********************************************************************
def mqtt_on_connect(client, userdata, flags, rc):
    """
      This procedure is called on connection to the mqtt broker
    """
    print("mqtt conn entered")
    client.subscribe("house/#")
    print("Subscribed to house")
    return
    

#********************************************************************
def mqtt_on_message(client, userdata, msg):
  """This procedure is called each time a mqtt message is received"""
  #print(msg.topic)
  sPayload = msg.payload.decode()
  jPayload = json.loads(msg.payload)
  #print(jPayload)
  cTopic = msg.topic.split("/")
  cNodeID = cTopic[1]
  try:
    nd, created = Node.objects.get_or_create(nodeID = cNodeID)
    if sPayload == "Offline":
      nd.textSstatus = sPayload
      nd.status = "X"
    else:
      
      if nd.status == "X":
        node_back_online(nd)
      nd.lastseen = timezone.make_aware(datetime.datetime.now(), timezone.get_current_timezone())
      nd.textSstatus = "Online"
      nd.status = "C"
    nd.lastData = sPayload
    if nd.battName:
      #print("Battery name is {}".format(nd.battName))
      if nd.battName in jPayload:
        nd.battLevel = jPayload[nd.battName]
        nd.battMonitor = True
    if "RSSI" in jPayload:
      nd.RSSI = jPayload["RSSI"]
    nd.save()
  except Exception as e:
    print(e)
  if created:
    print("Node {} has been created".format(nd.nodeID))
  else:
    print("Node {} has been updated".format(nd.nodeID))


#******************************************************************
def node_back_online(node):
  """
  Procedure run when a node is seen to be back on line
  """
  node.notification_sent = False
  node.status = 'C'
  node.textStatus = "Online"
  node.save()
  return

#******************************************************************
def missing_node(node):
  """
  Procedure run when a node has not been seen for a while
  """
  if node.status == 'C':
    node.textStatus = "Missing"
    node.status = "X"
    node.notification_sent = True
    node.status_sent = timezone.make_aware(datetime.datetime.now(), timezone.get_current_timezone())
    node.save()
    cDict = {'node': node}
    sendNotifyEmail("Node down notification for {}".format(node.nodeID), cDict, "monitor/email-down.html")
    print("Node {} marked as down and notification sent".format(node.nodeID))
  return

# ******************************************************************************
def sendNotifyEmail(inSubject, inDataDict, inTemplate):
    """A function to send email notification
    """
    try:
     
      email_server = smtplib.SMTP_SSL(Setting.objects.get(sKey="smtpserver").sValue, 465)
      email_server.login(Setting.objects.get(sKey="email_acct").sValue, Setting.objects.get(sKey="email_passwd").sValue)
     
      t = template.loader.get_template(inTemplate)
      body = t.render(inDataDict)
      
      msg = MIMEText(body, 'html') 
      msg['From'] = Setting.objects.get(sKey="email_from_addr").sValue
      msg['To'] = Setting.objects.get(sKey="email_notify").sValue
      msg['Subject'] = inSubject
      
      email_server.sendmail(Setting.objects.get(sKey="email_from_addr").sValue, Setting.objects.get(sKey="email_notify").sValue, msg.as_string())
      email_server.close()
    except Exception as e:
        print(e)
        print("Houston, we have an email error {}".format(e))
        #logging.error("SMTP error {}".format(e))        
       
    return


#******************************************************************
def mqtt_monitor():
    """ The main program that sends updates to the MQTT system
    """
       
    #functions called by mqtt client
    client.on_connect = mqtt_on_connect
    client.on_message = mqtt_on_message
    
    # set up the local MQTT environment
    #client.username_pw_set(config["General"]["mqttuser"],
    #      config["General"]["mqttpw"])
    client.connect("192.168.1.93")

    # used to manage mqtt subscriptions
    client.loop_start()

    #initialise the checkpoint timer
    checkTimer = timezone.now()

    aNode = Node.objects.get(pk=10)
    cDict = {'node': aNode}
    sendNotifyEmail("Test email", cDict, "monitor/email-info.html")

    while True:
      time.sleep(1)

      # this section runs regularly (every 15 sec) and does a number of functions
      if (timezone.now() - checkTimer) > datetime.timedelta(0,15):  #second value is seconds to pause between....
        # update the checkpoint timer
        checkTimer = timezone.now()                                 #reset timer
        
        print("Timer check")

        allNodes = Node.objects.all()

        for n in allNodes:
            #if nothing then our 'patience' will run out
            if (timezone.now() - n.lastseen) > datetime.timedelta(minutes=n.allowedDowntime):
                print("Node {} not seen for over {} minutes".format(n, n.allowedDowntime))
                missing_node(n)
               


#********************************************************************
if __name__ == "__main__":
    mqtt_monitor()
