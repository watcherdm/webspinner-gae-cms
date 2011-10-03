from base_handler import Handler
from models.auth import VerificationToken, User
from models.site import Site
from google.appengine.ext.webapp import template
class Auth():
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
      site = Site.all().get()
      if email and not code:
        if User.send_recovery_email(email, site.title):
          self.response.out.write("The email has been sent. Please check your email to reset your password.")
          return True
        else:
          self.response.out.write("The email was not sent. Please try again.")
          return False
      elif email and code and password:
        user = User.get_by_email(email)
        if user:
          if user.set_password(password, site.secret):
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
