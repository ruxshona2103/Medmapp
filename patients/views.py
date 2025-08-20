from rest_framework import generics, permissions
from .serializers import PatientProfileSerializer


class PatientProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = PatientProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user.patient_profile
