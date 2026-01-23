from django.shortcuts import render

# Create your views here.






def about_page(request):
    return render(request, "estate/about.html")



def properties_page(request):
    """_summary_

    Args:
        request (_type_): _description_
    """
    return render(request, "estate/properties.html")







def agents(request):
    return render(request, "estate/agents.html")


def agents_details(request):
    return render(request, "estate/agent-profile.html")




def service(request):
    return render(request, "estate/services.html")


def service_detail_page(request):
    return render(request, "estate/service-details.html")


def contact(request):
    return render(request, "estate/contact.html")



def properties_details(request):
    return render(request, "estate/property-details.html")



def dashboard_user(request):
    return render(request, "estate/dashboard.html")


