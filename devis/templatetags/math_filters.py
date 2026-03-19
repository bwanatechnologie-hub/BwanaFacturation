# devis/templatetags/math_filters.py
from django import template

register = template.Library()

@register.filter
def multiply(value, arg):
    """Multiplie value par arg"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def divide(value, arg):
    """Divise value par arg"""
    try:
        return float(value) / float(arg)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0

@register.filter
def add(value, arg):
    """Additionne value et arg"""
    try:
        return float(value) + float(arg)
    except (ValueError, TypeError):
        return 0