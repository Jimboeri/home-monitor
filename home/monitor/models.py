from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

# Create your models here.
class Node(models.Model):
  nodeID = models.CharField(max_length=30)
  descr = models.TextField(null=True, blank=True)
  topic = models.CharField(max_length=300, null=True, blank=True)
  status = models.CharField(max_length=1, default="X", help_text="'C' for current/online, 'X' for offline, 'M' for maintenance mode (no notifications)")
  textStatus = models.CharField(max_length=30, null=True, blank=True)
  is_gateway = models.BooleanField(default=False)
  notification_sent = models.BooleanField(default=False)
  lastseen = models.DateTimeField(null=True, blank=True)
  status_sent = models.DateTimeField(null=True, blank=True)
  next_update = models.DateTimeField(null=True, blank=True)
  lastData = models.TextField(null=True, blank=True)
  allowedDowntime = models.IntegerField(default=60, help_text="Minutes that the node can be 'unheard' before being marked as Offline")
  battName = models.CharField(max_length=30, null=True, blank=True, help_text = "Name of JSON attribute that contains battery level")
  battLevel = models.FloatField(default=0.0)
  battMonitor = models.BooleanField(default=False)
  battWarn = models.FloatField(default=0.0, help_text = "Battery level at which to send warning messages")
  battCritical = models.FloatField(default=0.0, help_text = "Battery level at which to send critical messages")
  RSSI = models.FloatField(default=0.0, help_text = "Received Signal Strength Indicator")
  def __str__(self):
    return(self.nodeID)

#class Profile(models.Model):
  #user = models.OneToOneField(User, on_delete=models.CASCADE)
  #phone_no = models.CharField(max_length=30, blank=True)
  #def __str__(self):
  #  return(self.user.username)
  
#class UserNotify(models.Model):
#  node = models.ForeignKey(Node, on_delete=models.CASCADE)
#  user = models.ForeignKey(Profile, on_delete=models.CASCADE)
#  send_email = models.BooleanField(default=False)
#  send_SMS = models.BooleanField(default=False)
#  def __str__(self):
#    return("{} notifications to {}".format(self.node.NodeID, self.user.user.username))
  
#@receiver(post_save, sender=User)
#def create_user_profile(sender, instance, created, **kwargs):
#    if created:
#        Profile.objects.create(user=instance)

#@receiver(post_save, sender=User)
#def save_user_profile(sender, instance, **kwargs):
#    instance.profile.save()  

class Setting(models.Model):
  sKey = models.CharField(max_length=30)
  sValue = models.CharField(max_length=300)
  def __str__(self):
    return("{}: {}".format(self.sKey, self.sValue))
