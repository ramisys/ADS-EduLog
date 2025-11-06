from django.shortcuts import render
from django.http import HttpResponse
from datetime import datetime

def index(request):
    return HttpResponse(f"EduLog system is working successfully in {datetime.now()}.")
   
