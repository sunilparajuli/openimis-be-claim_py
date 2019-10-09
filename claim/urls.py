from django.urls import path
from . import report_views

urlpatterns = [
    path('print/', report_views.print, name='print')
]
