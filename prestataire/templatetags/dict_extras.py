from django import template

register = template.Library()

@register.filter
def get_item(d, key):
    """
    Permet d'accéder à un dict dans un template:
    {{ mydict|get_item:mykey }}
    """
    if d is None:
        return None
    return d.get(key)
