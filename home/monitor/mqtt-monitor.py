#!/usr/bin/python

from email.mime.text import MIMEText
import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish
from django import template
import django.template.loader
from django.conf import settings
import os
import sys
import time
import pickle

import logging
import syslog
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

sys.path.append("/code/home")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "home.settings")
django.setup()

from monitor.models import Node, Setting, HassDomain, Entity, DeviceType

eMqtt_client_id = os.getenv("HOME_MQTT_CLIENT_ID")
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
    tPrefix = "Dev system - "
    mqttPrefix = "Ernie/"
else:
    bTesting = False
    tPrefix = ""
    mqttPrefix = ""

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
    #try:
    #    float(s)
    #    return True
    #except ValueError:
    #    pass

    #return False

    if isinstance(s, float):
        return True
    else:
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
    Topics = ["house", "zigbee2mqtt", "shellies", "homeassistant", "tasmota"]

    logging.info("MQTT conn entered")
    for topic in Topics:
        cTop = f"{mqttPrefix}{topic}/#"
        client.subscribe(cTop)
        logging.info(f"Subscribed to {cTop}")

    logging.info("MQTTConn finished")
    return


# ********************************************************************
def mqtt_on_message(client, userdata, msg):
    """This procedure is called each time a mqtt message is received"""

    sPayload = msg.payload.decode()

    #logging.debug(f"MQTT message received")

    cTopic = msg.topic.split("/")
    if bTesting:
        if cTopic[0] in mqttPrefix:
            del cTopic[0]
            #prDebug(f"Testing in progress, cTopic is now: {cTopic}", level=DEBUG)

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
    logging.debug(f"NodeID: {cNodeID}")

    try:
        nd, created = Node.objects.get_or_create(nodeID=cNodeID)
    except Exception as e:
        logging.error(f"Node creation error: {e}")
        return
 
    if len(cTopic) > 2:
        if cTopic[2] == "state":
            if sPayload == "on" or sPayload == "off" or sPayload == "online":
                nd.online(msg)
                if nd.status != "C":
                    node_back_online(nd)
            elif sPayload == "unavailable":
                logging.debug(f"Node {nd} is unavailable")
                if nd.status != "X":
                    missing_node(nd)
            return

    lEnt = Entity.objects.filter(state_topic=msg.topic)
    if len(lEnt) > 0:
        if len(lEnt) > 1:
            logging.warning(f"Found multiple entities for topic {msg.topic}")
        else:
            lEnt[0].text_state = sPayload
            if is_number(sPayload):
                lEnt[0].num_state = float(sPayload)
            lEnt[0].save()
            node_back_online(lEnt[0].node)

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
        logging.debug("Battery name is {}".format(nd.battName))
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
        logging.debug(f"RSSI: {jPayload}")
        nd.RSSI = float(jPayload["RSSI"])

    nd.save()

    if created:
        logging.debug(f"Node {nd.nodeID} has been created in mqtt_on_message")
    else:
        logging.debug(f"Node {nd.nodeID} has been updated in mqtt_on_message")

# ********************************************************************


def hassDiscovery(client, userdata, msg):
    """
    """

    sPayload = msg.payload.decode()
    logging.info(
        f"Process Home assistant discovery, topic: {msg.topic}, payload: {sPayload}")
    cTopic = msg.topic.split("/")
    if bTesting:
        if cTopic[0] in mqttPrefix:
            del cTopic[0]

    if len(cTopic) < 3:
        logging.error(
            f"Homeassistant error in discovery topic: {msg.topic}")
        return
    try:
        domain, created = HassDomain.objects.get_or_create(name=cTopic[1])
    except Exception as e:
        logging.error(
            f"Error accessing/creating Domain record in hassDiscovery, error is: {e}")
        return

    if is_json(sPayload):
        jPayload = json.loads(sPayload)
        if "device" in jPayload:
            if "name" in jPayload["device"]:
                cNode = jPayload["device"]["name"]
                node, created = Node.objects.get_or_create(nodeID=cNode)
                if created:
                    node.generated = "hassDiscovery"

                if "model" in jPayload["device"]:
                    node.model = jPayload["device"]["model"]

                if "device" in jPayload:
                    jDevice = jPayload["device"]
                    if "sw_version" in jDevice:
                        if "esphome" in jDevice["sw_version"]:
                            dev, created = DeviceType.objects.get_or_create(
                                name="Esphome")
                            node.devType = dev

                node.save()

                if "unique_id" in jPayload:
                    entity, eCreated = Entity.objects.get_or_create(
                        entityID=jPayload["unique_id"], node=node, domain=domain)

                    if "state_topic" in jPayload:
                        entity.state_topic = jPayload["state_topic"]
                    if "availability_topic" in jPayload:
                        entity.availability_topic = jPayload["availability_topic"]

                    if "value_template" in jPayload:
                        tStr = jPayload["value_template"]
                        tStr = tStr.replace("{", "")
                        tStr = tStr.replace("}", "")
                        tStr = tStr.replace(" ", "")
                        lStr = tStr.split(".")
                        if len(lStr) == 2:
                            entity.json_key = lStr[1]

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
    logging.info(f"zigbee data processing")
    sPayload = msg.payload.decode()

    cTopic = msg.topic.split("/")
    if bTesting:
        if cTopic[0] in mqttPrefix:
            del cTopic[0]

        if cTopic[1] == "bridge" and cTopic[2] == "devices":
            with open('bridge-devices.json', 'w') as f:
                f.write(sPayload)

    cNode = cTopic[1]

    node, created = Node.objects.get_or_create(nodeID=cNode)
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

        dev, created = DeviceType.objects.get_or_create(name="Zigbee")
        if not node.devType:
            node.devType = dev

        for e in node.entity_set.all():
            if e.json_key in jPayload:
                if is_number(jPayload[e.json_key]):
                    e.num_state = float(jPayload[e.json_key])
                    #logging.debug(f"Node {node.nodeID}, entity {e.entityID} numeric update")
                else:
                    e.text_state = jPayload[e.json_key]
                    #logging.debug(f"Node {node.nodeID}, entity {e.entityID} text update")
                e.save()

    node.online(msg)
    #node.save()
    logging.info(f"Node {node.nodeID} has been updated in zigbee2mqttData")

    return

# ********************************************************************


def shellies(client, userdata, msg):
    """
    """
    sPayload = msg.payload.decode()

    cTopic = msg.topic.split("/")
    if bTesting:
        if cTopic[0] in mqttPrefix:
            del cTopic[0]
            
    cNode = cTopic[1]

    jPayload = {}
    if is_json(sPayload):
        jPayload = json.loads(sPayload)

    if cTopic[1] == "announce":
        """
        if "id" in jPayload:
            node, created = Node.objects.get_or_create(nodeID=jPayload["id"])
            if "model" in jPayload:
                node.model = jPayload["model"]
            if "mac" in jPayload:
                node.macAddr = jPayload["mac"]
            if "ip" in jPayload:
                node.ipAddr = jPayload["ip"]
            
            node.lastData = sPayload
            node.online()
            node.save()
        """
        return

    node, created = Node.objects.get_or_create(nodeID=cNode)
    if created:
        node.generated = "shellies"

    # Device type processing
    dev, devCreated = DeviceType.objects.get_or_create(name="Shelly")

    node.devType = dev

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
        if cTopic[2] == "info":
            if "wifi_sta" in jPayload:
                if "rssi" in jPayload["wifi_sta"]:
                    node.RSSI = jPayload["wifi_sta"]["rssi"]

    node.online(msg)
    node.lastData = sPayload
    node.save()
    #prDebug(f"Node {node.nodeID} has been updated in shellies", level=INFO)

    return


# ******************************************************************
def node_back_online(node):
    """
  Procedure run when a node is seen to be back on line
  """
    node.notification_sent = False
    node.status = "C"
    node.textStatus = "Online"
    node.lastseen = timezone.now()
    node.save()
    logging.debug(f"Node {node.nodeID} marked as back on line, no notification")
    return


# ******************************************************************
def missing_node(node):
    """
  Procedure run when a node has not been seen for a while
  """
    if node.status == "C":
        if node.devType and node.devType.noStatus:
            # some nodes do not send status messages
            return
        node.textStatus = "Missing"
        node.status = "X"
        node.notification_sent = True
        node.status_sent = timezone.now()
        node.save()
        cDict = {"node": node, "base_url": eWeb_Base_URL}
        sendNotifyEmail(
            f"{tPrefix}Node down notification for {node.nodeID}",
            cDict,
            "monitor/email/email-down.html",
        )
        logging.warning(f"Node {node.nodeID} marked as down and notification sent")
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
        logging.error(f"Houston, we have an email error in sendNotifyEmail, error is {e}")

    return


# ******************************************************************************
def sendReport():
    """
  Function collates data and sends a full system report
  """
    logging.info("Send full report")
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
    sendNotifyEmail(f"{tPrefix}Home IoT report", cDict,
                    "monitor/email/email-full.html")
    logging.info("Sent Daily email")
    return


# ********************************************************************
def is_json(myjson):
    """
    Function to check if an input is a valid JSON message
    """
    if not isinstance(myjson, (str)):
        return False

    try:
        json_object = json.loads(myjson)
    except ValueError as e:
        #prDebug(f"'is_json' NOT valid JSON", base=baseLogging, level=DEBUG)
        return False
    if not isinstance(json_object, (dict)):
        #print(f"'is_json' Output not dict")
        return False

    #prDebug(f"'is_json' valid JSON, Output is {json_object}, type is: {type(json_object)}", base=baseLogging, level=DEBUG)
    return True


# ******************************************************************
def mqtt_monitor():
    """ The main program that sends updates to the MQTT system
    """

    # Set up logging
    #print("Home monitor script Starting")
    #syslog.syslog("Home monitor script Starting")
    #FORMAT = "%(asctime)-15s %(message)s"
    #logging.basicConfig(
    #    filename="home-monitor.log",
    #    level=WARNING,
    #    format=FORMAT,
    #)

    logging.info("Script has started logging")

    # functions called by mqtt client
    client.on_connect = mqtt_on_connect
    client.on_message = mqtt_on_message

    # set up the local MQTT environment
    client.username_pw_set(eMqtt_user, eMqtt_password)
    client.connect(eMqtt_host)

    logging.info(f"MQTT connected to host: {eMqtt_host}, with user {eMqtt_user}")

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
        "LastSummary": conf.dValue,
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

            logging.info("Timer check")

            allNodes = Node.objects.all()

            for n in allNodes:
                if n.lastseen:
                    # if nothing then our 'patience' will run out
                    if (timezone.now() - n.lastseen) > datetime.timedelta(
                        minutes=n.allowedDowntime
                    ):
                        tdRunning = timezone.now() - startTime
                        # dont check if nodes are down until after node allowed downtime since script started
                        if (tdRunning.total_seconds() > (n.allowedDowntime * 60) or bTesting):
                            # Only if been running for over an hour
                            if startTime + datetime.timedelta(hours=1) < timezone.now():
                                missing_node(n)

            # this section is ony run if the script has been running for an hour
            if (timezone.now() - startTime) > datetime.timedelta(hours=1):
                #prDebug(f"Script running for more than 1 hour", base=baseLogging, level=DEBUG)
                if timezone.now().hour > 7:  # run at certain time of the day
                    lsConf = Setting.objects.get(sKey="LastSummary")
                    #prDebug(f"Check: stored {lsConf.dValue}", base=baseLogging, level=DEBUG)
                    if (lsConf.dValue.day != timezone.now().day):
                        logging.info("Send 8am messages")
                        sendReport()
                        lsConf.dValue = timezone.now()
                        lsConf.save()
                        # update out notification data and save


# ********************************************************************
if __name__ == "__main__":
    mqtt_monitor()
