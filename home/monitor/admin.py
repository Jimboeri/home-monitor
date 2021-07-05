from django.contrib import admin
from .models import Node, HassDomain
#from .models import Profile
#from .models import UserNotify
from .models import Setting

# Register your models here.
admin.site.register(Node)
#admin.site.register(Profile)
#admin.site.register(UserNotify)
admin.site.register(Setting)
admin.site.register(HassDomain)