from django.shortcuts import render
from BRFN.decorators import admin_required

# Create your views here.

def home(request):
    return render(request, "home/home.html")

@admin_required
def dashboard(request):
    return render(request, "home/dashboard.html")
