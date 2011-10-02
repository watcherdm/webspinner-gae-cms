from google.appengine.ext import webapp
from appengine_utilities import sessions
from models import Site, User, Role
from django.utils import simplejson
from google.appengine.ext.webapp import template
import logging
from google.appengine.ext import db
from google.appengine.api import memcache

class Webspinner():
  def __init__(self, handler):
    site = memcache.get("site")
    if site:
      self.site = site
    else:
      site = Site.all().get()
      memcache.set("site", site)
      self.site = site
    self.handler = handler

  def get_nav_list(self):
    cuser = self.users.get_current_user(self.handler)
    if cuser:
      user_role = cuser.roles()
      logging.info(user_role)
    else:
      user_role = "Anonymous"
    html_out = memcache.get("menu_%s" % user_role )
    if html_out:
      return html_out
    html_out = "<ul class='site_menu'>"
    pages = memcache.get('site-pages')
    if not pages :
        pages = db.get(self.site.pages)
        memcache.set('site-pages', pages)
    def top_level(page):
      if not page.ancestor:
        return True
      else:
        return False
    def add_page_to_menu(page, html_out):
      html_out += "<li class='menu_item'><a href='%s' class='menu_item_link'>%s</a>" % (page.name, page.menu_name)
      children = filter(lambda x: x.ancestor == page, pages)
      if children:
        html_out += "<ul>"
        for p in children:
          add_page_to_menu(p)
        html_out += "</ul>"
      html_out += "</li>"
      return html_out
    top_level_pages = filter(top_level, pages)
    for page in top_level_pages:
      if self.handler.permission_check(page):
        html_out = add_page_to_menu(page, html_out)
    html_out += "</ul>"
    memcache.set("menu_%s" % user_role, html_out)
    return html_out

  class users:
    @classmethod
    def get_current_user(cls, handler):
      if 'user' in handler.session:
        user = User.get(handler.session['user'])
        return user
      else:
        return None

    @classmethod
    def is_current_user_admin(cls, handler):
      if u'user' in handler.session:
        user = User.get(handler.session['user'])
        role = Role.all().filter("name", "Administrator").get()
        if user.key() in role.users:
          return True
        else:
          return False
      else:
        return False

    @classmethod
    def create_login_url(ws, return_page):
      return "/login?return_url=%s" % return_page
    @classmethod
    def create_logout_url(ws, return_page):
      return "/logout?return_url=%s" %return_page

class Handler(webapp.RequestHandler):
  def __init__(self):
    self.ws = Webspinner(self)
    self.session = sessions.Session()
    self.actions = []
    
  def json_out(self, data):
    self.response.headers.add_header("Content-Type","application/json")
    self.response.out.write(simplejson.dumps(data))
  def render_out(self, template_file, values = {}):
    self.response.out.write(template.render(template_file,values))
  def render_string_out(self, template_object, template_values):
    context = template.Context(template_values)
    self.response.out.write(template_object.render(context))
  def permission_check(self, page):
    perms = db.get(page.permissions)
    anonrole = Role.all().filter("name", "Anonymous").get()
    if perms:
      user = self.ws.users.get_current_user(self)
      if not user:
        return False
      actions = []
      if self.ws.users.is_current_user_admin(self):
        return True
      for perm in perms:
        if perm.role.key() == anonrole.key():
          actions.append(perm.type)
          return True
        if user.key() in perm.role.users:
          actions.append(perm.type)
      if len(actions) == 0:
        return False
      else:
        return True
    else:
      return True
      # default to show the page, no permissions is the same as anonymous
