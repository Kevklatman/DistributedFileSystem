import datetime
from flask.json import JSONEncoder as BaseJSONEncoder

class JSONEncoder(BaseJSONEncoder):
    """Custom JSON encoder for handling datetime objects"""
    def default(self, obj):
        try:
            if isinstance(obj, datetime.datetime):
                return obj.isoformat()
            if isinstance(obj, datetime.date):
                return obj.isoformat()
            if isinstance(obj, datetime.time):
                return obj.isoformat()
            iterable = iter(obj)
        except TypeError:
            pass
        else:
            return list(iterable)
        return super().default(obj)