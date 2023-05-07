from django.contrib import admin
from .models import Node, HassDomain, Setting, Entity, DeviceType, MqttStore
#from .models import Profile
#from .models import UserNotify

# Register your models here.
admin.site.register(Node)
admin.site.register(Setting)
admin.site.register(HassDomain)
admin.site.register(Entity)
admin.site.register(DeviceType)
admin.site.register(MqttStore)

