'''
Copyright (c) 2010, Webspinner Inc.
All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:
Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
Neither the name of the appengine-utilities project nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
'''
import os
from google.appengine.ext.webapp import template
import wsgiref.handlers
from google.appengine.ext import webapp
from google.appengine.ext import db
from handlers.admin import Admin
from handlers.auth import Auth
from handlers.base_handler import Handler
from models.page import Page, Content
from models.auth import Role, Permission, User
from models.site import Site, Image
from models.theme import Theme
defaults = {}

def load_defaults():
  for root, dirs, files in os.walk('defaults'):
    print root, "consumes",
    for dir in dirs:
      print dir
    for name in files:
      print name
    print "bytes in", len(files), "non-directory files"

class GetPage(Handler):
  def generate_admin_html(self, page, user):
    contents = Content.all().fetch(1000)
    roles = Role.all().fetch(1000)
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
    return admin_html

  def get(self):
    if self.ws.site is None:
      self.redirect('/install')
      return False
    path = self.request.path
    #print path
    user_control = ""
    user_label = ""
    def kv_q(x):
      x = x.split('=')
      if len(x) < 2:
        return x[0]
      return {x[0]: x[1]}
    page = Page.get_by_name(path)
    if not page:
      self.error(404)
      return False
    if not self.permission_check(page):
      self.error(403)
      self.redirect(self.ws.users.create_login_url(path))
      return False
    admin_html = ""
    if page:
      if not page.theme:
        page.theme = Theme.create({"name": ["default" + page.name], "html":[open('defaults/template.html').read()],"css":[open('defaults/template.css')],"js":[""]})
        page.put()
      if not page.sections:
        page.get_or_make_sections()
      user = self.ws.users.get_current_user(self)
      if user:
        user_control = self.ws.users.create_logout_url(path)
        user_label = "Logout"

        if self.ws.users.is_current_user_admin(self):
          admin_html = self.generate_admin_html(page, user)
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
    user = self.ws.users.get_current_user()
    site = Site.create(save_items['site.admin'],save_items['site.password'],save_items['site.title'],user)
    self.redirect('/')


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



ROUTES = [('/admin', Admin.Administrate),
          ('/admin/add/(.+)', Admin.AddItem),
          ('/admin/edit/(.+)', Admin.EditItem),
          ('/admin/delete/(.+)', Admin.DeleteItem),
          ('/admin/download/(.+)', Admin.ExportItem),
          ('/admin/import/(.+)', Admin.ImportItem),
          ('/admin/set_user_roles/(.*)', Admin.SetUserRoles),
          ('/admin/email(.*)', Admin.EmailContent),
          ('/clearcache', Admin.CacheClear),
          ('/admin/lists/(.+)', Admin.ListJavascript),
          ('/login', Auth.Login),
          ('/logout', Auth.Logout),
          ('/pwrecovery/(.*)', Auth.UserRecovery),
          ('/install', Install),
          ('/images/(.*)/[sbtl]', ImageHandler),
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
