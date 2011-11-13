from base_model import WsModel

class ThemePackage(WsModel):
  """ ThemePackage groups theme elements together for packaging and distribution"""
  _modfields = [{"name":"name","type":"text"},
    {"name":"themes","type":"selectmulti","list":"Theme","list_val":"key","list_name":"name"}]
  name = WsModel.db.StringProperty()
  themes = WsModel.db.ListProperty(WsModel.db.Key)
  @classmethod
  def old_create(cls, dict_values):
    theme_package = cls()
    theme_package.name = "".join(dict_values["name"])
    theme_package.themes = dict_values["themes"]
    theme_package.put()
    return theme_package

WsModel.ThemePackage = ThemePackage

class Theme(WsModel):
  """ Theme relieves the need for static file upload
    Each theme element contains the complete html, css and js
    for the space the element is intended to fill."""
  _relfields = [{"model":"Page","field":"theme","value":"key"}]
  _modfields = [{"name":"name","type":"text"},
    {"name":"html","type":"textareahtml"},
    {"name":"css","type":"textarea"},
    {"name":"js","type":"textarea"}]
  name = WsModel.db.StringProperty()
  html = WsModel.db.TextProperty()
  css = WsModel.db.TextProperty()
  js = WsModel.db.TextProperty()
WsModel.Theme = Theme