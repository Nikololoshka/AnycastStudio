from django.db import models


class LowercaseEmailField(models.EmailField):
    def to_python(self, value):
        return _lowercase(super().to_python(value))

    def get_prep_value(self, value):
        return _lowercase(super().get_prep_value(value))

    def pre_save(self, model_instance, add):
        value = _lowercase(super().pre_save(model_instance, add))
        setattr(model_instance, self.attname, value)
        return value

def _lowercase(value):
    return value.strip().lower() if isinstance(value, str) else value