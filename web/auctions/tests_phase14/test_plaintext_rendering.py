"""Security regression tests for FANZ plaintext rendering."""

from django.template import Context, Template
from django.test import SimpleTestCase

from auctions.templatetags.post_content import (
    render_fanz_plaintext,
)


class FanzPlaintextRenderingTests(SimpleTestCase):

    def test_html_tags_are_escaped(self):
        result = str(
            render_fanz_plaintext("<b>Hello</b>")
        )

        self.assertEqual(
            result,
            "&lt;b&gt;Hello&lt;/b&gt;",
        )

    def test_script_injection_is_escaped(self):
        result = str(
            render_fanz_plaintext(
                '<script>alert("x")</script>'
            )
        )

        self.assertNotIn("<script>", result)
        self.assertIn("&lt;script&gt;", result)
        self.assertIn("&lt;/script&gt;", result)

    def test_html_attributes_are_escaped(self):
        result = str(
            render_fanz_plaintext(
                '<img src=x onerror="alert(1)">'
            )
        )

        self.assertNotIn("<img", result)
        self.assertIn("&lt;img", result)
        self.assertIn("&quot;", result)

    def test_multiline_text_preserved(self):
        result = str(
            render_fanz_plaintext(
                "First\r\nSecond\rThird\nFourth"
            )
        )

        self.assertEqual(
            result,
            "First<br>Second<br>Third<br>Fourth",
        )

    def test_empty_values(self):
        self.assertEqual(
            str(render_fanz_plaintext(None)),
            "",
        )

        self.assertEqual(
            str(render_fanz_plaintext("")),
            "",
        )

    def test_django_template_registration(self):
        template = Template(
            "{% load post_content %}"
            "{{ value|render_fanz_plaintext }}"
        )

        rendered = template.render(
            Context({
                "value": "<script>x</script>\nSafe",
            })
        )

        self.assertEqual(
            rendered,
            "&lt;script&gt;x&lt;/script&gt;<br>Safe",
        )
