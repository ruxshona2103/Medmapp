from core.models import Stage, Tag
from django.db import transaction

def get_default_stage():
    """
    Default bosqich: code_name='new' bo‘lsa o‘sha, bo‘lmasa order=1 (yoki eng past) ni oladi.
    """
    stage = Stage.objects.filter(code_name="new").order_by("order", "id").first()
    if stage:
        return stage
    return Stage.objects.order_by("order", "id").first()



def get_default_tag():
    # ixtiyoriy: default 'Normal' bo‘lsin desang, yoqmasa None qaytar.
    return Tag.objects.filter(name__iexact="Normal").first()
