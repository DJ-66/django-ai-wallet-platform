from django import forms
from django.contrib.auth.models import User
from .models import UserProfile
from .models import FeedPost


class FeedPostForm(forms.ModelForm):
    class Meta:
        model = FeedPost
        fields = [
            "content",
            "image",
            "is_public",
            "is_paid",
            "unlock_price",
        ]

        widgets = {
            "content": forms.Textarea(attrs={
                "rows": 4,
                "placeholder": "What's happening?",
            }),
        }
class SignUpForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    password_confirm = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ["username", "email", "password"]

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip().lower()

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")

        return email


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = [
            "display_name",
            "bio",
            "avatar",
            "banner",
            "location",
            "website",
        ]
