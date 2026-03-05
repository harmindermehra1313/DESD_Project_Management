from django.shortcuts import render
from BRFN.decorators import admin_required

# Create your views here.

@admin_required
def index(request):
    return render(request, "admin_records/index.html")