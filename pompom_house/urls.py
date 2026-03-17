from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth.views import LogoutView
from django.urls import include, path

from apartments import views as apartment_views
from messaging import views as messaging_views
from users import views as user_views

user_patterns = (
    [
        path('register/tenant/', user_views.register_tenant, name='register-tenant'),
        path('register/landlord/', user_views.register_landlord, name='register-landlord'),
        path('account/', user_views.account, name='account'),
    ],
    'users',
)

apartment_patterns = (
    [
        path('', apartment_views.listings, name='listings'),
        path('add/', apartment_views.create_apartment, name='add'),
        path('favourites/', apartment_views.favourites_page, name='favourites'),
        path('requests/', apartment_views.requests_page, name='requests'),
        path('requests/<int:request_id>/move-out/', apartment_views.request_move_out, name='request-move-out'),
        path('requests/<int:request_id>/approve-move-out/', apartment_views.approve_move_out, name='approve-move-out'),
        path('requests/<int:request_id>/<str:action>/', apartment_views.update_request, name='update-request'),
        path('<int:apartment_id>/request/', apartment_views.create_request, name='create-request'),
        path('<int:apartment_id>/relist/', apartment_views.relist_apartment, name='relist'),
        path('<int:apartment_id>/toggle-favourite/', apartment_views.toggle_favourite, name='toggle-favourite'),
        path('<int:apartment_id>/review/', apartment_views.save_review, name='save-review'),
        path('<int:apartment_id>/edit/', apartment_views.edit_apartment, name='edit'),
        path('<int:apartment_id>/delete/', apartment_views.delete_apartment, name='delete'),
        path('<int:apartment_id>/', apartment_views.apartment_detail, name='detail'),
    ],
    'apartments',
)

message_patterns = (
    [
        path('', messaging_views.conversation_list, name='list'),
        path('<int:conversation_id>/', messaging_views.conversation_detail, name='detail'),
    ],
    'messaging',
)

urlpatterns = [
    path('', user_views.landing, name='landing'),
    path('home/', user_views.home, name='home'),
    path('register/', user_views.register_choice, name='register-choice'),
    path('login/', user_views.login_choice, name='login'),
    path('login/<str:role>/', user_views.role_login, name='login-role'),
    path('password-reset/<str:role>/', user_views.password_reset, name='password-reset'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('users/', include(user_patterns, namespace='users')),
    path('apartments/', include(apartment_patterns, namespace='apartments')),
    path('messages/', include(message_patterns, namespace='messaging')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
