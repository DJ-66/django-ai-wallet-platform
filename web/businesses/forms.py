from django import forms

from core.image_utils import process_fanz_image_upload

from .models import BusinessListing, BusinessUpdate, BusinessMedia


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
            quality=90,
        )



class BusinessListingForm(forms.ModelForm):
    tos_accepted = forms.BooleanField(
        required=True,
        label="I accept the FANZ Terms of Service",
        error_messages={
            "required": (
                "You must accept the FANZ Terms of Service "
                "before creating your business."
            ),
        },
    )
    def __init__(self, *args, **kwargs):
        is_edit = kwargs.pop("is_edit", False)
        super().__init__(*args, **kwargs)

        if is_edit:
            self.fields.pop("tos_accepted", None)

    class Meta:
        model = BusinessListing
        fields = [
            "name",
            "industry",
            "description",
            "hero_image",
            "city",
            "country",
            "website_url",
            "phone",
            "email",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "placeholder": "Business name",
                    "autocomplete": "organization",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "rows": 6,
                    "placeholder": (
                        "Tell people about your business, services, "
                        "and what makes it special."
                    ),
                }
            ),
            "city": forms.TextInput(
                attrs={
                    "placeholder": "City",
                    "autocomplete": "address-level2",
                }
            ),
            "country": forms.TextInput(
                attrs={
                    "placeholder": "Country",
                    "autocomplete": "country-name",
                }
            ),
            "website_url": forms.URLInput(
                attrs={
                    "placeholder": "https://example.com",
                    "autocomplete": "url",
                }
            ),
            "phone": forms.TextInput(
                attrs={
                    "placeholder": "Business phone",
                    "autocomplete": "tel",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "placeholder": "Business email",
                    "autocomplete": "email",
                }
            ),
        }

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
            quality=90,
        )


class BusinessUpdateForm(forms.ModelForm):
    class Meta:
        model = BusinessUpdate
        fields = [
            "title",
            "body",
            "image",
            "is_featured",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "placeholder": "Update title",
                }
            ),
            "body": forms.Textarea(
                attrs={
                    "rows": 6,
                    "placeholder": (
                        "Share news, specials, announcements, "
                        "or anything happening at your business."
                    ),
                }
            ),
            "image": forms.ClearableFileInput(
                attrs={
                    "accept": "image/*,.jpg,.jpeg,.png,.webp,.avif",
                }
            ),
        }

    def clean_image(self):
        image = self.cleaned_data.get("image")

        if not image:
            return image

        return process_fanz_image_upload(
            image,
            platform_footer=True,
            max_width=1600,
            max_height=1600,
            quality=90,
        )

class BusinessUpdateAdminForm(forms.ModelForm):
    class Meta:
        model = BusinessUpdate
        fields = "__all__"

    def clean_image(self):
        image = self.cleaned_data.get("image")

        if not image:
            return image

        existing_image = getattr(self.instance, "image", None)

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
            quality=90,
        )


class MultipleBusinessImageInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleBusinessImageField(forms.ImageField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault(
            "widget",
            MultipleBusinessImageInput(
                attrs={
                    "accept": "image/*,.jpg,.jpeg,.png,.webp,.avif",
                }
            ),
        )
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_image_clean = super().clean

        if isinstance(data, (list, tuple)):
            return [
                single_image_clean(image, initial)
                for image in data
            ]

        if data:
            return [single_image_clean(data, initial)]

        return []


class BusinessMediaForm(forms.ModelForm):
    images = MultipleBusinessImageField(
        required=True,
    )

    class Meta:
        model = BusinessMedia
        fields = []

    def clean_images(self):
        images = self.cleaned_data.get("images", [])

        if len(images) > 8:
            raise forms.ValidationError(
                "You may upload a maximum of 8 images at once."
            )

        processed_images = []

        for image in images:
            processed_images.append(
                process_fanz_image_upload(
                    image,
                    platform_footer=True,
                    max_width=1600,
                    max_height=1600,
                    quality=90,
                )
            )

        return processed_images
