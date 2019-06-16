from django import forms
from .models import Node

#class NodeUpdateForm(forms.Form):
#    descr = forms.CharField(label='Node description', widget=forms.Textarea)

class NodeUpdateModelForm(forms.ModelForm):
    class Meta:
        model = Node
        fields = (['descr', 'battName', 'topic', 'status', 'allowedDowntime'])
        widgets = {
            'descr': forms.Textarea(attrs={'rows': 3}),
        }