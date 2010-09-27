'''
Copyright (c) 2010, Webspinner CMS
All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:
Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
Neither the name of the appengine-utilities project nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
'''
import os
import __main__
import time
from google.appengine.api import urlfetch
from google.appengine.ext.webapp import template
from appengine_utilities import sessions
from appengine_utilities import flash
from appengine_utilities import event
from appengine_utilities import cache
from appengine_utilities.rotmodel import ROTModel
import wsgiref.handlers
from google.appengine.ext import webapp
from google.appengine.api import memcache, users
from google.appengine.ext import db
from django.utils import simplejson
import hashlib
import re
from models import *

class Webspinner():
  def __init__(self):
    self.site = Site.all().get()

  def get_nav_list(self):
    html_out = "<ul class='site_menu'>"
    pages = db.get(self.site.pages)
    def top_level(page):
      if not page.ancestor:
        return True
      else:
        return False
    def add_page_to_menu(page, html_out):
      html_out += "<li class='menu_item'><a href='%s' class='menu_item_link'>%s</a>" % ("/".join(page.page_chain), page.menu_name)
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
      html_out = add_page_to_menu(page, html_out)
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
    self.ws = Webspinner()
    self.session = sessions.Session()
    
  def json_out(self, data):
    self.response.headers.add_header("Content-Type","application/json")
    self.response.out.write(simplejson.dumps(data))
  def render_out(self, template_file, values = {}):
    self.response.out.write(template.render(template_file,values))
  def render_string_out(self, template_object, template_values):
    context = template.Context(template_values)
    self.response.out.write(template_object.render(context))

def admin(handler_method):
  def redirect_if_needed(self, *args, **kwargs):
    user = self.ws.users.get_current_user(self)
    if user == None:
      self.redirect(self.ws.users.create_login_url('/admin'))
    else:
      is_admin = self.ws.users.is_current_user_admin(self)
      if(is_admin):
        handler_method(self, *args, **kwargs)
      else:
        self.redirect("/")
  return redirect_if_needed

class GetPage(Handler):
  def get(self):
    if self.ws.site is None:
      self.redirect('/install')
      return False
    path = self.request.path
    query_string = self.request.query_string
    #print path
    page_chain = path
    query_chain = query_string.split("&")
    user_control = ""
    user_label = ""
    def kv_q(x):
      x = x.split('=')
      if len(x) < 2:
        return x[0]
      return {x[0]: x[1]}
    query_chain_kv = map(kv_q, query_chain)
    page = Page.get_by_page_chain(page_chain)
    if page:
      user = self.ws.users.get_current_user(self)
      if user:
        user_control = self.ws.users.create_logout_url(path)
        user_label = "Logout"
        if self.ws.users.is_current_user_admin(self):
          admin_html = ["""<div class="admin page_theme_html">
            <form action="/admin/edit/theme/%s" method="POST">
              <textarea name="page.theme.html" id="page.theme.html">%s</textarea>
              <textarea name="page.theme.css" id="page.theme.css">%s</textarea>
              <textarea name="page.theme.js" id="page.theme.js">%s</textarea>
              <input type="submit" name="page.theme.submit" value="Save Changes"/>
            </form>
          </div>""" % (page.theme.key(), page.theme.html, page.theme.css, page.theme.js),]
          for section in db.get(page.sections):
            admin_html.append("""<div class="admin section_theme_html">
              <form action="/admin/edit/theme/%s" method="POST">
                <textarea name="section.theme.html" id="section.theme.html">%s</textarea>
                <textarea name="section.theme.css" id="section.theme.css">%s</textarea>
                <textarea name="section.theme.js" id="section.theme.js">%s</textarea>
                <input type="submit" name="section.theme.submit" value="Save Changes"/>
              </form>
            </div>""" % (section.theme.key(), section.theme.html, section.theme.css, section.theme.js))
            for content in db.get(section.contents):
              admin_html.append("""<div class="admin content.edit">
                <form action="/admin/edit/content/%s" method="POST">
                  <textarea name="content.content" id="content.content">%s</textarea>
                  <input type="submit" name="content.submit" id="content.submit" value="Save Changes" />
                </form>
              </div>""" % (content.key(), content.content))
      else:
        user_control = self.ws.users.create_login_url(path)
        user_label = "Login"
      page_theme = page.theme
      #print page.build_template()
      page_html = "<html><head><title>%s</title><style>%s</style></head><body>%s<script src='http://ajax.googleapis.com/ajax/libs/jquery/1.4.2/jquery.min.js' type='text/javascript'></script><script type='text/javascript'>%s</script>%s</body></html>" % (page.title, page_theme.css, page.build_template(), page_theme.js, "".join(admin_html))
      page_template = template.Template(page_html)
      sections = db.get(page.sections)
      section_dict = {}
      for section in sections:
        section_dict[section.name] =  section
      user_control_link = "<a href='%s' class='user.control'>%s</a>" % (user_control, user_label)
      template_values = {"ws":self.ws,"page": page, "sections": section_dict, "user_control_link": user_control_link}
      self.render_string_out(page_template, template_values)
    else:
      self.error(404) #self.json_out({'page_chain':page_chain,'query_chain':query_chain_kv})

class Install(Handler):

  def get(self):
    site = Site.all().get()
    if(site):
      self.redirect("/")
    self.render_out("templates/install.html")
  def post(self):
    site = Site.all().get()
    if(site):
      self.redirect("/")
    save_items = {'site.title':'','site.admin':'','site.password':''}
    form_items = ['site.title','site.admin','site.password']
    for item in form_items:
      if item in self.request.arguments():
        if self.request.get(item) != "":
          save_items[item] = self.request.get(item)
        else:
          self.json_out({"success":False,"message":"%s is not entered" % item})
          return False
      else:
        self.json_out({"success":False,"message":"%s is not in the form" % item})
        return False
    user = users.get_current_user()
    site = Site.create(save_items['site.admin'],save_items['site.password'],save_items['site.title'],user)
    self.redirect('/')

class Login(Handler):
  def get(self):
    template_values = {'return_url': self.request.get("return_url")}
    self.render_out("templates/login.html", template_values)
  def post(self):
    if 'user.email' not in self.request.arguments() or 'user.password' not in self.request.arguments():
      self.json_out({'success': False,'message': 'Login invalid, not a legitamate form'})
    if self.request.get('user.email') == "" or  self.request.get('user.password') == "":
      self.json_out({'success': False,'message': 'Please enter your email address and password to login'})
    login = User.login(self.request.get('user.email'),self.request.get('user.password'),self.ws.site)
    if login:
      self.session["user"] = login
      #print self.session["user"]
      self.redirect(self.request.get("return_url"))
    else:
      self.session.delete_item("user")
      self.redirect(self.request.get("return_url"))

class Logout(Handler):
  def get(self):
    self.session.delete_item("user")
    self.redirect(self.request.get("return_url"))

class Administrate(Handler):
  @admin
  def get(self):
    contents = Content.all().fetch(1000)
    theme_packages = ThemePackage.all().fetch(1000)
    themes = Theme.all().fetch(1000)
    pages = Page.all().fetch(1000)
    images = Image.all().fetch(1000)
    roles = Role.all().fetch(1000)
    sections = Section.all().fetch(1000)
    _users = User.all().fetch(1000)
    actions = ACTIONS
    template_values = {'logout_url':self.ws.users.create_logout_url('/'),'theme_packages': theme_packages,'themes': themes, 'images': images, 'pages': pages, 'contents':contents, 'roles':roles, 'users':_users, 'actions': actions, 'sections': sections, 'site': self.ws.site}
    self.response.out.write(template.render('templates/manage.html',template_values))

class ImageHandler(Handler):
  def get(self):
    name = self.request.path.split('/')[2]
    image = Image.get_by_name(name)
    if image and image.file:
      self.response.headers['Content-Type'] = 'image/JPEG'
      self.response.out.write(image.file)
    else:
      self.json_out({"name": name})

class AddItem(Handler):
  @admin
  def get(self, type):
    if type.capitalize() in globals():
      cls = globals()[type.capialize()]
      if cls:
        fields = cls().properties()
        self.render_out("form.html", fields)
  @admin
  def post(self, type):
    if type.capitalize() in globals():
      cls = globals()[type.capitalize()]
      if cls:
        #self.response.out.write(dir(cls))
        values = {}
        for k in self.request.arguments():
          value = self.request.get(k)
          if k.split('.')[-1] in cls().properties() and "List" in cls().properties()[k.split('.')[-1]].__class__().__str__():
            values[k.split('.')[-1]] = [x.lstrip().rstrip() for x in value.split(",")]
          else:
            values[k.split('.')[-1]] = value
          values[k] = self.request.get(k)
        result = cls.create(values)
        self.response.out.write(values)
      else:
        self.response.out.write(self.request)
      #self.response.out.write(dir(record._properties[record._properties.keys()[0]].__subclasshook__))

class EditItem(Handler):
  
  @admin
  def get(self, args):
    type = args.split("/")[0]
    key = args.split("/")[1]
    if type.capitalize() in globals():
      cls = globals()[type.capitalize()]
      if cls:
        item = db.get(key)
        
  @admin
  def post(self, args):
    type = args.split("/")[0]
    key = args.split("/")[1]
    if type.capitalize() in globals():
      cls = globals()[type.capitalize()]
      if cls:
        values = {}
        values["key"] = key
        for k in self.request.arguments():
          value = self.request.get(k)
          if k.split('.')[-1] in cls().properties() and "List" in cls().properties()[k.split('.')[-1]].__class__().__str__():
            values[k.split('.')[-1]] = [x.lstrip().rstrip() for x in value.split(",")]
          else:
            values[k.split('.')[-1]] = value
          values[k] = self.request.get(k)
        result = cls.update(values)
        self.response.out.write(values)
      else:
        self.response.out.write(self.request)
          

class DeleteItem(Handler):
  @admin
  def get(self, args):
    type = args.split("/")[0]
    key = args.split("/")[1]
    self.response.out.write(type + " : " + key)

class ExportItem(Handler):
  @admin
  def get(self, args):
    array_args = args.split("/")
    type = array_args[0]
    key = array_args[1]
    format = array_args[2]
    self.json_out(Site.export(key))
    

ROUTES = [('/admin', Administrate),
                    ('/admin/add/(.+)', AddItem),
                    ('/admin/edit/(.+)', EditItem),
                    ('/admin/delete/(.+)', DeleteItem),
                    ('/admin/download/(.+)', ExportItem),
                    ('/login', Login),
                    ('/logout', Logout),
                    ('/install', Install),
                    ('/images/.*/[sbtl]', ImageHandler),
                    ('/.*', GetPage),]


def main():
  application = webapp.WSGIApplication(
                                       ROUTES,
                                       debug=True)
  wsgiref.handlers.CGIHandler().run(application)

if __name__ == "__main__":
  main()
