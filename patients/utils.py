# patients/utils.py
from core.models import Stage, Tag

def get_default_stage():
    # 1) code_name bo‘yicha (barqaror)
    s = Stage.objects.filter(code_name__iexact="new").first()
    if s:
        return s
    # 2) nomi bo‘yicha (UZ/EN)
    s = Stage.objects.filter(title__iexact="Yangi").first() or Stage.objects.filter(title__iexact="New").first()
    if s:
        return s
    # 3) tartib bo‘yicha birinchi
    return Stage.objects.order_by("order", "id").first()

def get_default_tag():
    # ixtiyoriy: default 'Normal' bo‘lsin desang, yoqmasa None qaytar.
    return Tag.objects.filter(name__iexact="Normal").first()
