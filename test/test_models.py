import unittest
from models import *

""" crud testing """

class TestSiteModel(unittest.TestCase):
  def setUp(self):
    site = Site()
    site.actions = ['view','add','edit','delete','comment','rate']
    site.title = "Test Website"
    site.description = "Test Website Description"
    site.keywords = ['1','2','3']
    site.tags = ['tag1','tag2','tag3','tag4','tag5','tag6']
    site.put()
  def test_tags_exist(self):
    site = Site.all().get()
    self.assertTrue(['tag1','tag2','tag3','tag4','tag5','tag6'] == site.tags)
  def test_title_works(self):
    site = Site.all().get()
    self.assertTrue('Test Website' == site.title)
class TestPageMode(unittest.TestCase):
  def setUp(self):
    page = Page()
    
  def test_tags_exist(self):
    page = Page.all().get()
    self.assertTrue([] == page.tags
