from django import forms

from .models import Message


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ("body",)
        widgets = {
            "body": forms.Textarea(
                attrs={"rows": 2, "placeholder": "Write a message…", "autofocus": True}
            )
        }
        labels = {"body": ""}

    def clean_body(self):
        body = self.cleaned_data["body"].strip()
        if not body:
            raise forms.ValidationError("Message is empty.")
        return body
