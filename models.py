#!/usr/env python

"""Models module for Webspinner GAE CMS"""

from appengine_utilities import sessions
from appengine_utilities import flash
from appengine_utilities import event
from appengine_utilities import cache
from appengine_utilities.rotmodel import ROTModel
from google.appengine.ext import db
from google.appengine.api import mail
from django.utils import simplejson
from hashlib import sha256
from random import random
import re
from main import *
import datetime
import time

SIMPLE_TYPES = (int, long, float, bool, dict, basestring)
wysiwyg_plugin = "tinymce"
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
  _relfields = []
  _modfields = []
  @classmethod
  def update(cls, dict_values):
    if "key" in dict_values:
      model = db.get("".join(dict_values["key"]))
      for key, property in model.properties().iteritems():
        if key in dict_values:
          fitype = property.__class__.__str__(property)
          if ".StringListProperty" in fitype:
            dict_values[key] = [x.lstrip().rstrip() for x in "".join(dict_values[key]).split(",")]
          elif ".BooleanProperty" in fitype:
            dict_values[key] = "".join(dict_values[key]) != ""
          elif ".ReferenceProperty" in fitype:
            dict_values[key] = None if "".join(dict_values[key]) == "None" else db.get(dict_values[key])
          elif ".ListProperty" in fitype:
            dict_values[key] = [object.key() for object in db.get(dict_values[key])]
          else:
            dict_values[key] = "".join(dict_values[key])
          if dict_values[key]:
            setattr(model, key, dict_values[key])
      model.put()
      if len(model._relfields) > 0:
        name = model._relfields[0]["model"].lower() + "." + model._relfields[0]["value"].lower()
        if name in dict_values:
          if model._relfields[0]["model"] in globals():
            model_to = globals()[model._relfields[0]["model"]].get(dict_values[name])
            if model_to and len(model_to) > 0:
              if model._relfields[0]["field"] in model_to[0].properties():
                if ".ListProperty" in model_to[0].properties()[model._relfields[0]["field"]].__str__():
                  list_model_keys = getattr(model_to[0], model._relfields[0]["field"])
                  list_model_keys.append(model.key())
                  list_model_keys = list(set(list_model_keys))
                  setattr(model_to[0], model._relfields[0]["field"], list_model_keys)
                else:
                  setattr(model_to[0], model._relfields[0]["field"], model)
                model_to[0].put()
      if(cls.__name__ == "Page"):
        memcache.delete("site-pages")
      return model
    else:
      return None

  @classmethod
  def create(cls, dict_values):
    model = cls()
    for key in dict_values:
      if key in cls.properties():
        fitype = cls.properties()[key].__str__()
        if ".StringListProperty" in fitype:
          dict_values[key] = [x.lstrip().rstrip() for x in "".join(dict_values[key]).split(",")]
        elif ".BooleanProperty" in fitype:
          dict_values[key] = dict_values[key] != ""
        elif ".ReferenceProperty" in fitype:
          dict_values[key] = None if "".join(dict_values[key]) == "None" else db.get(dict_values[key])
        elif ".ListProperty" in fitype:
          dict_values[key] = [object.key() for object in db.get("".join(dict_values[key]).split(","))]
        else:
          dict_values[key] = "".join(dict_values[key])
        setattr(model, key, dict_values[key])
    model.put()
    if len(model._relfields) > 0:
      name = model._relfields[0]["model"].lower() + "." + model._relfields[0]["value"].lower()
      if name in dict_values:
        if model._relfields[0]["model"] in globals():
          model_to = globals()[model._relfields[0]["model"]].get(dict_values[name])
          if model_to:
            if model._relfields[0]["field"] in model_to.properties():
              if ".ListProperty" in model_to.properties()[model._relfields[0]["field"]].__str__():
                list_model_keys = getattr(model_to, model._relfields[0]["field"])
                list_model_keys.append(model.key())
                list_model_keys = list(set(list_model_keys))
                setattr(model_to, model._relfields[0]["field"], list_model_keys)
              else:
                setattr(model_to, model._relfields[0]["field"], model)
              model_to.put()
    
    if(cls.__name__ == "Page"):
      memcache.delete("site-pages")
    return model

  @classmethod
  def to_edit_list(cls, display_field_name = "name", return_url = "/"):
    models = cls.all().fetch(1000)
    html_out = "<br />".join(["<a href='/admin/edit/%s/%s?return_url=%s'>%s</a>" % (cls.__name__.lower(), model.key(), return_url,getattr(model, display_field_name)) for model in models])
    return html_out

  @classmethod
  def to_form(cls, return_url, mode = "add", model_key = None, rel_key = None):
    html_out = ""
    if model_key:
      model = cls.get(model_key)
      html_out += "<form action='/admin/%s/%s/%s?return_url=%s' method='post'>" % (mode, cls.__name__.lower(), model_key, return_url)
    else:
      model = cls()
      html_out += "<form action='/admin/%s/%s?return_url=%s' method='post'>" % (mode, cls.__name__.lower(), return_url)
    if rel_key and len(model._relfields) > 0:
      name = model._relfields[0]["model"].lower() + "." + model._relfields[0]["value"].lower()
      html_out += "<input type='hidden' value='%s' name='%s' id='%s' />" % (rel_key, name, name)
    for field in model._modfields:
      key = field["name"]
      type = field["type"]
      if key in model.properties():
        finame = cls.__name__.lower() + "." + key
        html_out += "<label for'%s'>%s</label>" % (finame, cls.__name__ + " " + key.capitalize() + ":")
        textfields = ["text","email","password","url","tel"]
        value = getattr(model, key)
        value = value if value != None else ""
        if type in textfields:
          html_out += "<input type='%s' id='%s' name='%s' value='%s' />" % (type, finame, finame, value)
        elif type == "textlist":
          value = ", ".join(value)
          html_out += "<input type='%s' id='%s' name='%s' value='%s' />" % ("text", finame, finame, value)
        elif type == "textarea":
          html_out += "<textarea name='%s' id='%s'>%s</textarea>" % (finame,finame, value)
        elif type == "textareahtml":
          html_out += "<textarea name='%s' id='%s' class='%s'>%s</textarea>" % (finame,finame, wysiwyg_plugin, value)
        elif type == "select":
          if "list" in field:
            if field["list"] in globals():
              object_type = globals()[field["list"]]
              objects = object_type.all().fetch(1000)
              def build_option(object):
                if model.is_saved():
                  if object.key() == model.key():
                    return ""
                in_val = ""
                if field["list_val"] == "key":
                  selected = " selected " if object == value else ""
                  in_val = object.key()
                else:
                  selected = " selected " if getattr(object, field["list_val"]) == value else ""
                  in_val = getattr(object, field["list_val"])
                option_out = "<option value='%s' %s>%s</option>" % (in_val, selected, getattr(object, field["list_name"]))
                return option_out
              if field["list_name"] in object_type.properties():
                html_out += "<select name='%s' id='%s'>%s</select>" % (finame, finame, "<option value='None'>-- None --</option>" + "".join(map(build_option, objects)))
              else:
                html_out += "<select name='%s' id='%s'>%s</select>" % (finame, finame, ["<option value='%s'>%s</option>" % (object.key(), object.key().id()) for object in objects])
            else:
              html_out += "<select name='%s' id='%s'>%s</select>" % (finame, finame, "".join(["<option value='%s'>%s</option>" % (x, x) for x in value.split(",")]))
        elif type == "checkbox":
          checked = " checked " if value else ""
          html_out += "<input type='%s' name='%s' id='%s' %s />" % (type, finame, finame, checked)
        else:
          html_out += "<input type='%s' id='%s' name='%s' value='%s' />" % (model._modfields[key], finame, finame, value)
      html_out += "<br />"
    html_out += "<input type='submit' name='%s.submit' id='%s.submit' value='Save' /></form>" % (cls.__name__.lower(), cls.__name__.lower())
    return html_out

  @classmethod
  def get_order_by_field(cls,keys = None, field = None, direction = "ASC"):
    models = []
    if keys is None:
      models = cls().all().fetch(10000)
    else:
      models = db.get(keys)
    if field in models[0].properties():
      direction = True if direction == "DESC" else False
      models = sorted(models, key = lambda model: getattr(model, field), reverse = direction)
    return models

  @classmethod
  def get_newest(cls, keys = None):
    return cls.get_order_by_field(keys, "date_created", "DESC")


ACTIONS = ['view','edit']

def string_to_tags(site, tags):
  result = list(set([x.lstrip().rstrip() for x in tags.split(",")]))
  site.tags.extend(result)
  site.put()
  return result

class Site(WsModel):
  """ Site is a wrapper class for all the site data."""
  _modfields = [
    {"name":"admin","type":"email"},
    {"name":"keywords","type":"textlist"},
    {"name":"description","type":"email"},
    {"name":"tags","type":"textlist"}
  ]
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
  def get_secret(cls):
    secret = memcache.get("site_secret")
    if secret:
      return secret
    else:
      secret = cls.all().get().secret
      if secret:
        memcache.set("site_secret", secret)
        return secret
      else:
        return False
  @classmethod
  def get_title(cls):
    title = memcache.get("site_title")
    if title:
      return title
    else:
      title = cls.all().get().title
      if title:
        memcache.set("site_title", title)
        return title
      else:
        return False
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
    page = Page.create({"name":["/"],"ancestor":["None"],"title":["Default Webspinner Page"],"menu_name":["Home"],"visible":[True], "page_chain":"/","tags": site.tags})
    main_theme = Theme.create({"name": ["default"], "html":["""
<div class="wrapper">
  <div class="header"><h1>{{ page.title }}</h1></div>
  <div class="nav">{{ ws.get_nav_list }} {{ user_control_link }}</div>
  <div class="content">{% block section_main %}{% endblock %}</div>
  <div class="footer">Copyright 2010 Webspinner Inc.</div>
</div>
    """],"css":["""
body{background: #eee; color: #111; font-family: Helvetica, Arial, SanSerif;text-align: center;}
div.wrapper{display: block; margin-left: auto; margin-right: auto; width: 960px;}
div.header{
border-top-left-radius: 20px; border-top-right-radius: 20px;
padding: 20px; display: block; text-align: left; width: 960px; background: #333; float: left;}
div.header h1{color: #fff; text-shadow: 1px 1px 1px rgba(0,0,0,1);}
div.content{background: #fff; color: #111; display: block; float: left; width: 960px; padding: 20px; text-align: left;}
div.nav{width: 1000px; padding: 0px ; background: -webkit-gradient(linear,0 0, 0 100%, from(rgba(100,100,100,1)), to(rgba(180,180,180,1)));display: block; float: left;}
div.nav ul.site_menu{list-style-type: none; margin: 0px; padding: 0px;}
div.nav ul.site_menu li.menu_item{display: block; padding: 0px; float: left;}
div.nav ul.site_menu li.menu_item a.menu_item_link:link{display: block; float: left; padding: 9px 15px;text-decoration: none; color: #f0f0f0; font-weight: bolder; text-shadow: 0px 1px 1px rgba(0,0,0,.6);}
div.nav ul.site_menu li.menu_item a.menu_item_link:hover{text-decoration: none; color: #fff; font-weight: bolder; text-shadow: 0px 2px 1px rgba(0,0,0,.9);}
div.nav ul.site_menu li.menu_item a.menu_item_link:visited{text-decoration: none; color: #fff; font-weight: bolder; text-shadow: 0px 1px 1px rgba(0,0,0,.6);}
div.nav ul.site_menu li.menu_item a.menu_item_link:active{text-decoration: none; color: #fff; font-weight: bolder; text-shadow: 0px 1px 1px rgba(0,0,0,.9);}
div.footer{float: left; display: block; width: 960px; padding: 5px 20px; background: -webkit-gradient(linear,0 0, 0 100%, from(rgba(100,100,100,1)), to(rgba(180,180,180,1))); font-weight: bolder; color: rgba(255,255,255,1);border-bottom-left-radius: 20px;border-bottom-right-radius: 20px;}
div.nav>a:link{display: block; float: right; padding: 9px 15px;text-decoration: none; color: #f0f0f0; font-weight: bolder; text-shadow: 0px 1px 1px rgba(0,0,0,.6);}
div.nav>a:active{display: block; float: right; padding: 9px 15px;text-decoration: none; color: #f0f0f0; font-weight: bolder; text-shadow: 0px 1px 1px rgba(0,0,0,.6);}
div.nav>a:hover{display: block; float: right; padding: 9px 15px;text-decoration: none; color: #f0f0f0; font-weight: bolder; text-shadow: 0px 1px 1px rgba(0,0,0,.6);}
div.nav>a:visited{display: block; float: right; padding: 9px 15px;text-decoration: none; color: #f0f0f0; font-weight: bolder; text-shadow: 0px 1px 1px rgba(0,0,0,.6);}
    """],"js":["""
if(!window.cms){
  cms = (function(window,document,undefined){
    return {
      test: function(){console.log("Hello CMS World!");}
    }
  })(window, window.document);
}
    """]})
    page.theme = main_theme
    page.put()
    sections = page.get_or_make_sections()
    theme_packages = ThemePackage.create({"name":["default"],"themes":[",".join([str(main_theme.key())])]})
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
  def get_table(cls, page_key = None):
    roles = Role.all().fetch(100)
    site = Site.all().get()
    html_out = "<table><tr><td></td>"
    html_out += "".join(["<th>%s</th>" % action for action in site.actions])
    html_out += "</tr>"
    if page_key:
      page = db.get(page_key)
    else:
      page = {}
    for role in roles:
      html_out += "<tr><th>%s</th>" % role.name
      for perm in cls.get_for_role(role):
        checked = perm.key() in page.permissions if page else False
        checked = "checked" if checked else " "
        html_out += "<td><input type='checkbox' name='page.permissions' id='page.permissions' value='%s' %s /></td>" % (perm.key(), checked)
      html_out += "</tr>"
    html_out += "</table>"
    return html_out

class User(WsModel):
  """ User contains the user information necessary to login as well as profile data"""
  _modfields = [{'name':"email", 'type':"email"},
    {'name':"firstname",'type':"text"},
    {"name":"lastname","type":"text"},
    {"name":"spouse","type":"text"},
    {"name":"address","type":"textarea"},
    {"name":"phone","type":"tel"},
    {"name":"fax","type":"tel"},
    {"name":"url","type":"url"},
    {"name":"tags","type":"textlist"}]
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
  def get_by_email(cls, email):
    """Returns the user with the passed in email address."""
    user = cls.all().filter("email",email).get()
    if user:
      return user
    else:
      return False
      
  @classmethod
  def login(cls, email, password, site):
    user = cls.all().filter("email",email).get()
    if not user:
      return False
    random_key = user.salt
    site_secret = site.secret
    result = False if sha256("%s%s%s" % (site_secret, random_key, password)).hexdigest() != user.password else user.key()
    return result

  @classmethod
  def create_user(cls, email, password, user = None):
    site_secret = Site.get_secret()
    random_key = str(random())
    new_user = cls()
    new_user.email = email
    new_user.oauth = user
    new_user.password = sha256("%s%s%s" % (site_secret, random_key, password)).hexdigest()
    new_user.salt = random_key
    new_user.put()
    return new_user
  
  @classmethod
  def send_recovery_email(cls, user_email):
    link = cls.generate_recovery_link(user_email)
    user = User.get_by_email(user_email)
    if not link:
      return False
    if not user:
      return False
    mail.send_mail(sender="IAOS.net website <info@iaos.net>",
      to = "%s %s <%s>" % (user.firstname, user.lastname, user.email),
      subject = "%s : User Password Reset" % Site.get_title(),
      body = """Dear %s %s,
      
      Please click the following link to reset your password:
%s
If you did not request the reset of this password you can safely ignore this message. 
If you do not have a password for this website but you are a member of the Irish 
American Orthopaedic Society then please come to the website and set your password.

Regards,
IAOS.net""" % (user.firstname, user.lastname, link))
    return True
  
  @classmethod
  def generate_recovery_link(cls, user_email):
    code = VerificationToken.create_token(user_email)
    if code:
      return "<a href='http://www.iaos.net/pwrecovery/%s'>Click Here to Reset Your Password</a>"%code
    return False
  
  def destroy_token(self):
    token = VerificationToken.get_by_user(self)
    if token:
      token.delete()
      return True
    else:
      return False
  
  def set_password(self, password):
    """ set_password is a instance method to set the password for a user. If there is no salt currently set it will be generated randomly. """
    site_secret = Site.get_secret()
    if not self.salt:
      self.salt = str(random())
    if password:
      self.password = sha256("%s%s%s" % (site_secret, self.salt, password)).hexdigest()
      self.put()
      return True
    else:
      return False

class ThemePackage(WsModel):
  """ ThemePackage groups theme elements together for packaging and distribusion"""
  _modfields = [{"name":"name","type":"text"},
    {"name":"themes","type":"selectmulti","list":"Theme","list_val":"key","list_name":"name"}]
  name = db.StringProperty()
  themes = db.ListProperty(db.Key)
  @classmethod
  def old_create(cls, dict_values):
    theme_package = cls()
    theme_package.name = "".join(dict_values["name"])
    theme_package.themes = dict_values["themes"]
    theme_package.put()
    return theme_package

class Theme(WsModel):
  """ Theme relieves the need for static file upload
    Each theme element contains the complete html, css and js
    for the space the element is intended to fill."""
  _relfields = [{"model":"Page","field":"theme","value":"key"}]
  _modfields = [{"name":"name","type":"text"},
    {"name":"html","type":"textareahtml"},
    {"name":"css","type":"textarea"},
    {"name":"js","type":"textarea"}]
  name = db.StringProperty()
  html = db.TextProperty()
  css = db.TextProperty()
  js = db.TextProperty()

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
  name = db.StringProperty()
  ancestor = db.SelfReferenceProperty()
  title = db.StringProperty()
  keywords = db.StringListProperty()
  description = db.StringProperty()
  menu_name = db.StringProperty()
  theme = db.ReferenceProperty(Theme)
  sections = db.ListProperty(db.Key)
  permissions = db.ListProperty(db.Key)
  visible = db.BooleanProperty()
  tags = db.StringListProperty()
  page_chain = db.StringListProperty()
  @classmethod
  def old_create(cls, dict_values):
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
      is_section = Section.create({"page":self.key(), "name": section})
      self.sections.append(is_section.key())
      result.append(is_section)
    self.put()
    return result


class Section(WsModel):
  """ Section is a wrapper class for the each logical section in a page.
  """
  _relfields = [{"model":"Page","field":"sections","value":"key"}]
  _modfields = [{"name":"name","type":"text"},
    {"name":"theme","type":"select","list":"Theme","list_val":"key","list_name":"name"},
    {"name":"visible","type":"checkbox"},
    {"name":"tags","type":"textlist"}]
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
    content = Content.create({"title":["Hello World"],
      "abstract":["hi there"],
      "content":["If you are logged in as an administratir use the menu on the left to modify the page and it's contents."],
      "visible":["on"],
      "tags":"cms"})
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
    self.contents.append(content_key)
    self.put()
    return content_key

  def contents_by_created(self):
    return self.__class__.get_newest(self.contents)

class Content(WsModel):
  """ Content is a wrapper class for the content elements in a section.
  """
  _relfields = [{"model":"Section","field":"contents","value":"key","method":"add_content"}]
  _modfields = [{"name":"title","type":"text"},
    {"name":"abstract","type":"textarea"},
    {"name":"content","type":"textareahtml"},
    {"name":"visible","type":"checkbox"},
    {"name":"tags","type":"textlist"}]
  title = db.StringProperty()
  abstract = db.StringProperty()
  content = db.TextProperty()
  permissions = db.ListProperty(db.Key)
  date_created = db.DateTimeProperty(auto_now_add=True)
  date_modified = db.DateTimeProperty(auto_now = True)
  created_by_user = db.ReferenceProperty(User)
  visible = db.BooleanProperty()
  tags = db.StringListProperty()

class Image(WsModel):
  """ Image is a wrapper class for the image elements in content """
  file = db.BlobProperty()
  title = db.StringProperty()
  name = db.StringProperty()
  tags = db.StringListProperty()
  def to_url(self):
    return "/images/%s/s" % self.name
  @classmethod
  def get_by_name(cls, name):
    return cls.all().filter("name =", str(name)).fetch(1)[0]
  @classmethod
  def create(cls, dict_values):
    img = cls()
    img.file = "".join(dict_values["file"])
    img.title = "".join(dict_values["title"])
    img.name = str(random()).split('.')[-1]
    img.tags = [x.lstrip().rstrip() for x in "".join(dict_values['tags']).split(",")]
    img.put()
    site = Site.all().get()
    site.images.append(img.key())
    site.put()
    return img
class VerificationToken(WsModel):
  """ Verification token to allow users to reset password """
  user = db.ReferenceProperty(User)
  code = db.StringProperty()
  @classmethod
  def create_token(cls, user_email):
    user = User.get_by_email(user_email)
    if user:
      token = cls.all().filter('user',user).get()
      if token:
        return token.code
      token = cls()
      code = sha256("%s%s"%(user_email, datetime.datetime.now().isoformat("-"))).hexdigest()
      if code:
        token.user = user
        token.code = code
        token.put()
        return code
      else:
        return False
    else:
      return False

  @classmethod
  def get_by_code(cls, code):
    if code[0] == '/':
      code = code[1:]
    token = cls.all().filter('code', code).get()
    if token:
      return token.user
    return False

  @classmethod
  def get_by_user(cls, user):
    if user:
      token = cls.all().filter('user',user).get()
      if token:
        return token
      else:
        return False
    else:
      return False