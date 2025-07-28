from modeltranslation.translator import register, TranslationOptions
from .models import Departments

@register(Departments)
class DepartmentsTranslationOptions(TranslationOptions):
    fields = ("name", "description")
