from django.shortcuts import render
from django.http import HttpResponse
from django.template import loader
from django.contrib.auth.models import User
from django.views import generic

from .models import Node

# Create your views here.
def node_list(request):
    node_list = Node.objects.all()
    context = {
        'node_list': node_list,
    }
    return render(request, 'monitor/node_list.html', context)
    
def index(request):
    nodeList = Node.objects.order_by('nodeID')
    onlineNodes = nodeList.filter(status__startswith = "C")
    offlineNodes = Node.objects.order_by('nodeID').filter(status="X")
    MaintNodes = Node.objects.order_by('nodeID').filter(status="M")
    context = {'nodeList': nodeList, 'onlineNodes': onlineNodes, 'offlineNodes': offlineNodes}
    return render(request, 'monitor/index.html', context)
  
def node_detail(request, node_id):
    node = Node.objects.get(pk=node_id)
    try:
      newStatus = request.POST['newStatus']
      node.textStatus = newStatus
      node.save()
    except Exception as e:
      print(e)
    context = {
        'node': node,
    }
    return render(request, 'monitor/node_detail.html', context)