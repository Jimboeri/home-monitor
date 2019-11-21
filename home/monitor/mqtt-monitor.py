#!/usr/bin/python

import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish
from django import template
import django.template.loader
from django.conf import settings
import os, sys, time
import pickle
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

eMqtt_client_id = os.getenv("HOME_MQTT_CLIENT_ID", "mqtt_monitor")
eMqtt_host = os.getenv("HOME_MQTT_HOST", "192.168.3.93")
eMqtt_port = os.getenv("HOME_MQTT_PORT", "1883")
eMqtt_user = os.getenv("HOME_MQTT_USER", "")
eMqtt_password = os.getenv("HOME_MQTT_PASSWORD", "")
eMail_From = os.getenv("HOME_MAIL_FROM", "auto@west.net.nz")
eMail_To = os.getenv("HOME_MAIL_To", "jim@west.kiwi")
eMail_Server = os.getenv("HOME_MAIL_SERVER", "smtp.gmail.com")
eMail_Acct = os.getenv("HOME_MAIL_ACCT", "auto@west.net.nz")
eMail_Password = os.getenv("HOME_MAIL_PASSWORD", "")

eWeb_Base_URL = os.getenv("HOME_WEB_BASE_URL", "http://192.168.3.3:8000/")

#eMqtt_client_id = os.getenv('MQTT_CLIENT_ID', 'mqtt_monitor')
print("MQTT client id is {}".format(eMqtt_client_id))
#The mqtt client is initialised
client = mqtt.Client(client_id=eMqtt_client_id)

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
  
  sPayload = msg.payload.decode()
  jPayload = json.loads(msg.payload)
  #print(msg.topic)
  #print(jPayload)
  cTopic = msg.topic.split("/")
  cNodeID = cTopic[1]
  print(cNodeID)
  try:
    nd, created = Node.objects.get_or_create(nodeID = cNodeID)
    if nd.status != "M":
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
        if nd.battLevel > nd.battWarn:
          nd.battStatus = "G"
        elif nd.battLevel > nd.battCritical:
          nd.battStatus = "W"
        else:
          nd.battStatus = "C"
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
    cDict = {'node': node, 'base_url': eWeb_Base_URL}
    sendNotifyEmail("Node down notification for {}".format(node.nodeID), cDict, "monitor/email-down.html")
    print("Node {} marked as down and notification sent".format(node.nodeID))
  return

# ******************************************************************************
def sendNotifyEmail(inSubject, inDataDict, inTemplate):
    """A function to send email notification
    """
    try:
     
      email_server = smtplib.SMTP_SSL(eMail_Server, 465)
      email_server.login(eMail_Acct, eMail_Password)
     
      t = template.loader.get_template(inTemplate)
      body = t.render(inDataDict)
    
      msg = MIMEText(body, 'html') 
      msg['From'] = eMail_From
  
      msg['To'] = eMail_To
      msg['Subject'] = inSubject
      
      email_server.sendmail(eMail_From, eMail_To, msg.as_string())
      email_server.close()
    except Exception as e:
        print(e)
        print("Houston, we have an email error {}".format(e))
        #logging.error("SMTP error {}".format(e))        
       
    return

# ******************************************************************************
def sendReport():
  """
  Function collates data and sends a full system report
  """
  print("Send full report")
  allNodes = Node.objects.all()
  batWarnList = []
  batCritList=[]
  nodeOKList = []
  nodeDownList = []
  for a in allNodes:
    if a.status == 'C':
      if a.battName == None:
        nodeOKList.append(a)
      else:
        if a.battLevel > a.battWarn:
          nodeOKList.append(a)
        elif a.battLevel > a.battCritical:
          batWarnList.append(a)
        else:
          batCritList.append(a)
    elif a.status == 'X':
      nodeDownList.append(a)
  cDict = {'nodes': allNodes, 'nodeOK': nodeOKList, 'nodeWarn': batWarnList,
      'nodeCrit': batCritList, 'nodeDown': nodeDownList,
      'base_url': eWeb_Base_URL}
  sendNotifyEmail("Home IoT report", cDict, "monitor/email-full.html")
  print("Sent Daily email")
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
    client.connect(eMqtt_host)

    # used to manage mqtt subscriptions
    client.loop_start()

    #initialise the checkpoint timer
    checkTimer = timezone.now()

    #aNode = Node.objects.get(pk=10)
    #cDict = {'node': aNode}
    #sendNotifyEmail("Test email", cDict, "monitor/email-down.html")
    #print("Sent test email")

    notification_data = {"LastSummary": datetime.datetime.now() + datetime.timedelta(days = -3)}

    startTime = timezone.now()

    #get any pickled notification data
    try:
        notificationPfile = open("notify.pkl", 'rb')
        notification_data = pickle.load(notificationPfile)
        print("Pickled notification read")
        notificationPfile.close()
    except:
        print("Notification pickle file not found")
        notification_data = {"LastSummary": datetime.datetime.now() + datetime.timedelta(days = -3)}

    #sendReport()

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
            
        if (timezone.now() - startTime) > datetime.timedelta(hours=1):    # this section is ony run if the script has been running for an hour
          if (timezone.now().hour > 7):                                   # run at certain time of the day
            xx = 1
            #print("Check 1 {}".format(notification_data["LastSummary"]))
            if notification_data["LastSummary"].day != datetime.datetime.now().day:
              print("Send 8am messages")
              sendReport()
              #update out notification data and save
              notification_data["LastSummary"] = datetime.datetime.now()
              #write a pickle containing current notification data
              try:
                  notificationPfile = open("notify.pkl", 'wb')
                  pickle.dump(notification_data, notificationPfile)
                  notificationPfile.close()
              except:
                  print("Notification Pickle failed")
              
 

#********************************************************************
if __name__ == "__main__":
    mqtt_monitor()
