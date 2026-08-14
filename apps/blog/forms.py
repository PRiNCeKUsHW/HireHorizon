from django import forms

from .models import Comment, Post


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ("title", "content", "status")
        widgets = {
            "title": forms.TextInput(
                attrs={"class": "editor__title", "placeholder": "Give it a title"}
            ),
            "content": forms.Textarea(
                attrs={
                    "class": "editor__content",
                    "rows": 14,
                    "placeholder": "Start writing…",
                }
            ),
        }

    def clean_title(self):
        title = self.cleaned_data["title"].strip()
        if not title:
            raise forms.ValidationError("A title is required.")
        return title

    def clean_content(self):
        content = self.cleaned_data["content"].strip()
        if len(content) < 2:
            raise forms.ValidationError("Write a little more than that.")
        return content


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ("body",)
        widgets = {
            "body": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Add your reply…",
                    # The composer is deliberately unlabelled on screen, which
                    # left the textarea with no accessible name at all.
                    "aria-label": "Write a reply",
                }
            )
        }
        labels = {"body": ""}

    def clean_body(self):
        body = self.cleaned_data["body"].strip()
        if not body:
            raise forms.ValidationError("Your reply is empty.")
        return body
