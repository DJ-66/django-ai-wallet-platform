from django import forms
from core.image_utils import process_fanz_image_upload
from .models import BusinessListing


class BusinessListingAdminForm(forms.ModelForm):
    class Meta:
        model = BusinessListing
        fields = "__all__"

    def clean_hero_image(self):
        image = self.cleaned_data.get("hero_image")

        if not image:
            return image

        existing_image = getattr(self.instance, "hero_image", None)

        if (
            self.instance.pk
            and existing_image
            and image == existing_image
        ):
            return image

        return process_fanz_image_upload(
            image,
            platform_footer=True,
            max_width=1600,
            max_height=1600,
            quality=82,
        )
