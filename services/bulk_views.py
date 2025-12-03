# services/bulk_views.py
# Bulk operations for tags management

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.db import transaction

from core.models import Tag
from .models import (
    VisaRequest, TransferRequest, TranslatorRequest,
    SimCardRequest, Hotel, Booking
)


class BulkUpdateTagsView(APIView):
    """
    Bir nechta orderlarning tagslarini bir vaqtning o'zida yangilash
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Bulk tags yangilash",
        operation_description="Bir nechta orderlarning tagslarini bir vaqtning o'zida yangilash",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['updates'],
            properties={
                'updates': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    description="Yangilanadigan orderlar ro'yxati",
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        required=['type', 'id', 'tags'],
                        properties={
                            'type': openapi.Schema(
                                type=openapi.TYPE_STRING,
                                enum=['visa', 'simcard', 'transfer', 'translator', 'hotel', 'booking'],
                                description="Order turi"
                            ),
                            'id': openapi.Schema(type=openapi.TYPE_INTEGER, description="Order ID"),
                            'tags': openapi.Schema(
                                type=openapi.TYPE_ARRAY,
                                items=openapi.Schema(type=openapi.TYPE_INTEGER),
                                description="Tag IDlar ro'yxati"
                            ),
                        }
                    )
                )
            },
            example={
                "updates": [
                    {"type": "visa", "id": 1, "tags": [1, 2]},
                    {"type": "simcard", "id": 2, "tags": [3]},
                ]
            }
        ),
        responses={
            200: openapi.Response(
                description="Muvaffaqiyatli yangilandi",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'success': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                        'updated_count': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'details': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_OBJECT)),
                    }
                )
            ),
            400: "Bad Request"
        },
        tags=["bulk-operations"]
    )
    def post(self, request):
        """
        Bulk tags update

        Request:
        {
            "updates": [
                {"type": "visa", "id": 1, "tags": [1, 2]},
                {"type": "simcard", "id": 2, "tags": [3, 4]}
            ]
        }
        """
        updates = request.data.get('updates', [])

        if not updates or not isinstance(updates, list):
            return Response(
                {'detail': 'updates ro\'yxati kiritilishi shart'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Model mapping
        MODEL_MAP = {
            'visa': VisaRequest,
            'simcard': SimCardRequest,
            'transfer': TransferRequest,
            'translator': TranslatorRequest,
            'hotel': Hotel,
            'booking': Booking,
        }

        results = []
        updated_count = 0

        with transaction.atomic():
            for update_item in updates:
                item_type = update_item.get('type')
                item_id = update_item.get('id')
                tag_ids = update_item.get('tags', [])

                if not item_type or not item_id:
                    results.append({
                        'type': item_type,
                        'id': item_id,
                        'status': 'error',
                        'message': 'type va id kiritilishi shart'
                    })
                    continue

                # Model olish
                model_class = MODEL_MAP.get(item_type)
                if not model_class:
                    results.append({
                        'type': item_type,
                        'id': item_id,
                        'status': 'error',
                        'message': f'Noto\'g\'ri type: {item_type}'
                    })
                    continue

                # Object olish
                try:
                    obj = model_class.objects.get(id=item_id)
                except model_class.DoesNotExist:
                    results.append({
                        'type': item_type,
                        'id': item_id,
                        'status': 'error',
                        'message': 'Object topilmadi'
                    })
                    continue

                # Permission check (faqat o'z orderlarini yangilashi mumkin)
                user = request.user
                if hasattr(obj, 'user') and obj.user != user:
                    if user.role not in ['admin', 'superadmin', 'operator']:
                        results.append({
                            'type': item_type,
                            'id': item_id,
                            'status': 'error',
                            'message': 'Ruxsat yo\'q'
                        })
                        continue

                # Tags yangilash
                if tag_ids is not None:
                    # Validate tag IDs
                    valid_tags = Tag.objects.filter(id__in=tag_ids)
                    if len(valid_tags) != len(tag_ids):
                        invalid_ids = set(tag_ids) - set(valid_tags.values_list('id', flat=True))
                        results.append({
                            'type': item_type,
                            'id': item_id,
                            'status': 'warning',
                            'message': f'Ba\'zi taglar topilmadi: {list(invalid_ids)}',
                            'updated': True
                        })

                    obj.tags.set(valid_tags)
                    updated_count += 1
                    results.append({
                        'type': item_type,
                        'id': item_id,
                        'status': 'success',
                        'tags': list(obj.tags.values_list('id', flat=True))
                    })

        return Response({
            'success': True,
            'updated_count': updated_count,
            'details': results
        }, status=status.HTTP_200_OK)


class TagManagementView(APIView):
    """
    Tag orqali orderlarni boshqarish (Stage kabi)
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Tag ga orderlar qo'shish",
        operation_description="Tanlangan tag ga orderlarni qo'shish",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['items'],
            properties={
                'items': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        required=['type', 'id'],
                        properties={
                            'type': openapi.Schema(
                                type=openapi.TYPE_STRING,
                                enum=['visa', 'simcard', 'transfer', 'translator', 'hotel', 'booking']
                            ),
                            'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                        }
                    )
                )
            },
            example={
                "items": [
                    {"type": "visa", "id": 1},
                    {"type": "simcard", "id": 2}
                ]
            }
        ),
        responses={200: "Muvaffaqiyatli qo'shildi"},
        tags=["tag-management"]
    )
    def post(self, request, tag_id):
        """
        Tag ga orderlar qo'shish

        POST /api/tags/{tag_id}/assign-items/
        """
        try:
            tag = Tag.objects.get(id=tag_id)
        except Tag.DoesNotExist:
            return Response(
                {'detail': 'Tag topilmadi'},
                status=status.HTTP_404_NOT_FOUND
            )

        items = request.data.get('items', [])

        MODEL_MAP = {
            'visa': VisaRequest,
            'simcard': SimCardRequest,
            'transfer': TransferRequest,
            'translator': TranslatorRequest,
            'hotel': Hotel,
            'booking': Booking,
        }

        added_count = 0
        results = []

        with transaction.atomic():
            for item in items:
                item_type = item.get('type')
                item_id = item.get('id')

                model_class = MODEL_MAP.get(item_type)
                if not model_class:
                    continue

                try:
                    obj = model_class.objects.get(id=item_id)
                    obj.tags.add(tag)
                    added_count += 1
                    results.append({
                        'type': item_type,
                        'id': item_id,
                        'status': 'added'
                    })
                except model_class.DoesNotExist:
                    results.append({
                        'type': item_type,
                        'id': item_id,
                        'status': 'not_found'
                    })

        return Response({
            'success': True,
            'tag_id': tag_id,
            'tag_name': tag.name,
            'added_count': added_count,
            'details': results
        }, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_summary="Tag dan orderlarni o'chirish",
        operation_description="Tanlangan tag dan orderlarni o'chirish",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['items'],
            properties={
                'items': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'type': openapi.Schema(type=openapi.TYPE_STRING),
                            'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                        }
                    )
                )
            }
        ),
        responses={200: "Muvaffaqiyatli o'chirildi"},
        tags=["tag-management"]
    )
    def delete(self, request, tag_id):
        """
        Tag dan orderlarni o'chirish

        DELETE /api/tags/{tag_id}/remove-items/
        """
        try:
            tag = Tag.objects.get(id=tag_id)
        except Tag.DoesNotExist:
            return Response(
                {'detail': 'Tag topilmadi'},
                status=status.HTTP_404_NOT_FOUND
            )

        items = request.data.get('items', [])

        MODEL_MAP = {
            'visa': VisaRequest,
            'simcard': SimCardRequest,
            'transfer': TransferRequest,
            'translator': TranslatorRequest,
            'hotel': Hotel,
            'booking': Booking,
        }

        removed_count = 0

        with transaction.atomic():
            for item in items:
                item_type = item.get('type')
                item_id = item.get('id')

                model_class = MODEL_MAP.get(item_type)
                if not model_class:
                    continue

                try:
                    obj = model_class.objects.get(id=item_id)
                    obj.tags.remove(tag)
                    removed_count += 1
                except model_class.DoesNotExist:
                    pass

        return Response({
            'success': True,
            'tag_id': tag_id,
            'removed_count': removed_count
        }, status=status.HTTP_200_OK)
