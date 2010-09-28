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
from main import *
import datetime
import time

SIMPLE_TYPES = (int, long, float, bool, dict, basestring)

def to_dict(model):
  output = {}

  for key, prop in model.properties().iteritems():
    value = getattr(model, key)

    if value is None or isinstance(value, SIMPLE_TYPES):
      output[key] = value
    elif isinstance(value, datetime.date):
        # Convert date/datetime to ms-since-epoch ("new Date()").
      ms = time.mktime(value.utctimetuple()) * 1000
      ms += getattr(value, 'microseconds', 0) / 1000
      output[key] = int(ms)
    elif isinstance(value, list):
      if len(value) < 1 or isinstance(value[0], SIMPLE_TYPES):
        output[key] = value
      else:
        sublist = []
        for v in value:
          m = db.get(v)
          sublist.append(to_dict(m))
        output[key] = sublist
    elif isinstance(value, db.Model):
      output[key] = to_dict(value)
    else:
      raise ValueError('cannot encode ' + repr(prop))

  return output

class WsModel(ROTModel):
  
  @classmethod
  def update(cls, dict_values):
    if "key" in dict_values:
      model = db.get(dict_values["key"])
      for key, property in model.properties().iteritems():
        if key in dict_values:
          fitype = property.__class__().__str__()
          if ".StringListProperty" in fitype:
            dict_values[key] = dict_values[key].split(",")
          elif ".BooleanProperty" in fitype:
            dict_values[key] = dict_values[key] != ""
          elif ".ReferenceProperty" in fitype:
            dict_values[key] = None if dict_values[key] == "None" else db.get(dict_values[key])
          elif ".ListProperty" in fitype:
            dict_values[key] = [object.key() for object in db.get(dict_values.split(","))]
          else:
            dict_values[key] = dict_values[key].lstrip().rstrip()
          setattr(model, key, dict_values[key])
      model.put()
      return model
    else:
      return None

ACTIONS = ['view','edit']

def string_to_tags(site, tags):
  result = list(set([x.lstrip().rstrip() for x in tags.split(",")]))
  site.tags.extend(result)
  site.put()
  return result

class Site(WsModel):
  """ Site is a wrapper class for all the site data."""
  admin = db.EmailProperty()
  title = db.StringProperty()
  actions = db.StringListProperty()
  description = db.StringProperty()
  keywords = db.StringListProperty()
  tags = db.StringListProperty()
  secret = db.StringProperty()
  pages = db.ListProperty(db.Key)
  roles = db.ListProperty(db.Key)
  images = db.ListProperty(db.Key)
  theme_packages = db.ListProperty(db.Key)
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
    page = Page.create({"name":"/","ancestor":None,"title":"Default Webspinner Page","menu_name":"Home","visible":True, "page_chain":"/","tags": site.tags})
    main_theme = Theme.create({"name": "default", "html":"""
<div class="wrapper">
  <div class="header"><h1>{{ page.title }}</h1></div>
  <div class="nav">{{ ws.get_nav_list }} {{ user_control_link }}</div>
  <div class="content">{% block section_main %}{% endblock %}</div>
  <div class="footer">Copyright 2010 Webspinner Inc.</div>
</div>
    ""","css":"""
body{background: #eee; color: #111; font-family: Helvetica, Arial, SanSerif;text-align: center;}
div.wrapper{display: block; margin-left: auto; margin-right: auto; width: 960px;}
div.header{padding: 20px; display: block; text-align: left; width: 960px; background: #333; float: left;}
div.header h1{color: #fff; text-shadow: 1px 1px 1px rgba(0,0,0,1);}
div.content{background: #fff; color: #111; display: block; float: left; width: 960px; padding: 20px; text-align: left;}
div.nav{width: 1000px; padding: 0px ; background: -webkit-gradient(linear,0 0, 0 100%, from(rgba(100,100,100,1)), to(rgba(180,180,180,1)));display: block; float: left;}
div.nav ul.site_menu{list-style-type: none; margin: 0px; padding: 0px;}
div.nav ul.site_menu li.menu_item{display: block; padding: 0px; float: left;}
div.nav ul.site_menu li.menu_item a.menu_item_link:link{display: block; float: left; padding: 9px 15px;text-decoration: none; color: #f0f0f0; font-weight: bolder; text-shadow: 0px 1px 1px rgba(0,0,0,.6);}
div.nav ul.site_menu li.menu_item a.menu_item_link:hover{text-decoration: none; color: #fff; font-weight: bolder; text-shadow: 0px 2px 1px rgba(0,0,0,.9);}
div.nav ul.site_menu li.menu_item a.menu_item_link:visited{text-decoration: none; color: #fff; font-weight: bolder; text-shadow: 0px 1px 1px rgba(0,0,0,.6);}
div.nav ul.site_menu li.menu_item a.menu_item_link:active{text-decoration: none; color: #fff; font-weight: bolder; text-shadow: 0px 1px 1px rgba(0,0,0,.9);}
div.footer{float: left; display: block; width: 960px; padding: 5px 20px; background: -webkit-gradient(linear,0 0, 0 100%, from(rgba(100,100,100,1)), to(rgba(180,180,180,1))); font-weight: bolder; color: rgba(255,255,255,1)}
    ""","js":""})
    page.theme = main_theme
    page.put()
    sections = page.get_or_make_sections()
    theme_packages = ThemePackage.create({"name":"default","themes":[main_theme.key()]})
    site.theme_packages.append(theme_packages.key())
    site.pages.append(page.key())
    site.put()
    admin = User.create_user(email, password, user)
    roles = Role.create_default()
    for role in roles:
      site.roles.append(role.key())
    Role.add_administrator(admin)
    site.put()
    perms = site.build_permissions()
    return site
  def actions_joined(self):
    return ", ".join(self.actions)
  def tags_joined(self):
    return ", ".join(self.tags)
  def keywords_joined(self):
    return ", ".join(self.keywords)

  @classmethod
  def export(cls, key):
    site = cls.get(key)
    return to_dict(site)

  def build_permissions(self):
    perm_set = []
    for action in self.actions:
      roles = db.get(self.roles)
      for role in roles:
        perm = Permission()
        perm.role = role
        perm.type = action
        perm.put()
        perm_set.append(perm)
    return perm_set
    
  def images_for_use(self):
    images = db.get(self.images)
    html_out = "<ul class='image_selector'>"
    for image in images:
      html_out += "<li><img src='/images/%s/s' title='%s' /></li>" % (image.name, image.title)
    html_out += "</ul>"
    return html_out
    
        
class Role(WsModel):
  """ Role defines the different available user roles"""
  name = db.StringProperty()
  users = db.ListProperty(db.Key)
  @classmethod
  def create_default(cls):
    roles_names = ['Anonymous','User','Administrator']
    roles = []
    for role in roles_names:
      new_role = cls()
      new_role.name = role
      new_role.put()
      roles.append(new_role)
    return roles
  @classmethod
  def add_administrator(cls, user):
    adminrole = cls.all().filter("name","Administrator").get()
    adminrole.users.append(user.key())
    adminrole.put()

class Permission(WsModel):
  """ Permission assigns an action type with a role and is used in content elements to associate a user with the actions he can take"""
  type = db.StringProperty()
  role = db.ReferenceProperty(Role)
  
  @classmethod
  def get_for_role(cls, role):
    return cls.all().filter("role",role).fetch(100)
  
  @classmethod
  def get_for_action(cls, action):
    return cls.all().filter("type", action).fetch(100)
  
  @classmethod
  def get_table(cls):
    roles = Role.all().fetch(100)
    site = Site.all().get()
    html_out = "<table><tr><td></td>"
    html_out += "".join(["<th>%s</th>" % action for action in site.actions])
    html_out += "</tr>"
    for role in roles:
      html_out += "<tr><th>%s</th>" % role.name
      html_out += "".join(["<td><input type='checkbox' name='page.permissions' id='page.permissions' value='%s'/></td>" % perm.key() for perm in cls.get_for_role(role)])
      html_out += "</tr>"
    html_out += "</table>"
    return html_out

class User(WsModel):   
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
  def create_user(cls, email, password, user = None):
    site_secret = Site.all().get().secret
    random_key = str(random())
    new_user = cls()
    new_user.email = email
    new_user.oauth = user
    new_user.password = sha256("%s%s%s" % (site_secret, random_key, password)).hexdigest()
    new_user.salt = random_key
    new_user.put()
    return new_user
    
class ThemePackage(WsModel):
  """ ThemePackage groups theme elements together for packaging and distribusion"""
  name = db.StringProperty()
  themes = db.ListProperty(db.Key)
  @classmethod
  def create(cls, dict_values):
    theme_package = cls()
    theme_package.name = dict_values["name"]
    theme_package.themes = dict_values["themes"]
    theme_package.put()
    return theme_package

class Theme(WsModel):
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
  @classmethod
  def update(cls, dict_values):
    theme = cls.get(dict_values["key"])
    if theme:
      theme.html = dict_values["html"]
      theme.css = dict_values["css"]
      theme.js = dict_values["js"]
      theme.put()
      pages = Page.all().filter("theme", theme).fetch(1000)
      for page in pages:
        sections = page.get_or_make_sections()
      return theme
    else:
      return None
    

class Page(WsModel):
  """ Page is a wrapper class for each logical page in the cms website
  """
  name = db.StringProperty()
  ancestor = db.SelfReferenceProperty()
  title = db.StringProperty()
  menu_name = db.StringProperty()
  theme = db.ReferenceProperty(Theme)
  sections = db.ListProperty(db.Key)
  permissions = db.ListProperty(db.Key)
  visible = db.BooleanProperty()
  tags = db.StringListProperty()
  page_chain = db.StringListProperty()
  @classmethod
  def create(cls, dict_values):
    mainpage = Page.all().get()
    page = cls()
    page.name = dict_values['name']
    if not dict_values['ancestor'] == "None"and not dict_values["ancestor"] == None:
      anc = Page.get_by_id(long(dict_values['ancestor']))
      page.ancestor = anc
    else:
      page.ancestor = None
    page.title = dict_values['title']
    page.menu_name = dict_values['menu_name']
    if "visible" in dict_values:
      page.visible = (dict_values['visible'] != "")
    page.tags = dict_values['tags']
    page.page_chain.append(dict_values["name"])
    if mainpage:
      page.theme = Theme.create({"name":page.name,"html":mainpage.theme.html, "css": mainpage.theme.css, "js": mainpage.theme.js})
    page.put()
    site = Site.all().get()
    if site:
      site.pages.append(page.key())
      site.put()
    return page

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
    sections = db.get(self.sections)
    for section in sections:
      blocks_expression = '{%% block %s %%}{%% endblock %%}' % section.name
      page_html = re.sub(blocks_expression, section.theme.html, page_html)
    return page_html
      
  def get_or_make_sections(self):
    blocks_expression = '{% block (section_[a-z]+) %}{% endblock %}'
    sections = re.findall(blocks_expression, self.theme.html)
    result = []
    for section in sections:
      is_section = Section.get_by_name(section)
      if is_section:
        if not is_section.key() in self.sections:
          self.sections.append(is_section.key())
        result.append(is_section)
      else:
        is_section = Section.create({"page":self.key(), "name": section})
        self.sections.append(is_section.key())
        result.append(is_section)
    self.put()
    return result
  

class Section(ROTModel):
  """ Section is a wrapper class for the each logical section in a page.
  """
  name = db.StringProperty()
  theme = db.ReferenceProperty(Theme)
  permissions = db.ListProperty(db.Key)
  visible = db.BooleanProperty()
  contents = db.ListProperty(db.Key)
  tags = db.StringListProperty()
  @classmethod
  def create(cls, dict_values):
    section = cls()
    page = db.get(dict_values["page"])
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
    section.add_content("Hello World!", "hi there")
    return section
    
  @classmethod
  def get_by_name(cls, name):
    result = cls.all().filter("name", name).fetch(1)
    if len(result) > 0:
      return result[0]
    else:
      return None

  def add_content(self, content, abstract, user = None, tags = None):
    content_object = Content()
    content_object.abstract = abstract
    content_object.content = content
    content_object.created_by_user = user
    if tags:
      content_object.tags = tags
    content_object.permissions = self.permissions
    content_object.visible = self.visible
    content_object.put()
    self.contents.append(content_object.key())
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
  @classmethod
  def update(cls, dict_values):
    content = cls.get(dict_values["key"])
    if content:
      content.content = dict_values["content"]
      content.put()
      return content
    else:
      return None
    
class Image(WsModel):
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
    site = Site.all().get()
    site.images.append(img.key())
    site.put()
    return img
