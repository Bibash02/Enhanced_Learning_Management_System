from django import template

register = template.Library()

@register.filter
def dict_key(d, key):
    """Return the value of a dict by key or None"""
    return d.get(key)
