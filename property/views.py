# views.py
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from .models import Property, State, City, PropertyType
from listings.models import SavedProperty



def homepage(request):
    """Homepage with property search"""
    
    # Get all states for dropdown
    states = State.objects.filter(is_active=True)
    
    # Get property types
    property_types = PropertyType.objects.all()
    
    # Featured properties
    featured_properties = Property.objects.filter(
        is_featured=True
    ).select_related('state', 'city', 'property_type', 'status')[:6]
    
    # Get all properties for display
    all_properties = Property.objects.select_related(
        'state', 'city', 'property_type', 'status'
    )[:10]
    
    # Get pricing packages for "Sell Your Properties" section
    from listings.models import ListingPackage
    pricing_packages = ListingPackage.objects.filter(is_active=True).order_by('price')[:4]
    
    # Get recent blog posts
    from blogs.models import Post
    from django.utils import timezone
    recent_blog_posts = Post.objects.select_related('author', 'category').order_by('-publish')[:3]
    print(f"{recent_blog_posts}")
    
    context = {
        'states': states,
        'property_types': property_types,
        'featured_properties': featured_properties,
        'all_properties': all_properties,
        'pricing_packages': pricing_packages,
        'recent_blog_posts': recent_blog_posts,
    }
    
    return render(request, 'estate/index.html', context)


def get_cities_by_state(request):
    """AJAX endpoint to get cities for a selected state"""
    state_id = request.GET.get('state_id')
    
    if not state_id:
        return JsonResponse({'cities': []})
    
    try:
        cities = City.objects.filter(
            state_id=state_id,
            is_active=True
        ).values('id', 'name')
        
        return JsonResponse({
            'cities': list(cities)
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


def search_properties(request):
    """Search/filter properties"""
    
    # Get filter parameters
    state_id = request.GET.get('state_type')
    city_id = request.GET.get('city_type')
    property_type = request.GET.get('property_type')
    price_range = request.GET.get('price_range')
    bedrooms = request.GET.get('bedrooms')
    bathrooms = request.GET.get('bathrooms')
    
    # Start with all properties
    properties = Property.objects.select_related(
        'state', 'city', 'property_type', 'status'
    )
    
    # Apply filters
    if state_id:
        properties = properties.filter(state_id=state_id)
    
    if city_id:
        properties = properties.filter(city_id=city_id)
    
    if property_type:
        properties = properties.filter(property_type__name=property_type)
    
    if price_range:
        if price_range == '1200000+':
            properties = properties.filter(price__gte=1200000)
        elif '-' in price_range:
            min_price, max_price = price_range.split('-')
            properties = properties.filter(price__gte=int(min_price), price__lte=int(max_price))
    
    if bedrooms:
        if bedrooms == '5+':
            properties = properties.filter(bedrooms__gte=5)
        else:
            properties = properties.filter(bedrooms=int(bedrooms))
    
    if bathrooms:
        if bathrooms == '4+':
            properties = properties.filter(bathrooms__gte=4)
        else:
            properties = properties.filter(bathrooms=int(bathrooms))
    
    context = {
        'properties': properties,
        'search_params': request.GET,
    }
    
    return render(request, 'estate/search_results.html', context)



def get_properties_details(request, slug):
    property_detail = get_object_or_404(Property, slug=slug)
    saved_property = None
    if request.user.is_authenticated:
        try:
            saved_property = SavedProperty.objects.get(user=request.user, property=property_detail)
        except SavedProperty.DoesNotExist:
            saved_property = None
        
    if request.method == "POST":
        property_saved = SavedProperty.objects.create(user=request.user, property=property_detail)
        try:
            return JsonResponse({
                "status": "success",
                "message": f"{property_detail.title} saved Successfully"
            })
        except Exception as e:
            return JsonResponse({
                "status": "error",
                "message": f"Error Saving Property: {str(e)}"
            })
    else:
        pass          
            
    # Track referral if 'ref' param is present
    ref_code = request.GET.get('ref')
    if ref_code:
        from agents.utils import store_property_referral
        store_property_referral(request, property_detail.id, ref_code)
    
    # Generate referral link for logged-in agents
    referral_link = None
    if request.user.is_authenticated and hasattr(request.user, 'agent_profile'):
        from agents.utils import generate_property_referral_url
        referral_link = generate_property_referral_url(request, property_detail, request.user.agent_profile)
        
    context = {
        'property': property_detail,
        'referral_link': referral_link,
        'saved_property': saved_property is not None,
    }
    return render(request, 'estate/property-details.html', context)


def property_list(request):
    """List all properties with pagination, filtering, and sorting"""
    from django.core.paginator import Paginator
    from django.db.models import Q
    
    # Base Queryset
    properties_list = Property.objects.select_related(
        'state', 'city', 'property_type', 'status', 'listed_by'
    ).filter(status__name__in=['for_sale', 'for_rent', 'pending']) # Show active listings
    
    # --- Filtering ---
    
    # Keyword Search (e.g. from global search)
    query = request.GET.get('q')
    if query:
        properties_list = properties_list.filter(
            Q(title__icontains=query) | 
            Q(description__icontains=query) |
            Q(address__icontains=query) |
            Q(city__name__icontains=query)
        )

    # Property Type
    prop_type = request.GET.get('type')
    if prop_type and prop_type != 'All Types':
        properties_list = properties_list.filter(property_type__name=prop_type)

    # Price Range
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    if min_price:
        properties_list = properties_list.filter(price__gte=min_price)
    if max_price:
        properties_list = properties_list.filter(price__lte=max_price)

    # Bedrooms
    bedrooms = request.GET.get('bedrooms')
    if bedrooms and bedrooms != 'Any':
        if '+' in bedrooms:
            val = int(bedrooms.replace('+', ''))
            properties_list = properties_list.filter(bedrooms__gte=val)
        else:
            properties_list = properties_list.filter(bedrooms=int(bedrooms))

    # Bathrooms
    bathrooms = request.GET.get('bathrooms')
    if bathrooms and bathrooms != 'Any':
        if '+' in bathrooms:
            val = int(bathrooms.replace('+', ''))
            properties_list = properties_list.filter(bathrooms__gte=val)
        else:
            properties_list = properties_list.filter(bathrooms=int(bathrooms))
            
    # Location (Text search for City/State/Address)
    location = request.GET.get('location')
    if location:
        properties_list = properties_list.filter(
            Q(city__name__icontains=location) | 
            Q(state__name__icontains=location) |
            Q(address__icontains=location)
        )
        
    # Features
    if request.GET.get('garage'):
        properties_list = properties_list.filter(has_garage=True)
    if request.GET.get('pool'):
        properties_list = properties_list.filter(has_pool=True)
    if request.GET.get('balcony'):
        properties_list = properties_list.filter(has_balcony=True)
    if request.GET.get('garden'):
        properties_list = properties_list.filter(has_garden=True)

    # --- Sorting ---
    sort_by = request.GET.get('sort', 'newest')
    if sort_by == 'price_asc':
        properties_list = properties_list.order_by('price')
    elif sort_by == 'price_desc':
        properties_list = properties_list.order_by('-price')
    elif sort_by == 'views':
        properties_list = properties_list.order_by('-views_count')
    else: # newest
        properties_list = properties_list.order_by('-created_at')

    
    # --- Pagination ---
    paginator = Paginator(properties_list, 9) 
    page_number = request.GET.get('page')
    properties = paginator.get_page(page_number)
    
    # Get Filter Options for Sidebar
    property_types = PropertyType.objects.all()
    
    # Sidebar Featured Properties (limit 3)
    featured_sidebar = Property.objects.filter(is_featured=True).exclude(status__name='sold').order_by('-created_at')[:3]
    
    context = {
        'properties': properties,
        'property_types': property_types,
        'search_params': request.GET, # To keep filter values in inputs
        'featured_sidebar': featured_sidebar,
    }
    
    return render(request, 'estate/properties.html', context)
