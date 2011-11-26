from google.appengine.api import mail
import html2text
from google.appengine.ext import db, deferred
import logging

class EmailNotifier():
  @classmethod
  def notify(cls, to, sender, content):
    # TODO: get a template together for email content and inject safe content into it.
    for mailuser in to:
      logging.info('Sending email to ' + mailuser.email)
      deferred.defer(mail.send_mail, sender = sender,
        to="%s %s <%s>" % (mailuser.firstname, mailuser.lastname, mailuser.email),
        subject="%s" % content.title,
        html="%s" % content.content,
        body="%s" % html2text.html2text(content.content, baseurl="http://www.iaos.net/"))
    return True