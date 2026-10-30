"""Account registration fields for anonymous business owners."""

from django import forms
from auctions.forms import SignUpForm


class GuestBusinessAccountForm(SignUpForm):
    """Reuse FANZ's username, email and password validation."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["username"].label = "FANZ username"
        self.fields["email"].label = "Account email"

        self.fields["password"].widget.attrs.update({
            "autocomplete": "new-password",
        })
        self.fields["password_confirm"].widget.attrs.update({
            "autocomplete": "new-password",
        })


    def clean(self):
        cleaned_data = super().clean()

        password = cleaned_data.get("password")
        confirmation = cleaned_data.get("password_confirm")

        if password and confirmation and password != confirmation:
            self.add_error(
                "password_confirm",
                "Passwords do not match.",
            )

        return cleaned_data
