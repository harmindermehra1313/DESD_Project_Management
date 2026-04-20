from django.shortcuts import render

# Create your views here.
def index(request):
    return render(request, "community/index.html")


def contact_us(request):
    context = {
        "contact_phone": "0800 00 1066",
        "contact_email": "BRFN@farmers.co.uk",
        "contact_address": "Coldharbour Lane, Bristol, BS16 1QY",
    }
    return render(request, "community/contact_us.html", context)