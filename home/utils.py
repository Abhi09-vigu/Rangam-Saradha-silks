import re
import urllib.parse
import urllib.request
from django.core.exceptions import ValidationError

ALLOWED_GOOGLE_MAPS_HOSTS = (
    'www.google.com',
    'maps.google.com',
    'google.com',
    'maps.app.goo.gl',
    'goo.gl',
)

def sanitize_and_format_google_map(input_text):
    """
    Sanitizes and converts Google Maps iframe code or Google Maps URL into a secure,
    responsive Google Maps <iframe> HTML string.
    """
    if not input_text or not input_text.strip():
        return ""

    text = input_text.strip()

    # 1. Check if full iframe HTML code is provided
    src_match = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', text, re.IGNORECASE)
    if src_match:
        url = src_match.group(1).strip()
    else:
        # Extract raw URL from text
        url_match = re.search(r'https?://[^\s"<>\']+', text, re.IGNORECASE)
        if url_match:
            url = url_match.group(0).strip()
        else:
            raise ValidationError("Invalid Google Maps code or URL. Please paste the full iframe embed code or map URL from Google Maps.")

    # 2. Validate URL structure & scheme
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        raise ValidationError("Invalid URL format in Google Maps embed code.")

    if parsed.scheme.lower() not in ('http', 'https'):
        raise ValidationError("Google Maps URL must use HTTPS.")

    host = parsed.netloc.lower().split(':')[0]
    is_allowed = any(host == allowed or host.endswith('.' + allowed) for allowed in ALLOWED_GOOGLE_MAPS_HOSTS)
    if not is_allowed:
        raise ValidationError("Only official Google Maps embed codes or URLs (google.com, maps.google.com, maps.app.goo.gl) are allowed.")

    embed_src = None

    # If it's already an official embed URL (/maps/embed?pb=...)
    if '/maps/embed' in parsed.path and 'pb=' in parsed.query:
        embed_src = url
    else:
        # Resolve short URL if needed
        final_url = url
        if 'goo.gl' in host:
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    final_url = resp.geturl()
            except Exception:
                pass

        # Extract place info, FTID, and coordinates
        ftid_match = re.search(r'1s(0x[0-9a-fA-F]+:0x[0-9a-fA-F]+)', final_url)
        coords_match = re.search(r'@(-?\d+\.\d+),(-?\d+\.\d+)', final_url) or re.search(r'!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)', final_url)
        place_match = re.search(r'/place/([^/@?]+)', final_url)

        lat = coords_match.group(1) if coords_match else "14.4179758"
        lng = coords_match.group(2) if coords_match else "77.7133326"
        place_name = urllib.parse.unquote(place_match.group(1)).replace('+', ' ') if place_match else "Rangam Saradha Silks"

        if ftid_match:
            ftid = ftid_match.group(1)
            encoded_place = urllib.parse.quote(place_name)
            pb = f"!1m18!1m12!1m3!1d3890.354!2d{lng}!3d{lat}!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s{ftid}!2s{encoded_place}!5e0!3m2!1sen!2sin!4v1700000000000!5m2!1sen!2sin"
            embed_src = f"https://www.google.com/maps/embed?pb={pb}"
        elif coords_match:
            embed_src = f"https://maps.google.com/maps?q={lat},{lng}&z=16&output=embed"
        else:
            embed_src = f"https://maps.google.com/maps?q={urllib.parse.quote(place_name)}&z=16&output=embed"

    if embed_src.startswith('http://'):
        embed_src = 'https://' + embed_src[7:]

    # 3. Return responsive <iframe> HTML string with 300px height
    sanitized_iframe = (
        f'<iframe src="{embed_src}" '
        f'width="100%" height="300" style="border:0;" '
        f'allowfullscreen="" loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe>'
    )

    return sanitized_iframe
