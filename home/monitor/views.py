from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect
from django.template import loader
from django.contrib.auth.models import User
from django.views import generic
from django.urls import reverse
from django.contrib.auth.decorators import login_required

from .models import Node

from .forms import NodeUpdateModelForm

# Create your views here.
# *****************************************************************************
def node_list(request):
    """ ."""
    node_list = Node.objects.all()
    context = {
        "node_list": node_list,
    }
    return render(request, "monitor/node_list.html", context)

# *****************************************************************************
def index(request):
    nodeList = Node.objects.order_by("nodeID")
    onlineNodes = nodeList.filter(status__startswith="C")
    offlineNodes = Node.objects.order_by("nodeID").filter(status="X")
    MaintNodes = Node.objects.order_by("nodeID").filter(status="M")
    context = {
        "nodeList": nodeList,
        "onlineNodes": onlineNodes,
        "offlineNodes": offlineNodes,
    }
    return render(request, "monitor/index.html", context)


# *****************************************************************************
def node_detail(request, node_id):
    node = Node.objects.get(pk=node_id)
    try:
        newStatus = request.POST["newStatus"]
        node.textStatus = newStatus
        node.save()
    except Exception as e:
        print(e)
    context = {
        "node": node,
    }
    return render(request, "monitor/node_detail.html", context)


# *****************************************************************************
@login_required
def node_update(request, node_id):
    # print("Enter node_update")
    # print(request.POST)
    node = get_object_or_404(Node, pk=node_id)

    if request.method == "POST":
        # create a form instance and populate it with data from the request:
        form = NodeUpdateModelForm(request.POST, instance=node)
        # form = NodeUpdateForm(request.POST)
        # print("Post received")
        # check whether it's valid:
        if form.is_valid():
            # print("Form valid")
            # process the data in form.cleaned_data as required
            form.save()
            # redirect to a new URL:
            return HttpResponseRedirect(reverse("node_detail", args=[node.id]))
    # if a GET (or any other method) we'll create a blank form
    else:
        form = NodeUpdateModelForm(instance=node)

    context = {"form": form, "node": node}
    return render(request, "monitor/node_update.html", context)

# *****************************************************************************
@login_required
def node_remove(request, node_ref):
    node = get_object_or_404(Node, pk=node_ref)
    if request.method == "POST":
        removeMe = "N"
        try:
            removeMe = request.POST["remove"]
        except:
            return HttpResponseRedirect(reverse("monitor:node_detail", args=[node.id]))
        if removeMe == "Y":
            node.status = "M"
            node.save()
            return HttpResponseRedirect(reverse("monitor:index"))
    context = {"node": node}

    return render(request, "monitor/node_remove.html", context)
