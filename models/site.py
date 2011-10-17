from .base_model import WsModel, to_dict
from .page import Page
from .theme import Theme, ThemePackage
from .auth import User, Role, Permission
from random import random

ACTIONS = ['view','edit']

class Site(WsModel):
  """ Site is a wrapper class for all the site data."""
  _modfields = [
    {"name":"admin","type":"email"},
    {"name":"keywords","type":"textlist"},
    {"name":"description","type":"email"},
    {"name":"tags","type":"textlist"}
  ]
  admin = WsModel.db.EmailProperty()
  title = WsModel.db.StringProperty()
  actions = WsModel.db.StringListProperty()
  description = WsModel.db.StringProperty()
  keywords = WsModel.db.StringListProperty()
  tags = WsModel.db.StringListProperty()
  secret = WsModel.db.StringProperty()
  pages = WsModel.db.ListProperty(WsModel.db.Key)
  roles = WsModel.db.ListProperty(WsModel.db.Key)
  images = WsModel.db.ListProperty(WsModel.db.Key)
  theme_packages = WsModel.db.ListProperty(WsModel.db.Key)
  def before_get(self):
    pass
  def after_get(self):
    pages = Page.all().get()
    if not self.pages == pages:
      self.pages.clear()
      for page in pages:
        self.pages.append(page.key())
      self.put()
  def get(self, **kwargs):
    self.before_get()
    super(Site, self).get(**kwargs)
    self.after_get()
  @classmethod
  def get_secret(cls):
    secret = WsModel.cache.get("site_secret")
    if secret:
      return secret
    else:
      secret = cls.all().get().secret
      if secret:
        WsModel.cache.add("site_secret", secret)
        return secret
      else:
        return False
  @classmethod
  def get_title(cls):
    title = WsModel.cache.get("site_title")
    if title:
      return title
    else:
      title = cls.all().get().title
      if title:
        WsModel.cache.add("site_title", title)
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
    main_theme = Theme.create({"name": ["default"], "html":[open('defaults/template.html').read()],"css":[open('defaults/template.css').read()],"js":[]})
    page.theme = main_theme
    page.put()
    theme_packages = ThemePackage.create({"name":["default"],"themes":[",".join([str(main_theme.key())])]})
    site.theme_packages.append(theme_packages.key())
    site.pages.append(page.key())
    site.put()
    admin = User.create_user(email, password, site.secret, user)
    roles = Role.create_default()
    for role in roles:
      site.roles.append(role.key())
    Role.add_administrator(admin)
    site.put()
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
      roles = WsModel.db.get(self.roles)
      for role in roles:
        perm = Permission()
        perm.role = role
        perm.type = action
        perm.put()
        perm_set.append(perm)
    return perm_set

  def images_for_use(self):
    images = WsModel.db.get(self.images)
    html_out = "<ul class='image_selector'>"
    for image in images:
      html_out += "<li><img src='/images/%s/s' title='%s' /></li>" % (image.name, image.title)
    html_out += "</ul>"
    return html_out

class Image(WsModel):
  """ Image is a wrapper class for the image elements in content """
  file = WsModel.db.BlobProperty()
  title = WsModel.db.StringProperty()
  name = WsModel.db.StringProperty()
  tags = WsModel.db.StringListProperty()
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
WsModel.Site = Site