from handlers.base_handler import Handler
from models.site import Image
from models.page import Page, Content
from models.auth import Role, Permission, User
from models.theme import Theme
from google.appengine.ext.webapp import template

class Resource():
  class ImageHandler(Handler):
    def get(self, imgid):
      
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

  class StaticHandler(Handler):
    def get(self, filename):
      try:
        self.response.headers.add_header("Content-Type", "text/html")
        self.response.out.write(open('public/'+filename).read())
      except :
        self.error(404);
        self.response.out.write(open('error/404.html').read())

  class PageHandler(Handler):
    def generate_admin_html(self, page, user):
      contents = Content.all().fetch(1000)
      roles = Role.all().fetch(1000)
      emaildata = {
        "contents":contents, 
        "roles":roles        
      }
      emailcontext = template.Context(emaildata)
      email_template = template.Template(open("templates/email.html").read())
      email_html = email_template.render(emailcontext)
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
              "title" : content.title,
              "content_edit" : Content.to_edit_list("title", self.request.path), 
              "content_form" : Content.to_form(self.request.path,"edit",content.key(), section.key()), 
              "content_deepform" : Content.to_form(self.request.path, rel_key = section.key())                
            } for content in section.get_contents())
          } for section in page.get_sections()
        ),
        "page_form" : Page.to_form(self.request.path, rel_key = self.ws.site.key()),
        "user_form" : User.to_form(self.request.path), 
        "user_list" : User.to_edit_list("email", self.request.path, True), 
        "user_edit_form" : User.to_form(self.request.path, "edit", user.key() ),
        "user_import" : open('defaults/admin/user_import.html').read(),
        "images" : self.ws.site.images_for_use(),
        "email_blast" : email_html
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
        self.redirect('/')
        return False
      admin_html = ""
      if page:
        if not page.theme:
          page.theme = Theme.create({"name": ["default" + page.name], "html":[open('defaults/template.html').read()],"css":[open('defaults/template.css').read()],"js":[""]})
          page.put()
        if not page.sections:
          page.get_or_make_sections()
        user = self.ws.users.get_current_user(self)
        if user:
          auth = [
            {
              "user_control" : self.ws.users.create_account_url(path),
              "user_label" : "Account"
            }
          ]

          if self.ws.users.is_current_user_admin(self):
            admin_html = self.generate_admin_html(page, user)
        else:
          auth = [
            {
              "user_control" : self.ws.users.create_register_url(path),
              "user_label" : "Register"
            },
            {
              "user_control" : self.ws.users.create_login_url(path),
              "user_label" : "Login"
            }
          ]
        page_theme = page.theme
        page_content_template = template.Template(page.build_template())
        sections = page.get_sections()
        section_dict = {}
        site_users = User.all().fetch(1000)
        for section in sections:
          section_dict[section.name] =  section
        user_control_link = ""
        for control in auth:
          user_control_link += "<a href='%s' class='account control'>%s</a>" % (control['user_control'], control['user_label'])
        page_content_template_values = {
          "site_users": site_users, 
          "ws":self.ws,
          "page": page,
          "sections": section_dict,
          "user_control_link": user_control_link
        }
        page_content = self.render_string(page_content_template, page_content_template_values)
        page_template_html = open("defaults/outer.html").read()
        page_template = template.Template(page_template_html)
        template_values = {
          "title" : page.title,
          "css" : page_theme.css,
          "content" : page_content,
          "js" : page_theme.js,
          "admin_content": admin_html
        }
        self.render_string_out(page_template, template_values)
      else:
        self.error(404)
