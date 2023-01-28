from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

# *******************************************************************


class HassDomain(models.Model):
    name = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.name}"

# *******************************************************************


class DeviceType(models.Model):
    name = models.CharField(max_length=30)
    descr = models.TextField(null=True, blank=True)
    noStatus = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name}"

    class Meta:
        ordering = ["name"]

# *******************************************************************


class Node(models.Model):
    nodeID = models.CharField(max_length=100)
    devType = models.ForeignKey(
        DeviceType, on_delete=models.SET_NULL, null=True, blank=True
    )
    descr = models.TextField(null=True, blank=True)
    topic = models.CharField(max_length=300, null=True, blank=True)
    status = models.CharField(
        max_length=1,
        default="X",
        help_text="'C' for current/online, 'X' for offline, 'M' for maintenance mode (no notifications)",
    )
    textStatus = models.CharField(max_length=30, null=True, blank=True)
    is_gateway = models.BooleanField(default=False)
    notification_sent = models.BooleanField(default=False)
    lastseen = models.DateTimeField(null=True, blank=True)
    status_sent = models.DateTimeField(null=True, blank=True)
    next_update = models.DateTimeField(null=True, blank=True)
    lastData = models.TextField(null=True, blank=True)
    allowedDowntime = models.IntegerField(
        default=60,
        help_text="Minutes that the node can be 'unheard' before being marked as Offline",
    )
    battPower = models.BooleanField(default=False, help_text="True if the node is battery powered")
    battName = models.CharField(
        max_length=30,
        null=True,
        blank=True,
        help_text="Name of JSON attribute that contains battery level",
    )
    battLevel = models.FloatField(default=0.0)
    battVoltage = models.FloatField(default=0.0)
    battMonitor = models.BooleanField(default=False)
    battWarn = models.FloatField(
        default=0.0, help_text="Battery level at which to send warning messages"
    )
    battCritical = models.FloatField(
        default=0.0, help_text="Battery level at which to send critical messages"
    )
    battStatus = models.CharField(
        max_length=1,
        default=" ",
        null=True, 
        blank=True,
        help_text="'G' for good, 'W' for warning, 'C' for critically low, ' ' for not monitored",
    )
    linkQuality = models.FloatField(
        default=0.0, help_text="The link quality of the node",null=True, 
        blank=True,
    )
    RSSI = models.FloatField(
        default=0.0, help_text="Received Signal Strength Indicator"
    )

    model = models.CharField(max_length=100, null=True, blank=True)
    macAddr = models.CharField(max_length=20, null=True, blank=True)
    ipAddr = models.CharField(max_length=20, null=True, blank=True)
    generated = models.CharField(max_length=30, null=True, blank=True)
    lstMQTTTopic = models.CharField(max_length=100, null=True, blank=True)
    
    class Meta:
        ordering = ["nodeID"]

    def __str__(self):
        return self.nodeID

    def online(self, msg):
        self.status = 'C'
        self.textStatus = "Online"
        self.lastseen = timezone.now()
        self.lstMQTTTopic = msg.topic
        self.save()
        return


class Entity(models.Model):
    entityID = models.CharField(max_length=100)
    node = models.ForeignKey(Node, on_delete=models.CASCADE)
    domain = models.ForeignKey(
        HassDomain, on_delete=models.SET_NULL, null=True, blank=True
    )
    state_topic = models.CharField(max_length=200, null=True, blank=True)
    json_key = models.CharField(max_length=50, null=True, blank=True)
    availability_topic = models.CharField(
        max_length=200, null=True, blank=True)
    text_state = models.CharField(max_length=200, null=True, blank=True)
    num_state = models.FloatField(default=0.0)

    def __str__(self):
        return(f"Node: {self.node.nodeID}, Entity: {self.entityID}")


# class Profile(models.Model):
# user = models.OneToOneField(User, on_delete=models.CASCADE)
# phone_no = models.CharField(max_length=30, blank=True)
# def __str__(self):
#  return(self.user.username)

# class UserNotify(models.Model):
#  node = models.ForeignKey(Node, on_delete=models.CASCADE)
#  user = models.ForeignKey(Profile, on_delete=models.CASCADE)
#  send_email = models.BooleanField(default=False)
#  send_SMS = models.BooleanField(default=False)
#  def __str__(self):
#    return("{} notifications to {}".format(self.node.NodeID, self.user.user.username))

# @receiver(post_save, sender=User)
# def create_user_profile(sender, instance, created, **kwargs):
#    if created:
#        Profile.objects.create(user=instance)

# @receiver(post_save, sender=User)
# def save_user_profile(sender, instance, **kwargs):
#    instance.profile.save()


class Setting(models.Model):
    sKey = models.CharField(max_length=30)
    sValue = models.CharField(max_length=300, default=" ")
    dValue = models.DateTimeField(default=timezone.now)
    fValue = models.FloatField(default=0)

    def __str__(self):
        return "{}: {}".format(self.sKey, self.sValue)
