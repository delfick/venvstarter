class memoized_property(object):
    def __init__(self, func):
        self.func = func
        self.key = f".{self.func.__name__}"

    def __get__(self, instance, owner):
        obj = getattr(instance, self.key, None)
        if obj is None:
            obj = self.func(instance)
            setattr(instance, self.key, obj)
        return obj

    def __set__(self, instance, value):
        setattr(instance, self.key, value)


def do_format(s, **kwargs):
    if hasattr(s, "format"):
        return s.format(**kwargs)
    else:
        return str(s).format(**kwargs)
