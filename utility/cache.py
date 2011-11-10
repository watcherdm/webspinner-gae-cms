from google.appengine.api import memcache

class Cache():
  keys = []
  def add(self, key, data):
    if not key in self.keys:
      self.keys.append(key)
    memcache.set(key, data)
  def get(self, key):
    return memcache.get(key)
  def clear(self):
    for key in self.keys:
      memcache.delete(key)