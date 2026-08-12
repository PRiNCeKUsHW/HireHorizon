from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

User = get_user_model()


class RegisterForm(UserCreationForm):
    email = forms.EmailField(
        required=True, help_text="Used for sign-in recovery only. Never shown publicly."
    )
    display_name = forms.CharField(max_length=50, required=False)

    class Meta:
        model = User
        fields = ("username", "email", "display_name")

    def clean_email(self):
        """Emails must be unique; the model field alone does not enforce it."""
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with that email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.display_name = self.cleaned_data.get("display_name", "")
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    """Standard Django auth form.

    The default error message is intentionally the same whether the username
    exists or the password is wrong, which avoids confirming who has an account.
    """

    username = forms.CharField(widget=forms.TextInput(attrs={"autofocus": True}))


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("display_name", "bio", "location", "website")
        widgets = {
            "bio": forms.Textarea(
                attrs={"rows": 3, "placeholder": "A short line about you"}
            ),
        }
        help_texts = {"bio": "Up to 280 characters."}
