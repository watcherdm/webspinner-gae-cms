from .base_model import WsModel
from random import random
from hashlib import sha256
from google.appengine.api import mail
import datetime

ACTIONS = ['view','edit']

class Role(WsModel):
  """ Role defines the different available user roles"""
  name = WsModel.db.StringProperty()
  users = WsModel.db.ListProperty(WsModel.db.Key)
  @classmethod
  def create_default(cls):
    roles_names = ['Anonymous','User','Administrator']
    roles = []
    for role in roles_names:
      new_role = cls()
      new_role.name = role
      new_role.put()
      roles.append(new_role)
    WsModel.memcache.set('roles', roles)
    return roles
  def add_user(self, user_key):
    self.users.append(user_key);
    self.put()
    WsModel.memcache.set('role_' + self.name + '_users', self.users)
  @classmethod
  def add_administrator(cls, user):
    adminrole = filter(lambda x : x.name == "Administrator", WsModel.memcache.get('roles'))
    adminrole = cls.all().filter("name","Administrator").get()
    adminrole.users.append(user.key())
    adminrole.put()

class Permission(WsModel):
  """ Permission assigns an action type with a role and is used in content elements to associate a user with the actions he can take"""
  type = WsModel.db.StringProperty()
  role = WsModel.db.ReferenceProperty(Role)

  @classmethod
  def get_for_role(cls, role):
    return cls.all().filter("role",role).fetch(100)

  @classmethod
  def get_for_action(cls, action):
    return cls.all().filter("type", action).fetch(100)

  @classmethod
  def get_table(cls, page_key = None):
    roles = Role.all().fetch(100)
    html_out = "<table><tr><td></td>"
    html_out += "".join(["<th>%s</th>" % action for action in ACTIONS])
    html_out += "</tr>"
    if page_key:
      page = WsModel.db.get(page_key)
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
  oauth = WsModel.db.UserProperty()
  email = WsModel.db.EmailProperty()
  password = WsModel.db.StringProperty()
  salt = WsModel.db.StringProperty()
  firstname = WsModel.db.StringProperty()
  lastname = WsModel.db.StringProperty()
  spouse = WsModel.db.StringProperty()
  address = WsModel.db.PostalAddressProperty()
  phone = WsModel.db.PhoneNumberProperty()
  fax = WsModel.db.PhoneNumberProperty()
  location = WsModel.db.GeoPtProperty()
  url = WsModel.db.LinkProperty()
  picture = WsModel.db.BlobProperty()
  tags = WsModel.db.StringListProperty()

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
  def create_user(cls, email, password, site_secret, user = None):
    random_key = str(random())
    new_user = cls()
    new_user.email = email
    new_user.oauth = user
    new_user.password = sha256("%s%s%s" % (site_secret, random_key, password)).hexdigest()
    new_user.salt = random_key
    new_user.put()
    return new_user

  @classmethod
  def send_recovery_email(cls, user_email, site_title):
    link = cls.generate_recovery_link(user_email)
    user = User.get_by_email(user_email)
    if not link:
      return False
    if not user:
      return False
    mail.send_mail(sender="IAOS.net website <info@iaos.net>",
      to = "%s %s <%s>" % (user.firstname, user.lastname, user.email),
      subject = "%s : User Password Reset" % site_title,
      body = """Dear %s %s,
      
Please click the following link to reset your password:
%s
If you did not request the reset of this password you can safely ignore this message. 
If you do not have a password for this website but you are a member of the Irish 
American Orthopaedic Society then please come to the website and set your password.

Regards,
IAOS.net""" % (user.firstname, user.lastname, link),
      html = """<h3>Dear %s %s,</h3>
<p><a href="%s">Please click here to reset your password.</a> </p>
<p>If you did not request the reset of this password you can safely ignore this message. 
If you do not have a password for this website but you are a member of the Irish 
American Orthopaedic Society then please come to the website and set your password.</p>
</p>
Regards,<br/>
IAOS.net""" % (user.firstname, user.lastname, link))
    return True
  
  @classmethod
  def generate_recovery_link(cls, user_email):
    code = VerificationToken.create_token(user_email)
    if code:
      return "http://www.iaos.net/pwrecovery/%s"%code
    return False
  
  def destroy_token(self):
    token = VerificationToken.get_by_user(self)
    if token:
      token.delete()
      return True
    else:
      return False
  
  def set_password(self, password, site_secret):
    """ set_password is a instance method to set the password for a user. If there is no salt currently set it will be generated randomly. """
    if not self.salt:
      self.salt = str(random())
    if password:
      self.password = sha256("%s%s%s" % (site_secret, self.salt, password)).hexdigest()
      self.put()
      return True
    else:
      return False
      
  def create_roles_form(self, return_url):
    roles = WsModel.memcache.get("roles")
    if not roles:
      roles = Role.all().fetch(1000)
      WsModel.memcache.set("roles", roles)
    role_out = "<select name='role'>"
    for role in roles:
      user_role = self.roles()[0].name if self.roles() else "Anonymous"
      selected = "selected" if role.name == user_role else ""
      role_out += "<option value='%s' %s>%s</option>" % (role.key(), selected ,role.name)
    role_out += "</select>"
    html_out = """<form action='/admin/set_user_roles/' method='POST'>%s 
      <input type="hidden" name="user" value="%s"/>
      <input type="hidden" name="return_url" value="%s"/>
      %s
      <input type="submit" value="Set Role"/>
    </form>""" % (self.email, self.key(), return_url, role_out)
    return html_out

  def roles(self):
    this_user_roles = Role.all().filter("users =", self.key()).fetch(1000)
    return this_user_roles

class VerificationToken(WsModel):
  """ Verification token to allow users to reset password """
  user = WsModel.db.ReferenceProperty(User)
  code = WsModel.db.StringProperty()
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
