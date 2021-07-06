from django.contrib import admin
from .models import Node, HassDomain, Setting, Entity
#from .models import Profile
#from .models import UserNotify

# Register your models here.
admin.site.register(Node)
admin.site.register(Setting)
admin.site.register(HassDomain)
admin.site.register(Entity)