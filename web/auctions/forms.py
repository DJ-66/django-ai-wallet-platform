from django import forms
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from .models import FeedPost, UserProfile, DirectMessage

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
            "bank_qr_image",
            "bank_payment_notes",
            "location",
            "website",
            "youtube",
            "instagram",
            "x_url",
            "tiktok",
            "telegram",
        ]

        labels = {
            "display_name": _("Display name"),
            "bio": _("Bio"),
            "avatar": _("Avatar"),
            "banner": _("Banner"),
            "bank_qr_image": _("Payment QR Code"),
            "bank_payment_notes": _("Payment instructions"),
            "location": _("Location"),
            "website": _("Website"),

            # brand names stay as-is
            "youtube": "YouTube",
            "instagram": "Instagram",
            "x_url": "X.com",
            "tiktok": "TikTok",
            "telegram": "Telegram",
}

class DirectMessageForm(forms.ModelForm):
    class Meta:
        model = DirectMessage
        fields = ["body"]
        widgets = {
            "body": forms.Textarea(attrs={
                "rows": 3,
                "placeholder": "Write a message...",
            })
        }
