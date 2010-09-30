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
    if perms:
      user = self.ws.users.get_current_user()
      for perm in perms:
        if user in perm.role.users:
          self.actions.append(perm.type)
      if len(self.actions) == 0:
        return False
      else:
        return self.actions
    else:
      return True
      # default to show the page, no permissions is the same as anonymous
    

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
    page = Page.get_by_name(path)
    pages = Page.all().fetch(100)
    admin_html = []
    if page:
      if "visible" in page.properties():
        checked = "checked" if page.visible else ""
      user = self.ws.users.get_current_user(self)
      if user:
        user_control = self.ws.users.create_logout_url(path)
        user_label = "Logout"
        if self.ws.users.is_current_user_admin(self):
          admin_html = ["<div class='admin_tools'>", 
            # page admin for current page
            """<span class="admin_tab">Admin Page
            <div class="admin page_wrapper">
              <div class="tab_strip"><span class="data_tab">Data</span><span class="look_tab">Looks</span><span class="secure_tab">Security</span>
              </div>
              <div class="data">
              <form action="/admin/edit/page/%s?return_url=%s" method="POST">
                <label for="page.name">Page Name: <span class='help'>how it appears in the url</span></label><br />
                <input type="text" id="page.name" name="page.name" value="%s" required /><br />
                <label for="page.ancestor">Parent Page: <span class='help'>which page this will appear under in the menu, if any.</span></label><br />
                <select name="page.ancestor" id="page.ancestor">
                <option value="None">-- None --</option>
                %s
                </select><br />
                <label for="page.title">Page Title: <span class='help'>the title of the page shows in the browser title or tab title.</span></label><br />
                <input type="text" name="page.title" id="page.title" value="%s" required /><br />
                <label for="page.menu_name">Page Menu Name: <span class='help'>the name to appear in the menu listing.</span></label><br />
                <input type="text" name="page.menu_name" id="page.menu_name" value="%s" required /><br />
                <label for="page.visible">Visible?: <span class='help'>if the page is visible to any user besides administrators.</span></label><br />
                <input type="checkbox" name="page.visible" id="page.visible" value="True" %s /><br />
                <label for="page.tags">Tags: <span class='help'>the tags associated with this page.</span></label><br />
                <input type="text" name="page.tags" id="page.tags" value="%s" /><br />
                <input type="submit" name="page.submit" id="page.submit" />
              </form>
            </div>
            <div class="look">
              <form action="/admin/edit/theme/%s?return_url=%s" method="POST">
                <textarea name="page.theme.html" id="page.theme.html">%s</textarea>
                <textarea name="page.theme.css" id="page.theme.css">%s</textarea>
                <textarea name="page.theme.js" id="page.theme.js">%s</textarea>
                <input type="submit" name="page.theme.submit" value="Save Changes"/>
              </form>
            </div>
            <div class="secure">
              <form action="/admin/edit/page/%s?return_url=%s" method="POST">
                %s
                <input type="submit" name="page.permissions.submit" value="Save Permissions"/>
              </form>
            </div>
          </div>
          </span>""" % (page.key(), self.request.path, page.name, ["<option value='%s'>%s</option>" % (upage.key(), upage.title) for upage in pages], page.title, page.menu_name, checked, ", ".join(page.tags), page.theme.key(), self.request.path, page.theme.html, page.theme.css, page.theme.js, page.key(), self.request.path, Permission.get_table())]
          s = 0
          c = 0
          for section in db.get(page.sections):
            admin_html.append("""<span class="admin_tab">%s<div class="admin section_theme_html">
              <form action="/admin/edit/theme/%s?return_url=%s" method="POST">
                <textarea name="section.theme.html" id="section.theme.html">%s</textarea>
                <textarea name="section.theme.css" id="section.theme.css">%s</textarea>
                <textarea name="section.theme.js" id="section.theme.js">%s</textarea>
                <input type="submit" name="section.theme.submit" value="Save Changes"/>
              </form>
            </div></span>""" % (section.name.replace("section_","").capitalize(),section.theme.key(),self.request.path,  section.theme.html, section.theme.css, section.theme.js))
            s += 1
            for content in db.get(section.contents):
              admin_html.append("""<span class="admin_tab">Admin Content %d<div class="admin content.edit">
                <form action="/admin/edit/content/%s?return_url=%s" method="POST">
                  <textarea name="content.content" id="content.content">%s</textarea>
                  <input type="submit" name="content.submit" id="content.submit" value="Save Changes" />
                </form>
              </div></span>""" % (c, content.key(),self.request.path,  content.content))
              c += 1
          # add page form
          admin_html.append("""<span class="admin_tab">Add New Page <div class="admin page.add">
                <form action="/admin/add/page?return_url=%s" method="POST">
      <label for="page.name">Page Name: <span class='help'>how it appears in the url</span></label><br />
      <input type="text" id="page.name" name="page.name" required /><br />
      <label for="page.ancestor">Parent Page: <span class='help'>which page this will appear under in the menu, if any.</span></label><br />
      <select name="page.ancestor" id="page.ancestor">
      <option value="None">-- None --</option>
      %s
      </select><br />
      <label for="page.title">Page Title: <span class='help'>the title of the page shows in the browser title or tab title.</span></label><br />
      <input type="text" name="page.title" id="page.title" required /><br />
      <label for="page.menu_name">Page Menu Name: <span class='help'>the name to appear in the menu listing.</span></label><br />
      <input type="text" name="page.menu_name" id="page.menu_name" required /><br />
      <label for="page.visible">Visible?: <span class='help'>if the page is visible to any user besides administrators.</span></label><br />
      <input type="checkbox" name="page.visible" id="page.visible" value="True" %s /><br />
      <label for="page.tags">Tags: <span class='help'>the tags associated with this page.</span></label><br />
      <input type="text" name="page.tags" id="page.tags" /><br />
      <input type="submit" name="page.submit" id="page.submit" />
    </form>         
          </div></span>""" % (self.request.path, ["<option value='%s'>%s</option>" % (upage.key(), upage.title) for upage in pages], checked))
          # image manager for the site
          admin_html.append("""<span class="admin_tab">Images
            <div class="admin image.add">
              <div class="tab_strip">
                <span class="data_tab">Add Image</span>
                <span class="look_tab">Use Image</span>
              </div>
              <div class="data">
      <form action="/admin/add/image?return_url=%s" enctype="form/multipart" method="POST">
        <label for="image.file">Image File: <span class='help'>the image file to store and display.</span></label><br/>
        <input type="file" name="image.file" id="image.file" required /><br/>
        <label for="image.title">Image Title: <span class='help'>the title that will be used when referring to the image in themes.</span></label><br />
        <input type="text" name="image.title" id="image.title" /><br/>
        <label for="image.tags">Image Tags: <span class='help'>the tags associated with this image.</span></label><br/>
        <input type="text" name="image.tags" id="image.tags" /><br/>
        <input type="submit" name="image.submit" id="image.submit" value="Upload Image"/>
      </form>
              </div>
              <div class="look">
                %s
              </div>
            </div>
          </span>""" % (self.request.path, self.ws.site.images_for_use()))
          # css for admin items
          admin_html.append("""<style>div.admin {display: none; position: absolute; height: 480px; width: 640px; background: #333; left: 300px; top: 20px; border: solid 3px #fff; -webkit-box-shadow: 0px 1px 1px rgba(0,0,0,.8);}
          div.admin textarea{width: 630px; height: 120px;margin: 5px; z-index: 10000; background: #111; color: #1f1;}
          div.admin_tools {position: fixed; top: 10px left: 0px; text-align: left;}
          div.admin_tools>span {position: relative;left: 0px;padding: 6px; display: block; height: 20px; width: 150px; background: #333; border: solid 3px #fff; -webkit-box-shadow: 0px 1px 1px rgba(0,0,0,.8); color: #fff; text-shadow: 0px 1px 1px rgba(0,0,0,.8); font-weight: bolder;margin-left: -15px; margin-top: 10px;}
          span.help {display: none;}
          div.admin input[type=text], div.admin select,div.admin label{margin: 5px; width: 630px;}
          
          span.data_tab{position: relative; top: -23px; border: solid 3px #fff; border-bottom: none; background: #333;padding: 4px 10px ; margin-left: 5px; margin-right: 5px; color: #fff; text-shadow: 0px 1px 1px rgba(0,0,0,.8);}
          span.look_tab{position: relative; top: -23px; border: solid 3px #fff; border-bottom: none; background: #333;padding: 4px 10px ; margin-left: 5px; margin-right: 5px; color: #fff; text-shadow: 0px 1px 1px rgba(0,0,0,.8);}
          span.secure_tab{position: relative; top: -23px; border: solid 3px #fff; border-bottom: none; background: #333;padding: 4px 10px ; margin-left: 5px; margin-right: 5px; color: #fff; text-shadow: 0px 1px 1px rgba(0,0,0,.8);}
          div.admin div.data {}
          div.admin div.look {display: none;}
          div.admin div.secure {display: none;}
          div.secure table{color: white; width: 100%;}
          </style>""")
          # javascript for admin items
          admin_html.append("""<script type="text/javascript">
$(function(){
              $("div.admin_tools").find("span").toggle(function(){$(this).find(">div").show().css("top", 100 - $(this).offset().top + "px")}, function(e){if($(e.srcElement).hasClass("admin_tab")){$(this).find("div:not(.tab_strip, .data)").hide().find(".data").show();}});
              $("div.admin_tools span div").click(function(e){e.stopPropagation(); return true;});
              $("div.admin_tools span div.admin>div.tab_strip>span").click(webspinner.admin.showPanel);
})
if(!window.webspinner){
  webspinner = {};
}
webspinner.admin = (function(){
              return {
                showPanel: function(e){
                  console.log(this);
                  var tab = $(this).attr("class");
                  console.log(tab);
                  tab = tab.replace("_tab", "");
                  console.log(tab);
                  $(this).parents("div.admin").children(":not(.tab_strip)").hide();
                  console.log($(this).parents("div.admin"));
                  $(this).parents(".admin").find("." + tab).show();
                },
                sendPermissions : function(e){
                  var form = $(this).parents("form");
                  $(form).find("input[type=checkbox").each(function(){
                    if ($(this).attr("checked")){
                      result.push($(this).val());
                    }
                  });
                }
              }
})()
          </script>""")
          admin_html.append("</div>")
      else:
        user_control = self.ws.users.create_login_url(path)
        user_label = "Login"
      page_theme = page.theme
      #print page.build_template()
      page_html = "<html><head><title>%s</title><style>%s</style></head><body>%s<script src='http://ajax.googleapis.com/ajax/libs/jquery/1.4.2/jquery.min.js' type='text/javascript'></script><script type='text/javascript'>%s</script>{{ admin_content }}</body></html>" % (page.title, page_theme.css, page.build_template(), page_theme.js)
      page_template = template.Template(page_html)
      sections = db.get(page.sections)
      section_dict = {}
      site_users = User.all().fetch(1000)
      for section in sections:
        section_dict[section.name] =  section
      user_control_link = "<a href='%s' class='user.control'>%s</a>" % (user_control, user_label)
      template_values = {"site_users": site_users, "ws":self.ws,"page": page, "sections": section_dict, "user_control_link": user_control_link, 'admin_content': "".join(admin_html)}
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
      self.response.headers['Content-Type'] = 'image/PNG'
      self.response.out.write(image.file)
    else:
      self.json_out({"name": name})

class AddItem(Handler):
  @admin
  def get(self, type):
    if type.capitalize() in globals():
      cls = globals()[type.capitalize()]
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
        item = db.get(key)
        html_out = """<form action="/admin/edit/%s/%s?return_url=%s" method="POST">""" % (type, key, return_url)
        for key, property in item.properties().iteritems():
          fitype = item.properties()[key].__class__().__str__()
          httype = "text"
          if ".ListProperty" in fitype:
            httype = "text"
          if ".BlobProperty" in fitype:
            httype = "file"
          elif ".StringProperty" in fitype:
            httype = "text"
          html_out += """<label for="%s">%s</label>
          <input type="file" name="%s" id="%s" value="%s" />
          """ % (type.lowercase() + "." + property, property.capitalize(), httype + "." + propertytype.lowercase() + "." + property, )
        
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
          value = self.request.get(k)
          if k.split('.')[-1] in cls().properties().keys():
            if k.split(".")[-1] == "permissions":
              self.response.out.write(self.request.get("page.permissions"))
              return False
            if ".ListProperty" in cls().properties()[k.split('.')[-1]].__class__.__str__(""):
              values[k.split('.')[-1]] = [x.lstrip().rstrip() for x in value.split(",")]
            else:
              values[k.split('.')[-1]] = value
          values[k] = self.request.get(k)
        result = cls.update(values)
        if result:
          #print result
          self.redirect(self.request.get("return_url"))
        else:
          self.response.out.write("Failed to update")
      else:
        self.response.out.write(self.request.get("return_url"))
          

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
