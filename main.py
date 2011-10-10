'''
Copyright (c) 2010, Webspinner Inc.
All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:
Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
Neither the name of the appengine-utilities project nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
'''
import wsgiref.handlers
from google.appengine.ext import webapp
from handlers.admin import Admin
from handlers.auth import Auth
from handlers.resource import Resource
from utility.handler import Utility

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
          ('/install', Admin.Install),
          ('/login', Auth.Login),
          ('/logout', Auth.Logout),
          ('/account', Auth.Account),
          ('/pwrecovery/(.*)', Auth.UserRecovery),
          ('/images/(.*)/[sbtl]', Resource.ImageHandler),
          ('/util/(.*)/(.*)/(.*)', Utility),
          ('/(.*)css', Resource.CssHandler),
          ('/.*', Resource.PageHandler),]


def main():
  application = webapp.WSGIApplication(ROUTES, debug=True)
  wsgiref.handlers.CGIHandler().run(application)

if __name__ == "__main__":
  main()
