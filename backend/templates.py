"""Common place for jinja2 template stuff."""

import jinja2

JINJA_ENVIRONMENT = jinja2.Environment(
  loader=jinja2.FileSystemLoader('templates/'),
  extensions=['jinja2.ext.autoescape'],
  autoescape=True)

def GetTemplate(template_name):
  return JINJA_ENVIRONMENT.get_template(template_name)

def _FormatCents(value):
    return "${:,.2f}".format(value / 100.0)

JINJA_ENVIRONMENT.filters.update(dict(formatCents=_FormatCents))
