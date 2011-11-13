#!/usr/env python

"""Models module for Webspinner GAE CMS"""

import re
from .base_model import WsModel
from .theme import Theme, ThemePackage
from .auth import User
import logging

def string_to_tags(site, tags):
  result = list(set([x.lstrip().rstrip() for x in tags.split(",")]))
  site.tags.extend(result)
  site.put()
  return result

class Page(WsModel):
  """ Page is a wrapper class for each logical page in the cms website
  """
  _relfields = [{"model":"Site","field":"pages","value":"key"}]
  _modfields = [{"name":"name","type":"text"},
    {"name":"ancestor","type":"select","list":"Page","list_val":"key","list_name":"title"},
    {"name":"title","type":"text"},
    {"name":"menu_name","type":"text"},
    {"name":"visible","type":"checkbox"},
    {"name":"tags","type":"textlist"},
    {"name":"keywords","type":"textlist"},
    {"name":"description","type":"textarea"},
  ]
  name = WsModel.db.StringProperty()
  ancestor = WsModel.db.SelfReferenceProperty()
  title = WsModel.db.StringProperty()
  keywords = WsModel.db.StringListProperty()
  description = WsModel.db.StringProperty()
  menu_name = WsModel.db.StringProperty()
  theme = WsModel.db.ReferenceProperty(Theme)
  sections = WsModel.db.ListProperty(WsModel.db.Key)
  permissions = WsModel.db.ListProperty(WsModel.db.Key)
  visible = WsModel.db.BooleanProperty()
  tags = WsModel.db.StringListProperty()
  page_chain = WsModel.db.StringListProperty()

  @classmethod
  def get_by_name(cls, name):
    result = cls.all().filter("name", name).fetch(1)
    if len(result) > 0:
      return result[0]
    else:
      return None


  @classmethod
  def get_by_page_chain(cls, page_chain):
    result = cls.all().filter("page_chain", page_chain).fetch(1)
    if len(result) > 0:
      return  result[0]
    else:
      return None
  @classmethod
  def get_by_page_name(cls, path):
    result = cls.all().filter("name", path).fetch(1)
    if len(result) > 0:
      return result[0]
    else:
      return None

  def build_template(self):
    page_html = self.theme.html
    sections = WsModel.db.get(self.sections)
    for section in sections:
      blocks_expression = '{%% block %s %%}{%% endblock %%}' % section.name
      page_html = re.sub(blocks_expression, section.theme.html, page_html)
    return page_html

  def get_or_make_sections(self):
    blocks_expression = '{% block (section_[a-z]+) %}{% endblock %}'
    sections = re.findall(blocks_expression, self.theme.html)
    result = []
    for section in sections:
      is_section = Section.create({"page":self.key(), "name": section})
      self.sections.append(is_section.key())
      result.append(is_section)
    self.put()
    return result
  
  def get_sections(self):
    return WsModel.db.get(self.sections)
WsModel.Page = Page

class Section(WsModel):
  """ Section is a wrapper class for the each logical section in a page.
  """
  _relfields = [{"model":"Page","field":"sections","value":"key"}]
  _modfields = [{"name":"name","type":"text"},
    {"name":"theme","type":"select","list":"Theme","list_val":"key","list_name":"name"},
    {"name":"visible","type":"checkbox"},
    {"name":"tags","type":"textlist"}]
  name = WsModel.db.StringProperty()
  theme = WsModel.db.ReferenceProperty(Theme)
  permissions = WsModel.db.ListProperty(WsModel.db.Key)
  visible = WsModel.db.BooleanProperty()
  contents = WsModel.db.ListProperty(WsModel.db.Key)
  tags = WsModel.db.StringListProperty()
  @classmethod
  def create(cls, dict_values):
    section = cls()
    page = WsModel.db.get(dict_values["page"])
    section.name = dict_values["name"]
    section.permissions = page.permissions
    section.visible = page.visible
    section.tags = page.tags
    section.theme = Theme.create({"name":"default_section", "html":"""
<div class="%s">
  {%% for content in sections.%s.contents_by_created %%}
    {{ content.content }}
  {%% endfor %%}
</div>
    """ % (section.name, section.name), "css":"","js":""})
    theme_packages = ThemePackage.all().fetch(1000)
    for theme_package in theme_packages:
      if page.theme.key() in theme_package.themes:
        theme_package.themes.append(section.theme.key())
        theme_package.put()
    content = Content.create({
      "title":["Hello World"],
      "abstract":["hi there"],
      "content":["If you are logged in as an administrator use the menu on the left to modify the page and it's contents."],
      "visible":["on"],
      "tags":"cms"
    })
    section.add_content(content.key())
    return section

  @classmethod
  def get_by_name(cls, name):
    result = cls.all().filter("name", name).fetch(1)
    if len(result) > 0:
      return result[0]
    else:
      return None

  def add_content(self, content_key):
    logging.info('Content add called %s' % content_key)
    self.contents.append(content_key)
    self.put()
    return content_key

  def contents_by_created(self):
    return self.__class__.get_newest(self.contents)
  
  def get_contents(self):
    return WsModel.db.get(self.contents)
WsModel.Section = Section
class Content(WsModel):
  """ Content is a wrapper class for the content elements in a section.
  """
  _relfields = [{"model": "Section","field":"contents","value":"key","method":"add_content"}]
  _modfields = [{"name":"title","type":"text"},
    {"name":"abstract","type":"textarea"},
    {"name":"content","type":"textareahtml"},
    {"name":"visible","type":"checkbox"},
    {"name":"tags","type":"textlist"}]
  title = WsModel.db.StringProperty()
  abstract = WsModel.db.StringProperty()
  content = WsModel.db.TextProperty()
  permissions = WsModel.db.ListProperty(WsModel.db.Key)
  date_created = WsModel.db.DateTimeProperty(auto_now_add=True)
  date_modified = WsModel.db.DateTimeProperty(auto_now = True)
  created_by_user = WsModel.db.ReferenceProperty(User)
  visible = WsModel.db.BooleanProperty()
  tags = WsModel.db.StringListProperty()
WsModel.Content = Content