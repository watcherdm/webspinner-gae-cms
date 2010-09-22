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

ACTIONS = ['view','edit']

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
  tags = db.StringListProperty()

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

