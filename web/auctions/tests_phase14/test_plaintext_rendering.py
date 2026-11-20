"""Security regression tests for FANZ plaintext rendering."""

from django.template import Context, Template
from django.test import SimpleTestCase

from auctions.templatetags.post_content import (
    render_dm_plaintext,
    render_fanz_plaintext,
)


class DirectMessagePlaintextRenderingTests(SimpleTestCase):

    def test_valid_https_url_is_linkified(self):
        result = str(
            render_dm_plaintext(
                "Visit https://example.com/path?q=one#section"
            )
        )

        self.assertEqual(
            result,
            'Visit <a href="https://example.com/path?q=one#section" '
            'target="_blank" rel="noopener noreferrer ugc">'
            "https://example.com/path?q=one#section</a>",
        )

    def test_multiple_https_urls_are_linkified(self):
        result = str(
            render_dm_plaintext(
                "https://one.example/a and https://two.example/b"
            )
        )

        self.assertEqual(result.count("<a "), 2)
        self.assertIn('href="https://one.example/a"', result)
        self.assertIn('href="https://two.example/b"', result)

    def test_html_and_script_injection_are_escaped(self):
        result = str(
            render_dm_plaintext(
                '<script>alert("x")</script> '
                '<a href="https://evil.example">click</a>'
            )
        )

        self.assertNotIn("<script>", result)
        self.assertNotIn('<a href="https://evil.example">click</a>', result)
        self.assertIn("&lt;script&gt;", result)
        self.assertIn("&lt;a href=&quot;https://evil.example&quot;&gt;", result)

    def test_unsafe_schemes_and_email_are_not_linkified(self):
        source = (
            "http://example.com javascript:alert(1) data:text/html,x "
            "file:///tmp/x //example.com user@example.com "
            "javascript:https://evil.example data:https://evil.example "
            "file:https://evil.example http://https://evil.example "
            "//https://evil.example"
        )
        result = str(render_dm_plaintext(source))

        self.assertEqual(result, source)
        self.assertNotIn("<a ", result)

    def test_malformed_https_urls_are_not_linkified(self):
        source = (
            "https:// https:///missing-host https://example..com/path "
            "https://-bad.example/path https://example.com:bad/path "
            "https://example.com/%ZZ https://user@example.com/path "
            "https://999.999.999.999/path embeddedhttps://example.com"
        )
        result = str(render_dm_plaintext(source))

        self.assertEqual(result, source)
        self.assertNotIn("<a ", result)

    def test_trailing_punctuation_is_excluded_from_link(self):
        result = str(
            render_dm_plaintext(
                "See https://example.com/docs, "
                "(https://example.org/path)."
            )
        )

        self.assertIn(
            'href="https://example.com/docs" target="_blank" '
            'rel="noopener noreferrer ugc">https://example.com/docs</a>,',
            result,
        )
        self.assertIn(
            '(<a href="https://example.org/path" target="_blank" '
            'rel="noopener noreferrer ugc">https://example.org/path</a>).',
            result,
        )

    def test_unicode_and_line_breaks_are_preserved(self):
        result = str(
            render_dm_plaintext(
                "Café 你好 https://example.com/über\r\nSecond line"
            )
        )

        self.assertEqual(
            result,
            'Café 你好 <a href="https://example.com/über" target="_blank" '
            'rel="noopener noreferrer ugc">https://example.com/über</a>'
            "<br>Second line",
        )

    def test_django_template_registration(self):
        template = Template(
            "{% load post_content %}"
            "{{ value|render_dm_plaintext }}"
        )

        rendered = template.render(
            Context({"value": "https://example.com"})
        )

        self.assertIn('href="https://example.com"', rendered)


class FanzPlaintextRenderingTests(SimpleTestCase):

    def test_html_tags_are_escaped(self):
        result = str(
            render_fanz_plaintext("<b>Hello</b>")
        )

        self.assertEqual(
            result,
            "&lt;b&gt;Hello&lt;/b&gt;",
        )

    def test_https_url_is_not_linkified(self):
        source = "Public comment https://example.com/path"

        self.assertEqual(
            str(render_fanz_plaintext(source)),
            source,
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
