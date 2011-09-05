'''
Copyright (c) 2010, Webspinner Inc.
All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:
Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
Neither the name of the appengine-utilities project nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
'''
import logging
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
from google.appengine.ext import db, deferred
from django.utils import simplejson
import hashlib
import re
from models import *

defaults = {}

def load_defaults():
  for root, dirs, files in os.walk('defaults'):
    print root, "consumes",
    for dir in dirs:
      print dir
    for name in files:
      print name
    print "bytes in", len(files), "non-directory files"

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


def admin(handler_method):
  """ Admin required decorator
  """
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
    page = Page.get_by_name(path)
    if not page:
      self.error(404)
      return False
    if not self.permission_check(page):
      self.error(403)
      self.redirect(self.ws.users.create_login_url(path))
      return False
    pages = Page.all().fetch(100)
    admin_html = []
    if page:
      if not page.theme:
        page.theme = Theme.create({"name": ["default" + page.name], "html":[open('defaults/template.html').read()],"css":[open('defaults/template.css')],"js":[""]})
        page.put()
      if not page.sections:
        page.get_or_make_sections()
      if "visible" in page.properties():
        checked = "checked" if page.visible else ""
      user = self.ws.users.get_current_user(self)
      if user:
        user_control = self.ws.users.create_logout_url(path)
        user_label = "Logout"
        contents = Content.all().fetch(1000)
        roles = Role.all().fetch(1000)

        if self.ws.users.is_current_user_admin(self):
          admindata = {
            "page_edit" : Page.to_form(self.request.path, "edit", page.key()), 
            "theme_edit" : Theme.to_form(self.request.path, "edit", page.theme.key(), page.key()), 
            "page_key" : page.key(), 
            "path" : self.request.path, 
            "permission_table" : Permission.get_table(page.key()),
            "sections" : (
              {
                "name" : section.name.replace("section_","").capitalize(),
                "theme_key" : section.theme.key(),
                "theme_html" : section.theme.html, 
                "theme_css" : section.theme.css, 
                "theme_js" : section.theme.js,
                "content" : ({
                  "content_edit" : Content.to_edit_list("title", self.request.path), 
                  "content_form" : Content.to_form(self.request.path,"edit",content.key(), section.key()), 
                  "content_deepform" : Content.to_form(self.request.path, rel_key = section.key())                
                } for content in db.get(section.contents))
              } for section in db.get(page.sections)
            ),
            "page_form" : Page.to_form(self.request.path, rel_key = self.ws.site.key()),
            "user_form" : User.to_form(self.request.path), 
            "user_list" : User.to_edit_list("email", self.request.path, True), 
            "user_edit_form" : User.to_form(self.request.path, "edit", user.key() ),
            "images" : self.ws.site.images_for_use(),
            "contents":contents, 
            "roles":roles
          }
          context = template.Context(admindata)
          admin_template = template.Template(open("defaults/admin/tabs.html").read())
          admin_html = admin_template.render(context)
      else:
        user_control = self.ws.users.create_login_url(path)
        user_label = "Login"
      page_theme = page.theme
      page_html = """<html>
      <head>
        <title>
          %s
        </title>
        <meta http-equiv='X-UA-Compatible' content='chrome=1'>
        <style>
          %s
        </style>
      </head>
      <body>
        %s
        <script src='http://ajax.googleapis.com/ajax/libs/jquery/1.6.2/jquery.min.js' type='text/javascript'>
        </script>
        <script type='text/javascript'>
          %s
        </script>
        {{ admin_content }}
      </body>
    </html>""" % (page.title, page_theme.css, page.build_template(), page_theme.js)
      page_template = template.Template(page_html)
      sections = db.get(page.sections)
      section_dict = {}
      site_users = User.all().fetch(1000)
      for section in sections:
        section_dict[section.name] =  section
      user_control_link = "<a href='%s' class='user.control'>%s</a>" % (user_control, user_label)
      template_values = {
        "site_users": site_users, 
        "ws":self.ws,
        "page": page, 
        "sections": section_dict, 
        "user_control_link": user_control_link, 
        'admin_content': admin_html
      }
      self.render_string_out(page_template, template_values)
    else:
      self.error(404)

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
      self.response.headers['Content-Type'] = 'image/PNG'
      self.response.out.write(image.file)
    else:
      self.json_out({"name": name})

class CssHandler(Handler):
  def get(self, page):
    if page == "":
      page = "/"
    page = Page.get_by_name(page)
    if page:
      self.response.headers.add_header("Content-Type","text/css")
      self.response.out.write(page.theme.css)

class AddItem(Handler):
  @admin
  def get(self, type):
    if type.capitalize() in globals():
      cls = globals()[type.capitalize()]
      if cls:
        fields = cls().properties()
        self.response.out.write(cls.to_form("/"))
  @admin
  def post(self, type):
    if type.capitalize() in globals():
      cls = globals()[type.capitalize()]
      if cls:
        #self.response.out.write(dir(cls))
        values = {}
        for k in self.request.arguments():
          value = self.request.get_all(k)
          if k.split('-')[-1] == "permissions":
            values[k.split('-')[-1]] = ",".join(self.request.get_all("page.permissions"))
          if k.split('-')[-1] in cls().properties() and "List" in cls().properties()[k.split('-')[-1]].__class__().__str__():
            values[k.split('-')[-1]] = [x.lstrip().rstrip() for x in value]
          else:
            values[k.split('-')[-1]] = value
          values[k] = self.request.get(k)
        result = cls.create(values)
        if result:
          self.redirect(self.request.get("return_url"))
        else:
          self.response.out.write("Failed to update")
      else:
        self.response.out.write(self.request.get("return_url"))
      #self.response.out.write(dir(record._properties[record._properties.keys()[0]].__subclasshook__))

class EditItem(Handler):
  #TODO: finish dynamic form builder
  @admin
  def get(self, args):
    type = args.split("/")[0]
    key = args.split("/")[1]
    return_url = self.request.get("return_url")
    if type.capitalize() in globals():
      cls = globals()[type.capitalize()]
      if cls:
        self.response.out.write(cls.to_form(return_url, "edit", key))

  @admin
  def post(self, args):
    type = args.split("/")[0]
    key = args.split("/")[1].split("?")[0]
    if type.capitalize() in globals():
      cls = globals()[type.capitalize()]
      if cls:
        values = {}
        values["key"] = key

        for k in self.request.arguments():
          logging.info(k)
          value = self.request.get_all(k)
          logging.info(value)
          if k.split('-')[-1] in cls().properties().keys():
            if ".ListProperty" in cls().properties()[k.split('-')[-1]].__class__.__str__(""):
              if k.split("-")[-1] == "permissions":
                values[k.split('-')[-1]] = self.request.get_all(k)
              else:
                values[k.split('-')[-1]] = [x.lstrip().rstrip() for x in value.split(",")]
            else:
              values[k.split('-')[-1]] = value
          values[k] = self.request.get_all(k)
        result = cls.update(values)
        if result:
          #print result
          self.redirect(self.request.get("return_url"))
        else:
          self.response.out.write("Failed to update")
      else:
        self.response.out.write(self.request.get("return_url"))

class SetUserRoles(Handler):
  @admin
  def get(self, args):
    args = args.split('/')
    key = args[0].split('?')[0]
    return_url = self.request.get('return_url')
    duser = db.get(key)
    self.response.out.write(duser.create_roles_form(return_url))
  @admin
  def post(self, args):
    user = self.request.get('user')
    role = self.request.get('role')
    return_url = self.request.get('return_url')
    if not user or not role:
      self.redirect(return_url)
    duser = db.get(user)
    drole = db.get(role)
    urole = duser.roles()
    for ur in urole:
      ur.users.remove(duser.key())
      ur.put()
    drole.users.append(duser.key())
    drole.put()
    self.redirect(return_url)

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

class EmailContent(Handler):
  @admin
  def post(self, *args):
    from google.appengine.api import mail
    import html2text
    # TODO: get a template together for email content and inject safe content into it.
    content = db.get(self.request.get('content'))
    role = db.get(self.request.get('role'))
    mailusers = db.get(role.users)
    for mailuser in mailusers:
      deferred.defer(mail.send_mail, sender = "IAOS Website <info@iaos.net>",
        to="%s %s <%s>" % (mailuser.firstname, mailuser.lastname, mailuser.email),
        subject="%s" % content.title,
        html="%s" % content.content,
        body="%s" % html2text.html2text(content.content, baseurl="http://www.iaos.net/"))
    self.response.out.write("""BODY : %s
    HTML : %s
    SUBJECT : %s""" % ())
    self.response.out.write("""Emails scheduled successfully.""")

class CacheClear(Handler):
  def get(self):
    self.response.out.write(memcache.flush_all())

class UserRecovery(Handler):
  def get(self, code = False):
    if not code:
      code = self.request.get("code")
    args = {}
    if code:
      token = VerificationToken.get_by_code(code)
      if token:
        email = token.email
        if not email:
          self.error(403)
          return False
        args = {
          "code": code,
          "email": email,
        }
    self.response.out.write(template.render('templates/pwrecovery.html',args))
  def post(self, *args, **kwargs):
    email = self.request.get("email")
    code = self.request.get("code")
    password = self.request.get("password")
    if email and not code:
      if User.send_recovery_email(email):
        self.response.out.write("The email has been sent. Please check your email to reset your password.")
        return True
      else:
        self.response.out.write("The email was not sent. Please try again.")
        return False
    elif email and code and password:
      user = User.get_by_email(email)
      if user:
        if user.set_password(password):
          site = Site.all().get()
          login = User.login(email, password, site)
          self.session["user"] = login
          user.destroy_token()
          self.redirect('/')
          return True
        else:
          self.response.out.write("An Error Occurred Resetting Password, Please try again.")
          return False
      else:
        self.response.out.write("Cannot Reset Password For This User")
        return False
    return False
    

class ListJavascript(Handler):
  def get(self, type):
    if type == "images":
      self.response.headers.add_header("Content-Type","text/javascript")
      self.response.out.write("var tinyMCEImageList = [%s]" % "".join(["['" + image.title + "','" + image.to_url() +"']" for image in db.get(self.ws.site.images)]))

ROUTES = [('/admin', Administrate),
                    ('/admin/add/(.+)', AddItem),
                    ('/admin/edit/(.+)', EditItem),
                    ('/admin/delete/(.+)', DeleteItem),
                    ('/admin/download/(.+)', ExportItem),
                    ('/admin/set_user_roles/(.*)', SetUserRoles),
                    ('/admin/lists/(.+)', ListJavascript),
                    ('/admin/email(.*)', EmailContent),
                    ('/login', Login),
                    ('/logout', Logout),
                    ('/install', Install),
                    ('/images/.*/[sbtl]', ImageHandler),
                    ('/pwrecovery/(.*)', UserRecovery),
                    ('/clearcache', CacheClear),
                    ('/(.*)css', CssHandler),
                    ('/.*', GetPage),]


def main():
  #load_defaults()
  application = webapp.WSGIApplication(
                                       ROUTES,
                                       debug=True)
  wsgiref.handlers.CGIHandler().run(application)

if __name__ == "__main__":
  main()
