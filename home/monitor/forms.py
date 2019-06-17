from django import forms
from .models import Node

#class NodeUpdateForm(forms.Form):
#    descr = forms.CharField(label='Node description', widget=forms.Textarea)

class NodeUpdateModelForm(forms.ModelForm):
    class Meta:
        model = Node
        fields = (['descr', 'topic', 'status', 'allowedDowntime', 'battName', 'battWarn', 'battCritical'])
        widgets = {
            'descr': forms.Textarea(attrs={'rows': 3}),
        }