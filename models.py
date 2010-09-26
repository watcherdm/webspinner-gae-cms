#!/usr/env python

"""Models module for Webspinner GAE CMS"""

from appengine_utilities import sessions
from appengine_utilities import flash
from appengine_utilities import event
from appengine_utilities import cache
from appengine_utilities.rotmodel import ROTModel
from google.appengine.ext import db
from django.utils import simplejson
from hashlib import sha256
from random import random
import re

ACTIONS = ['view','edit']

def string_to_tags(site, tags):
  result = list(set([x.lstrip().rstrip() for x in tags.split(",")]))
  site.tags.extend(result)
  site.put()
  return result

class Site(ROTModel):
  """ Site is a wrapper class for all the site data."""
  admin = db.EmailProperty()
  title = db.StringProperty()
  actions = db.StringListProperty()
  description = db.StringProperty()
  keywords = db.StringListProperty()
  tags = db.StringListProperty()
  secret = db.StringProperty()
  @classmethod
  def create(cls, email, password, title, user = None):
    site = cls()
    site.admin = email
    site.title = title
    site.actions = ACTIONS
    site.description = "New Webspinner CMS install"
    site.keywords = ['webspinner inc.']
    site.tags = ['cms']
    site.secret = str(random())
    site.put()
    admin = User.create_user(email, password, user)
    Role.create_default()
    Role.add_administrator(admin)
    return site
  def actions_joined(self):
    return ", ".join(self.actions)
  def tags_joined(self):
    return ", ".join(self.tags)
  def keywords_joined(self):
    return ", ".join(self.keywords)
  @classmethod
  def export(cls, key, format):
    site = cls.get(key)
    
  
class Role(ROTModel):
  """ Role defines the different available user roles"""
  name = db.StringProperty()
  pages = db.ListProperty(db.Key)
  users = db.ListProperty(db.Key)
  @classmethod
  def create_default(cls):
    roles = ['Anonymous','User','Administrator']
    for role in roles:
      new_role = cls()
      new_role.name = role
      new_role.put()
  @classmethod
  def add_administrator(cls, user):
    adminrole = cls.all().filter("name","Administrator").get()
    adminrole.users.append(user.key())
    user.role = adminrole.key()
    user.put()

class Permission(ROTModel):
  """ Permission assigns an action type with a role and is used in content elements to associate a user with the actions he can take"""
  type = db.StringProperty()
  role = db.ReferenceProperty(Role)

class User(ROTModel):   
  """ User contains the user information necessary to login as well as profile data"""
  oauth = db.UserProperty()
  email = db.EmailProperty()
  password = db.StringProperty()
  salt = db.StringProperty()
  firstname = db.StringProperty()
  lastname = db.StringProperty()
  spouse = db.StringProperty()
  address = db.PostalAddressProperty()
  phone = db.PhoneNumberProperty()
  fax = db.PhoneNumberProperty()
  role = db.ReferenceProperty(Role)
  location = db.GeoPtProperty()
  url = db.LinkProperty()
  picture = db.BlobProperty()
  tags = db.StringListProperty()
  @classmethod
  def login(cls, email, password, site):
    user = cls.all().filter("email",email).get()
    random_key = user.salt
    site_secret = site.secret
    result = False if sha256("%s%s%s" % (site_secret, random_key, password)).hexdigest() != user.password else user.key()
    return result
  @classmethod
  def create_user(cls, email, password, role = None, user = None):
    site_secret = Site.all().get().secret
    random_key = str(random())
    new_user = cls()
    new_user.email = email
    new_user.oauth = user
    new_user.password = sha256("%s%s%s" % (site_secret, random_key, password)).hexdigest()
    new_user.salt = random_key
    new_user.role = role
    new_user.put()
    return new_user

class ThemePackage(ROTModel):
  """ ThemePackage groups theme elements together for packaging and distribusion"""
  name = db.StringProperty()
  themes = db.ListProperty(db.Key)

class Theme(ROTModel):
  """ Theme relieves the need for static file upload 
    Each theme element contains the complete html, css and js 
    for the space the element is intended to fill."""
  name = db.StringProperty()
  html = db.TextProperty()
  css = db.TextProperty()
  js = db.TextProperty()
  @classmethod
  def create(cls, dict_values):
    theme = cls()
    theme.name = dict_values["name"]
    theme.html = dict_values["html"]
    theme.css = dict_values["css"]
    theme.js = dict_values["js"]
    theme.put()
    return theme

class Page(ROTModel):
  """ Page is a wrapper class for each logical page in the cms website
  """
  name = db.StringProperty()
  ancestor = db.SelfReferenceProperty()
  site = db.ReferenceProperty(Site)
  title = db.StringProperty()
  menu_name = db.StringProperty()
  theme = db.ReferenceProperty(Theme)
  panels = db.StringListProperty()
  permissions = db.ListProperty(db.Key)
  visible = db.BooleanProperty()
  tags = db.StringListProperty()
  page_chain = db.StringListProperty()
  @classmethod
  def create(cls, dict_values):
    page = cls()
    page.name = dict_values['name']
    print 'ancestor' in dict_values
    if not dict_values['ancestor'] == "None":
      anc = Page.get_by_id(long(dict_values['ancestor']))
      page.ancestor = anc
    else:
      page.ancestor = None
    page.title = dict_values['title']
    page.menu_name = dict_values['menu_name']
    page.visible = (dict_values['visible'] != "")
    page.tags = dict_values['tags']
    page.page_chain.append(dict_values["name"])
    page.site = db.get(dict_values["site"])
    page.put()
    return page
  @classmethod
  def get_by_name(cls, name):
    return cls.all().filter("name", name).fetch(1)[0]
  @classmethod
  def get_by_page_chain(cls, page_chain):
    result = cls.all().filter("page_chain", page_chain).fetch(1)
    if len(result) > 0:
      return  result[0]
    else:
      return None
  def sections(self):
    result = {}
    for panel in self.panels:
      section = Section.get_by_name(panel)
      result[panel] = section
    return result
  def build_template(self):
    page_html = self.theme.html
    for panel in self.panels:
      section = Section.get_by_name(panel)
      blocks_expression = '{%% block %s %%}{%% endblock %%}' % panel
      page_html = re.sub(blocks_expression, section.theme.html, page_html)
    return page_html
      
  def get_or_make_sections(self):
    blocks_expression = '{% block (section_[a-z]+) %}{% endblock %}'
    sections = re.findall(blocks_expression, self.theme.html)
    self.panels = sections
    self.put()
    result = []
    for section in sections:
      is_section = Section.get_by_name(section)
      if is_section and is_section.page == self:
        result.append(is_section)
      else:
        is_section = Section()
        is_section.name = section
        is_section.page = self
        is_section.panel = section
        is_section.permissions = self.permissions
        is_section.visible = self.visible
        is_section.tags = self.tags
        is_section.put()
        result.append(is_section)
    return result

class Section(ROTModel):
  """ Section is a wrapper class for the each logical section in a page.
  """
  site = db.ReferenceProperty(Site)
  name = db.StringProperty()
  theme = db.ReferenceProperty(Theme)
  page = db.ReferenceProperty(Page)
  panel = db.StringProperty()
  permissions = db.ListProperty(db.Key)
  visible = db.BooleanProperty()
  contents = db.ListProperty(db.Key)
  tags = db.StringListProperty()
  @classmethod
  def get_by_name(cls, name):
    result = cls.all().filter("name", name).fetch(1)
    if len(result) > 0:
      return result[0]
    else:
      return None

  def add_content(self, content, abstract, user, tags):
    content_object = Content()
    content_object.section = self
    content_object.abstract = abstract
    content_object.content = content
    content_object.created_by_user = user
    content_object.tags = string_to_tags(self.site, tags)
    content_object.permissions = self.permissions
    content_object.visible = self.visible
    content_object.put()
    self.contents.append(content_object.key)
    self.put()
    return content_object
    
  def contents_by(self, method):
    contents = db.get(self.contents)
    return contents
  def contents_by_created(self):
    return self.contents_by("-date_created")

class Content(ROTModel):
  """ Content is a wrapper class for the content elements in a section.  
  """
  section = db.ReferenceProperty(Section)
  abstract = db.StringProperty()
  content = db.TextProperty()
  permissions = db.ListProperty(db.Key)
  date_created = db.DateTimeProperty(auto_now_add=True)
  date_modified = db.DateTimeProperty(auto_now = True)
  created_by_user = db.ReferenceProperty(User)
  visible = db.BooleanProperty()
  tags = db.StringListProperty()

class Image(ROTModel):
  """ Image is a wrapper class for the image elements in content """
  file = db.BlobProperty()
  title = db.StringProperty()
  name = db.StringProperty()
  tags = db.StringListProperty()
  @classmethod
  def get_by_name(cls, name):
    return cls.all().filter("name =", str(name)).fetch(1)[0]
  @classmethod
  def create(cls, dict_values):
    img = cls()
    img.file = dict_values["file"]
    img.title = dict_values["title"]
    img.name = str(random()).split('.')[-1]
    img.tags = dict_values['tags']
    img.put()
    return img
