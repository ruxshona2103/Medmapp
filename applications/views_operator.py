from rest_framework import generics, permissions, status
from rest_framework.response import Response
from .models import Application
from .serializers import ApplicationSerializer


class OperatorApplicationsView(generics.ListAPIView):
    """
    Operator faqat login bo‘lgan holda barcha arizalarni ko‘ra oladi.
    """
    serializer_class = ApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'operator':
            return Application.objects.all().order_by('-created_at')
        return Application.objects.none()


class ChangeApplicationStatusView(generics.UpdateAPIView):
    """
    Operator ariza statusini o‘zgartira oladi.
    """
    serializer_class = ApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, *args, **kwargs):
        user = request.user
        if user.role != 'operator':
            return Response({'detail': 'Siz operator emassiz!'}, status=status.HTTP_403_FORBIDDEN)

        try:
            application = Application.objects.get(pk=kwargs['pk'])
        except Application.DoesNotExist:
            return Response({'detail': 'Ariza topilmadi!'}, status=status.HTTP_404_NOT_FOUND)

        new_status = request.data.get('status')
        if not new_status:
            return Response({'detail': 'Status ko‘rsatilmagan!'}, status=status.HTTP_400_BAD_REQUEST)

        application.status = new_status
        application.save()
        return Response({'detail': 'Status yangilandi', 'status': application.status})
