from django.urls import path

from . import views

app_name = "monitor"
urlpatterns = [
    path('', views.index, name='index'),
    path('node_list/', views.node_list, name='node_list'),
    path('node/<int:node_id>/', views.node_detail, name='node_detail'),
    path('node/update/<int:node_id>/', views.node_update, name='node_update'),
    path('node/remove/<int:node_ref>/', views.node_remove, name='node_remove'),
]

