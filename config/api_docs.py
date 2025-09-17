# config/api_docs.py
import re
from drf_yasg.generators import OpenAPISchemaGenerator
from django.utils.functional import cached_property

API_PREFIX = r"^/api/patients"

ALLOWED = {
    "admin":   [r".*"],  # hammasi
    "operator":[
        rf"{API_PREFIX}/patients/.*$",
        rf"{API_PREFIX}/tags/.*$",
        rf"{API_PREFIX}/stages/.*$",
        rf"{API_PREFIX}/documents/.*$",
        rf"{API_PREFIX}/response-letters/.*$",
    ],
    "patient":[
        rf"{API_PREFIX}/profile/me/$",
        rf"{API_PREFIX}/documents/.*$",
        rf"{API_PREFIX}/contracts/\d+/approve/$",
    ],
}

def _role(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return "patient"  # mehmon uchun minimal
    if getattr(user, "is_superuser", False):
        return "admin"
    raw = getattr(user, "role", "")
    v = str(raw).strip().lower()
    return {"bemor":"patient"}.get(v, v) or "patient"

class RoleAwareGenerator(OpenAPISchemaGenerator):
    @cached_property
    def _compiled(self):
        return {k: [re.compile(p) for p in v] for k, v in ALLOWED.items()}

    def get_schema(self, request=None, public=False):
        schema = super().get_schema(request=request, public=public)
        if not getattr(schema, "paths", None):
            return schema
        role = _role(request) if request else "patient"
        regexes = self._compiled.get(role, [])
        original = getattr(schema.paths, "_paths", {})
        if role == "admin":  # hammasi
            return schema
        new_paths = {path: item for path, item in original.items()
                     if any(r.match(path) for r in regexes)}
        schema.paths._paths = new_paths
        return schema
