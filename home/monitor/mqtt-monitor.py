#!/usr/bin/python

import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish
from django import template
import django.template.loader
from django.conf import settings
import os, sys, time
import pickle

# import logging
import datetime
from django.utils import timezone
import json
import smtplib

# from email.MIMEMultipart import MIMEMultipart
from email.mime.text import MIMEText

sys.path.append("/code/home")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "home.settings")
django.setup()
from monitor.models import Node, Setting, HassDomain, Entity

eMqtt_client_id = os.getenv("HOME_MQTT_CLIENT_ID", "mqtt_monitor")
eMqtt_host = os.getenv("HOME_MQTT_HOST", "mqtt.west.net.nz")
eMqtt_port = os.getenv("HOME_MQTT_PORT", "1883")
eMqtt_user = os.getenv("HOME_MQTT_USER", "")
eMqtt_password = os.getenv("HOME_MQTT_PASSWORD", "")
eMail_From = os.getenv("HOME_MAIL_FROM", "auto@west.net.nz")
eMail_To = os.getenv("HOME_MAIL_To", "jim@west.kiwi")
eMail_Server = os.getenv("HOME_MAIL_SERVER", "smtp.gmail.com")
eMail_Acct = os.getenv("HOME_MAIL_ACCT", "auto@west.net.nz")
eMail_Password = os.getenv("HOME_MAIL_PASSWORD", "")

eWeb_Base_URL = os.getenv("HOME_WEB_BASE_URL", "http://monitor.west.net.nz")

# eMqtt_client_id = os.getenv('MQTT_CLIENT_ID', 'mqtt_monitor')
print("MQTT client id is {}".format(eMqtt_client_id))
# The mqtt client is initialised
# client = mqtt.Client(client_id=eMqtt_client_id)
client = mqtt.Client()

# ********************************************************************
def is_json(myjson):
    """
    Function to check if an input is a valid JSON message
    """
    try:
        json_object = json.loads(myjson)
    except ValueError as e:
        return False
    return True


# ********************************************************************
def mqtt_on_connect(client, userdata, flags, rc):
    """
      This procedure is called on connection to the mqtt broker
    """
    Topics = ["house", "zigbee2mqtt", "shellies", "homeassistant"]

    print("MQTT conn entered")
    for topic in Topics:
        cTop = topic + "/#"
        client.subscribe(cTop)
        print(f"Subscribed to {cTop}")
    
    print("MQTTConn finished")
    return


# ********************************************************************
def mqtt_on_message(client, userdata, msg):
    """This procedure is called each time a mqtt message is received"""

    sPayload = msg.payload.decode()
    
    cTopic = msg.topic.split("/")
    #print(cTopic)

    # Processing varies depending on the topic

    if cTopic[0] == "homeassistant":    # This is a topic used for zigbee2mqtt discovery messages
        hassDiscovery(client, userdata, msg)
        return  
    
    if cTopic[0] == "tasmota":    # This is a topic used for Tasmota discovery messages
        tasmotaDiscovery(client, userdata, msg)
        return

    if cTopic[0] == "zigbee2mqtt":    # This is a topic used for zigbee2mqtt Data messages
        zigbee2mqttData(client, userdata, msg)
        return

    if cTopic[0] == "shellies":    # This is a topic used for shellies discovery & data messages
        shellies(client, userdata, msg)
        return

    jPayload = {}
    if is_json(sPayload):
        jPayload = json.loads(sPayload)
        #print(f"on_msg, JSON check: Input: {sPayload}, output: {jPayload}, passed as valid")


    cNodeID = cTopic[1]
    print(f"NodeID: {cNodeID}")
    #print(f"JSON Payload is {jPayload}")
    
    try:
        nd, created = Node.objects.get_or_create(nodeID=cNodeID)
    except Exception as e:
        print(e)
        return

    if nd.status != "M":
        if sPayload == "Offline":
            nd.textSstatus = sPayload
            nd.status = "X"
        else:
            if nd.status == "X":
                node_back_online(nd)
    nd.lastseen = timezone.now()
    nd.textSstatus = "Online"
    nd.status = "C"
    nd.lastData = sPayload.replace('","', '", "')
    if nd.battName:
        print("Battery name is {}".format(nd.battName))
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
        print(f"RSSI: {jPayload}")
        nd.RSSI = float(jPayload["RSSI"])

    nd.save()

    if created:
        print("Node {} has been created".format(nd.nodeID))
    else:
        print("Node {} has been updated".format(nd.nodeID))

# ********************************************************************
def hassDiscovery(client, userdata, msg):
    """
    """
    
    sPayload = msg.payload.decode()
    print(f"Process Home assistant discovery, topic: {msg.topic}, payload: {sPayload}")
    cTopic = msg.topic.split("/")
    if len(cTopic) < 3:
        print(f"Homeassistant error in discovery topic: {msg.topic}")
        return
    try:
        domain, created = HassDomain.objects.get_or_create(name=cTopic[1])
    except Exception as e:
        print(e)
        return

    if is_json(sPayload):
        jPayload = json.loads(sPayload)
        if "device" in jPayload:
            if "name" in jPayload["device"]:
                cNode = jPayload["device"]["name"]
                node, created = Node.objects.get_or_create(nodeID = cNode)

                if "model" in jPayload["device"]:
                    node.model= jPayload["device"]["model"]

                node.save()

                if "unique_id" in jPayload:
                    entity, eCreated = Entity.objects.get_or_create(entityID = jPayload["unique_id"], node = node, domain = domain)

                    if "state_topic" in jPayload:
                        entity.state_topic = jPayload["state_topic"]
                    if "availability_topic" in jPayload:
                        entity.availability_topic = jPayload["availability_topic"]
                    entity.save()

    return

# ********************************************************************
def tasmotaDiscovery(client, userdata, msg):
    """
    """
    return

# ********************************************************************
def zigbee2mqttData(client, userdata, msg):
    """
    """
    sPayload = msg.payload.decode()
    
    cTopic = msg.topic.split("/")
    cNode = cTopic[1]

    node, created = Node.objects.get_or_create(nodeID = cNode)
    node.lastData = sPayload
    node.lastseen = timezone.now()

    if is_json(sPayload):
        jPayload = json.loads(sPayload)
        if "battery" in jPayload:
            node.battLevel = jPayload["battery"]
            node.battWarn = 60
            node.battCritical = 50
            if node.battLevel > node.battWarn:
                node.battStatus = "G"
            elif node.battLevel > node.battCritical:
                node.battStatus = "W"
            else:
                node.battStatus = "C"
        if "voltage" in jPayload:
            node.battVoltage = jPayload["voltage"] / 1000
        if "linkquality" in jPayload:
            node.linkQuality = jPayload["linkquality"]

    node.online()
    node.save()
    print(f"Node {node.nodeID} has been updated in zigbee2mqttData")

    return

# ********************************************************************
def shellies(client, userdata, msg):
    """
    """
    sPayload = msg.payload.decode()
    
    cTopic = msg.topic.split("/")
    cNode = cTopic[1]

    jPayload = {}
    if is_json(sPayload):
        jPayload = json.loads(sPayload)

    if cTopic[1] == "announce":
        if "id" in jPayload:
            node, created = Node.objects.get_or_create(nodeID = jPayload["id"])
            if "model" in jPayload:
                node.model = jPayload["model"]
            if "mac" in jPayload:
                node.macAddr = jPayload["mac"]
            if "ip" in jPayload:
                node.ipAddr = jPayload["ip"]
            node.online()
            node.save()
            return

    node, created = Node.objects.get_or_create(nodeID = cNode)

    if len(cTopic) == 3:
        if cTopic[2] == "online" and sPayload == "false":
            node.status = 'X'
            node.textStatus = "Missing"
            node.save()
            return
        if cTopic[2] == "announce":
            if "model" in jPayload:
                node.model = jPayload["model"]
            if "mac" in jPayload:
                node.macAddr = jPayload["mac"]
            if "ip" in jPayload:
                node.ipAddr = jPayload["ip"]
    
    node.online()
    node.save()
    print(f"Node {node.nodeID} has been updated in shellies")

    return


# ******************************************************************
def node_back_online(node):
    """
  Procedure run when a node is seen to be back on line
  """
    node.notification_sent = False
    node.status = "C"
    node.textStatus = "Online"
    node.save()
    return


# ******************************************************************
def missing_node(node):
    """
  Procedure run when a node has not been seen for a while
  """
    if node.status == "C":
        node.textStatus = "Missing"
        node.status = "X"
        node.notification_sent = True
        node.status_sent = timezone.make_aware(
            datetime.datetime.now(), timezone.get_current_timezone()
        )
        node.save()
        cDict = {"node": node, "base_url": eWeb_Base_URL}
        sendNotifyEmail(
            "Node down notification for {}".format(node.nodeID),
            cDict,
            "monitor/email-down.html",
        )
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

        msg = MIMEText(body, "html")
        msg["From"] = eMail_From

        msg["To"] = eMail_To
        msg["Subject"] = inSubject

        email_server.sendmail(eMail_From, eMail_To, msg.as_string())
        email_server.close()
    except Exception as e:
        print(e)
        print("Houston, we have an email error {}".format(e))
        # logging.error("SMTP error {}".format(e))

    return


# ******************************************************************************
def sendReport():
    """
  Function collates data and sends a full system report
  """
    print("Send full report")
    allNodes = Node.objects.all()
    batWarnList = []
    batCritList = []
    nodeOKList = []
    nodeDownList = []
    for a in allNodes:
        if a.status == "C":
            if a.battName == None:
                nodeOKList.append(a)
            else:
                if a.battLevel > a.battWarn:
                    nodeOKList.append(a)
                elif a.battLevel > a.battCritical:
                    batWarnList.append(a)
                else:
                    batCritList.append(a)
        elif a.status == "X":
            nodeDownList.append(a)
    cDict = {
        "nodes": allNodes,
        "nodeOK": nodeOKList,
        "nodeWarn": batWarnList,
        "nodeCrit": batCritList,
        "nodeDown": nodeDownList,
        "base_url": eWeb_Base_URL,
    }
    sendNotifyEmail("Home IoT report", cDict, "monitor/email-full.html")
    print("Sent Daily email")
    return


# ********************************************************************
def is_json(myjson):
    """
    Function to check if an input is a valid JSON message
    """
    if not isinstance(myjson, (str)):
        return False
    #print(f"'is_json' Input is {myjson}")
    try:
        json_object = json.loads(myjson)
    except ValueError as e:
        #print(f"'is_json' NOT valid JSON")
        return False
    if not isinstance(json_object, (dict)):
        #print(f"'is_json' Output not dict")
        return False

    #print(f"'is_json' valid JSON, Output is {json_object}, type is: {type(json_object)}")
    return True


# ******************************************************************
def mqtt_monitor():
    """ The main program that sends updates to the MQTT system
    """

    # functions called by mqtt client
    client.on_connect = mqtt_on_connect
    client.on_message = mqtt_on_message

    # set up the local MQTT environment
    client.username_pw_set(eMqtt_user, eMqtt_password)
    client.connect(eMqtt_host)

    # used to manage mqtt subscriptions
    client.loop_start()

    # initialise the checkpoint timer
    checkTimer = timezone.now()

    # aNode = Node.objects.get(pk=10)
    # cDict = {'node': aNode}
    # sendNotifyEmail("Test email", cDict, "monitor/email-down.html")
    # print("Sent test email")

    conf, created = Setting.objects.get_or_create(sKey="LastSummary")
    if created:
        conf.dValue = timezone.now() + datetime.timedelta(days=-3)
        conf.save()

    notification_data = {
        "LastSummary":conf.dValue,
    }

    startTime = timezone.now()

    while True:
        time.sleep(1)

        # this section runs regularly (every 15 sec) and does a number of functions
        if (timezone.now() - checkTimer) > datetime.timedelta(
            0, 15
        ):  # second value is seconds to pause between....
            # update the checkpoint timer
            checkTimer = timezone.now()  # reset timer

            print("Timer check")

            allNodes = Node.objects.all()

            for n in allNodes:
                if n.lastseen:
                    # if nothing then our 'patience' will run out
                    if (timezone.now() - n.lastseen) > datetime.timedelta(
                        minutes=n.allowedDowntime
                    ):
                        print(
                            "Node {} not seen for over {} minutes".format(
                                n, n.allowedDowntime
                            )
                        )
                        missing_node(n)

            if (timezone.now() - startTime) > datetime.timedelta(
                hours=1
            ):  # this section is ony run if the script has been running for an hour
                if timezone.now().hour > 7:  # run at certain time of the day
                    lsConf = Setting.objects.get(sKey="LastSummary")
                    # print("Check 1 {}".format(notification_data["LastSummary"]))
                    if (lsConf.dValue != timezone.now().day):
                        print("Send 8am messages")
                        sendReport()
                        lsConf.dValue = timezone.now()
                        lsConf.save()
                        # update out notification data and save


# ********************************************************************
if __name__ == "__main__":
    mqtt_monitor()
