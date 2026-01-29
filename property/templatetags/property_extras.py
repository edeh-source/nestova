from django import template
import re

register = template.Library()

@register.simple_tag(takes_context=True)
def url_replace(context, **kwargs):
    query = context['request'].GET.copy()
    for k, v in kwargs.items():
        query[k] = v
    return query.urlencode()

@register.filter(name='force_https')
def force_https(url):
    """Force URL to use HTTPS"""
    if url and url.startswith('http://'):
        return url.replace('http://', 'https://')
    return url

@register.filter(name='youtube_id')
def youtube_id(value):
    """Extract YouTube/Vimeo ID from URL"""
    if not value:
        return ""
    if hasattr(value, 'url'):
        value = value.url
    
    # Robust YouTube ID regex
    # Handles: watch?v=ID, youtu.be/ID, embed/ID, v/ID, shorts/ID
    yt_pattern = r'(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/|youtube\.com\/shorts\/)([^"&?\/ ]{11})'
    match = re.search(yt_pattern, str(value))
    if match:
        return match.group(1)
    
    # Check if value itself looks like an 11-char ID
    val_str = str(value).strip()
    if len(val_str) == 11 and re.match(r'^[a-zA-Z0-9_-]{11}$', val_str):
        return val_str
        
    return value