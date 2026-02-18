from django.shortcuts import render

# Create your views here.
def index(request):
    return render(request, "accounts/index.html")

# TBC - loads placeholder form based on selected role but doesn't save anything
def register(request):
    role = request.GET.get("role", "customer")

    if request.method == "POST":
        # TBC - save, currently print
        print("Received POST for role:", request.POST.get("role"))
        print("Form data:", request.POST)
        return render(request, "accounts/register_success.html")

    return render(request, "accounts/register.html", {
        "role": role,
    })