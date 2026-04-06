"""
"""
from kmarkup import parse
from kmarkup.renderers import to_html
from kmarkup.renderers import to_json

#from .renderers import to_html, to_json

a = parse("{foo `xyz`}")
#: kmarkup.ast.Document

print(a)
print(type(a))
print(a.to_dict())

print(to_html(a))

#).to_dict(),
