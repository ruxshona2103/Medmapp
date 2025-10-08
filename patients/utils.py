# patients/utils.py
from core.models import Stage, Tag

# patients/utils.py
from django.db import transaction
from core.models import Stage

def get_default_stage():
    """
    Default bosqichni qaytaradi:
      1) 'new' yoki 'yangi' code_name bo'lgan bo'lsa — shuni
      2) bo'lmasa order,id bo'yicha birinchi bosqich
      3) umuman hech narsa bo'lmasa — standart setni yaratib, 'new'ni qaytaradi
    """
    stage = (
        Stage.objects.filter(code_name__in=["new", "yangi"])
        .order_by("order", "id")
        .first()
        or Stage.objects.order_by("order", "id").first()
    )
    if stage:
        return stage

    # ——— Bazada bosqichlar yo‘q: standartlarini yaratamiz
    with transaction.atomic():
        defaults = [
            # code_name,        title,              order, color
            ("new",             "Yangi",            1,     "#4F46E5"),
            ("documents",       "Hujjatlar",        2,     "#0EA5E9"),
            ("payment",         "To‘lov",           3,     "#10B981"),
            ("trip",            "Safar",            4,     "#F59E0B"),
            ("response_letters","Javob xatlari",    5,     "#EF4444"),
        ]
        Stage.objects.bulk_create([
            Stage(code_name=c, title=t, order=o, color=col) for c, t, o, col in defaults
        ])
    return Stage.objects.get(code_name="new")

def get_default_tag():
    # ixtiyoriy: default 'Normal' bo‘lsin desang, yoqmasa None qaytar.
    return Tag.objects.filter(name__iexact="Normal").first()
