from django.urls import path

from .views import (
    ProductCreateView,
    ProductDeleteView,
    ProductDetailView,
    ProductListView,
    ProductUpdateView,
)

app_name = "products"

urlpatterns = [
    path("", ProductListView.as_view(), name="product_list"),
    path("sell/", ProductCreateView.as_view(), name="product_create"),
    path("<uuid:pk>/", ProductDetailView.as_view(), name="product_detail"),
    path("<uuid:pk>/edit/", ProductUpdateView.as_view(), name="product_update"),
    path("<uuid:pk>/delete/", ProductDeleteView.as_view(), name="product_delete"),
]
