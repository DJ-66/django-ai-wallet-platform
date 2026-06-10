
from django.contrib import admin
from django.http import HttpResponse
from django.urls import path, include
from django.contrib.auth import views as auth_views
from auctions.views import activate_view
from auctions import views as auction_views
from django.shortcuts import redirect
from django.utils.translation import get_language_from_request

def legacy_user_profile_redirect(request, username):
    return redirect("public_profile_root", username=username, permanent=True)

def home(request):
    lang = request.GET.get("lang") or get_language_from_request(request)

    is_spanish = lang and lang.startswith("es")

    if is_spanish:
        title_line = "Economía de Creadores ✦ Amigos IA ✦ Subastas de Centavos"
        create = "Crear."
        connect = "Conectar."
        monetize = "Monetizar!"
        feed = "Explorar Feed"
        signup = "Registrarse"
        login = "Iniciar sesión"
        html_lang = "es"
    else:
        title_line = "Creator Economy ✦ AI Friends ✦ Penny Auctions"
        create = "Create."
        connect = "Connect."
        monetize = "Monetize!"
        feed = "Explore Feed"
        signup = "Sign Up"
        login = "Login"
        html_lang = "en"

    return HttpResponse(f"""
<!DOCTYPE html>
<html lang="{html_lang}">
<head>
  <title>Fanz.to</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link rel="icon"
      href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🤩</text></svg>">
<style>
.hero-logo {{
    text-align: center;
}}

.hero-emoji {{
    display: block;
    font-size: 4rem;
    margin-bottom: 10px;
}}

.lang-pills {{
    position: absolute;
    top: 15px;
    right: 15px;
    z-index: 1000;
}}

.lang-pill {{
    display: inline-block;
    padding: 6px 10px;
    margin: 0 2px;
    border-radius: 999px;
    background: rgba(255,255,255,.12);
    color: white;
    text-decoration: none;
    font-weight: 600;
    font-size: 0.85rem;
}}

.lang-pill:hover {{
    background: rgba(255,255,255,.22);
}}

.flag-svg {{
    display: inline-block;
    width: 18px;
    height: 12px;
    margin-right: 6px;
    border-radius: 3px;
    background-size: cover;
    background-position: center;
    vertical-align: -1px;
}}

.flag-us {{
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 7410 3900'%3E%3Crect width='7410' height='3900' fill='%23b22234'/%3E%3Cpath d='M0 450h7410v300H0zm0 600h7410v300H0zm0 600h7410v300H0zm0 600h7410v300H0zm0 600h7410v300H0zm0 600h7410v300H0' fill='%23fff'/%3E%3Crect width='2964' height='2100' fill='%233c3b6e'/%3E%3C/svg%3E");
}}

.flag-py {{
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 5 3'%3E%3Cpath fill='%23d52b1e' d='M0 0h5v1H0z'/%3E%3Cpath fill='%23fff' d='M0 1h5v1H0z'/%3E%3Cpath fill='%2300338e' d='M0 2h5v1H0z'/%3E%3C/svg%3E");
}}

</style>
</head>
<body style="font-family:Arial,sans-serif;text-align:center;padding:60px 20px;background:#0f1020;color:white;">
  <div class="lang-pills">
    <a href="/?lang=en" class="lang-pill"><span class="flag-svg flag-us"></span> EN</a>
    <a href="/?lang=es" class="lang-pill"><span class="flag-svg flag-py"></span> ES</a>
  </div>

  <div class="hero-logo">
      <span class="hero-emoji">🤩</span>
  </div>

  <h1 style="font-size:80px;margin-bottom:10px;">Fanz.to</h1>
  <h2 style="font-weight:400;margin-bottom:20px;">{title_line}</h2>

  <p style="font-size:28px;line-height:1.4;margin-bottom:36px;">
   🤔💭 {create}<br>
   𐦂𖨆𐀪𖠋 {connect}<br>
   💰❤️ {monetize}
  </p>

  <p>
    <a href="/auctions/feed/" style="display:inline-block;margin:8px;padding:14px 22px;background:#6c5ce7;color:white;text-decoration:none;border-radius:10px;">{feed}</a>
    <a href="/auctions/signup/" style="display:inline-block;margin:8px;padding:14px 22px;background:#00b894;color:white;text-decoration:none;border-radius:10px;">{signup}</a>
    <a href="/accounts/login/" style="display:inline-block;margin:8px;padding:14px 22px;background:#2d3436;color:white;text-decoration:none;border-radius:10px;">{login}</a>
  </p>
</body>
</html>
""")


urlpatterns = [
    path("", home),
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("auctions/", include("auctions.urls")),
    path("u/<str:username>/", legacy_user_profile_redirect, name="legacy_public_profile"),
    path('login/', auth_views.LoginView.as_view(
        template_name='auth/login.html'
    ), name='login'),

    path('logout/', auth_views.LogoutView.as_view(
        next_page='login'
    ), name='logout'),

    # ✅ ADD THIS
    path("activate/<uidb64>/<token>/", activate_view, name="activate"),
    path("ai/", include("auctions.ai_urls")),
    path("<str:username>/", auction_views.public_profile, name="public_profile_root"),

]

