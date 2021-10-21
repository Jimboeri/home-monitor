#!/usr/bin/python

import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish
from django import template
import django.template.loader
from django.conf import settings
import os, sys, time
import pickle

import logging, syslog
import datetime
from django.utils import timezone
import json
import smtplib

# Define constants
DEBUG = 10
INFO = 20
WARNING = 30
ERROR = 40
CRITICAL = 50

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

baseLogging = int(os.getenv("BASE_LOGGING", WARNING))

eTesting = os.getenv("TESTING", "F")
if eTesting == "T":
    bTesting = True
else:
    bTesting = False

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
def is_number(s):
    """
    Function to see if a string is numeric
    """
    try:
        float(s)
        return True
    except ValueError:
        pass
 
    return False


# *******************************************************************
def prDebug(tStr, base=baseLogging, level=INFO):
    """
    Control output to logs
    """
    if level >= base:       # only print if level is high enough
        if level <= 10:     # DEBUG
            print(tStr)
            logging.debug(tStr)
        elif level <= 20:   # INFO
            print(tStr)
            logging.info(tStr)
        elif level <= 30:   # WARNING
            print(f"WARNING {tStr}")
            logging.warning(tStr)
        elif level <= 40:   # WARNING
            print(f"ERROR {tStr}")
            logging.error(tStr)
        elif level <= 50:   # WARNING
            print(f"CRITICAL {tStr}")
            logging.critical(tStr)
    return


# ********************************************************************
def mqtt_on_connect(client, userdata, flags, rc):
    """
      This procedure is called on connection to the mqtt broker
    """
    Topics = ["house", "zigbee2mqtt", "shellies", "homeassistant"]

    prDebug("MQTT conn entered")
    for topic in Topics:
        cTop = topic + "/#"
        client.subscribe(cTop)
        prDebug(f"Subscribed to {cTop}")
    
    prDebug("MQTTConn finished")
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


    lEnt = Entity.objects.filter(state_topic=msg.topic)
    if len(lEnt) > 0:
        if len(lEnt) > 1:
            prDebug(f"Found multiple entities for topic {msg.topic}")
        else:
            lEnt[0].text_state = sPayload
            if is_number(sPayload):
                lEnt[0].num_state = float(sPayload)
            lEnt[0].save()

    cNodeID = cTopic[1]
    prDebug(f"NodeID: {cNodeID}", level=DEBUG)
    
    try:
        nd, created = Node.objects.get_or_create(nodeID=cNodeID)
    except Exception as e:
        prDebug(f"Node creation error: {e}", level=ERROR)
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
        prDebug("Battery name is {}".format(nd.battName), level=DEBUG)
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
        prDebug(f"RSSI: {jPayload}", level=DEBUG)
        nd.RSSI = float(jPayload["RSSI"])

    nd.save()

    if created:
        prDebug("Node {} has been created in mqtt_on_message".format(nd.nodeID), level=DEBUG)
    else:
        prDebug("Node {} has been updated in mqtt_on_message".format(nd.nodeID), level=DEBUG)

# ********************************************************************
def hassDiscovery(client, userdata, msg):
    """
    """
    
    sPayload = msg.payload.decode()
    prDebug(f"Process Home assistant discovery, topic: {msg.topic}, payload: {sPayload}", level=INFO)
    cTopic = msg.topic.split("/")
    if len(cTopic) < 3:
        prDebug(f"Homeassistant error in discovery topic: {msg.topic}", level=ERROR)
        return
    try:
        domain, created = HassDomain.objects.get_or_create(name=cTopic[1])
    except Exception as e:
        prDebug(f"Error accessing/creating Domain record in hassDiscovery, error is: {e}", level=ERROR)
        return

    if is_json(sPayload):
        jPayload = json.loads(sPayload)
        if "device" in jPayload:
            if "name" in jPayload["device"]:
                cNode = jPayload["device"]["name"]
                node, created = Node.objects.get_or_create(nodeID = cNode)
                if created:
                    node.generated = "hassDiscovery"

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
    if created:
        node.generated = "zigbee2mqttData"

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
            node.lastData = sPayload
            node.save()
            return

    node, created = Node.objects.get_or_create(nodeID = cNode)
    if created:
        node.generated = "shellies"

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
    node.lastData = sPayload
    node.save()
    prDebug(f"Node {node.nodeID} has been updated in shellies", level=DEBUG)

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
        node.status_sent = timezone.now()
        node.save()
        cDict = {"node": node, "base_url": eWeb_Base_URL}
        sendNotifyEmail(
            "Node down notification for {}".format(node.nodeID),
            cDict,
            "monitor/email/email-down.html",
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
    prDebug("Send full report", level=INFO)
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
    sendNotifyEmail("Home IoT report", cDict, "monitor/email/email-full.html")
    prDebug("Sent Daily email", level=INFO)
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

    # Set up logging
    print("Home monitor script Starting")
    syslog.syslog("Home monitor script Starting")
    FORMAT = "%(asctime)-15s %(message)s"
    logging.basicConfig(
        filename="home-monitor.log",
        level=WARNING,
        format=FORMAT,
    )

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
    # sendNotifyEmail("Test email", cDict, "monitor/email/email-down.html")
    # print("Sent test email")

    conf, created = Setting.objects.get_or_create(sKey="LastSummary")
    if created:
        conf.dValue = timezone.now() + datetime.timedelta(days=-3)
        conf.save()

    notification_data = {
        "LastSummary":conf.dValue,
    }

    startTime = timezone.now()

    if bTesting:
        sendReport()

    while True:
        time.sleep(1)

        # this section runs regularly (every 15 sec) and does a number of functions
        if (timezone.now() - checkTimer) > datetime.timedelta(
            0, 15
        ):  # second value is seconds to pause between....
            # update the checkpoint timer
            checkTimer = timezone.now()  # reset timer

            prDebug("Timer check", level=INFO)

            allNodes = Node.objects.all()

            for n in allNodes:
                if n.lastseen:
                    # if nothing then our 'patience' will run out
                    if (timezone.now() - n.lastseen) > datetime.timedelta(
                        minutes=n.allowedDowntime
                    ):
                        prDebug(f"Node {n} not seen for over {n.allowedDowntime} minutes", level=WARNING)
                        missing_node(n)

            if (timezone.now() - startTime) > datetime.timedelta(
                hours=1
            ):  # this section is ony run if the script has been running for an hour
                if timezone.now().hour > 7:  # run at certain time of the day
                    lsConf = Setting.objects.get(sKey="LastSummary")
                    # print("Check 1 {}".format(notification_data["LastSummary"]))
                    if (lsConf.dValue != timezone.now().day):
                        prDebug("Send 8am messages", level=INFO)
                        sendReport()
                        lsConf.dValue = timezone.now()
                        lsConf.save()
                        # update out notification data and save


# ********************************************************************
if __name__ == "__main__":
    mqtt_monitor()
