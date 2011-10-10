from handlers.base_handler import Handler
import models

class Utility(Handler):
  

  def get(self, a, b, c):
    results = []
    model_set = models.__getattribute__(a)
    if model_set:
      model = model_set.__getattribute__(b)
      if model:
        instances = model().all().fetch(1000)
        for instance in instances:
          method = instance.__getattribute__(c)
          if method:
            result = method()
            try:
              self.render_json(result)
            except:
              result = result.__str__()
            results.append(result)
    self.json_out(results)