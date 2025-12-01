from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q
from django.urls import reverse_lazy
from django.views.generic import (
    TemplateView,
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from .forms import ProductForm
from .models import Product, ProductImage

class HomePageView(TemplateView):
    template_name = "home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Exclude products that have an associated auction (auction__isnull=False means has auction)
        published = Product.objects.filter(status=Product.Status.PUBLISHED).exclude(auction__isnull=False)
        ctx["new_products"] = published.order_by("-created_at")[:8]
        ctx["featured_products"] = published.order_by("-price")[:8]
        ctx["spotlight_products"] = published.order_by("-updated_at")[:8]
        return ctx


class SellerRequiredMixin(UserPassesTestMixin):
    """Ensure the current user is marked as seller."""

    raise_exception = True

    def test_func(self):
        user = self.request.user
        return user.is_authenticated and getattr(user, "is_seller", False)


class ProductOwnerRequiredMixin(UserPassesTestMixin):
    """Allow access only to the product owner or superuser."""

    raise_exception = True

    def test_func(self):
        product = self.get_object()
        user = self.request.user
        return user.is_authenticated and (user.is_superuser or product.seller_id == user.id)


class ProductListView(ListView):
    model = Product
    context_object_name = "products"
    template_name = "products/product_list.html"
    paginate_by = 12

    def get_queryset(self):
        user = self.request.user
        # Base queryset excludes auction products
        base_qs = Product.objects.exclude(auction__isnull=False)
        
        if user.is_authenticated:
            if user.is_superuser:
                return base_qs
            return base_qs.filter(
                Q(status=Product.Status.PUBLISHED) | Q(seller=user)
            )
        return base_qs.filter(status=Product.Status.PUBLISHED)


class ProductDetailView(DetailView):
    model = Product
    template_name = "products/product_detail.html"
    context_object_name = "product"

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated:
            if user.is_superuser:
                return Product.objects.all()
            return Product.objects.filter(
                Q(status=Product.Status.PUBLISHED) | Q(seller=user)
            )
        return Product.objects.filter(status=Product.Status.PUBLISHED)


class ProductCreateView(LoginRequiredMixin, SellerRequiredMixin, CreateView):
    model = Product
    form_class = ProductForm
    template_name = "products/product_form.html"
    # success_url = '/products/' # ถ้าบันทึกสำเร็จแล้ว error ว่า No URL to redirect ให้เปิดบรรทัดนี้ครับ

    def form_valid(self, form):
        form.instance.seller = self.request.user
        response = super().form_valid(form)
        
        # Handle multiple images
        images = self.request.FILES.getlist('images')
        if images:
            # Use first image as main product image if not set
            if not self.object.image and len(images) > 0:
                self.object.image = images[0]
                self.object.save()
                images = images[1:]  # Remaining images
            
            # Save remaining images as ProductImage instances
            for img in images:
                ProductImage.objects.create(product=self.object, image=img)
                
        return response


    #ดักจับ Error แล้วปริ้นท์บอกใน Terminal
    def form_invalid(self, form):
        print("FORM ERRORS:", form.errors)
        return super().form_invalid(form)


class ProductUpdateView(LoginRequiredMixin, ProductOwnerRequiredMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = "products/product_form.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        
        # Handle image deletions
        deleted_ids = self.request.POST.get('deleted_image_ids', '')
        if deleted_ids:
            ids = deleted_ids.split(',')
            for img_id in ids:
                if img_id == 'main':
                    # Delete main image
                    self.object.image.delete(save=False)
                    self.object.image = None
                    self.object.save()
                elif img_id:
                    # Delete gallery image
                    ProductImage.objects.filter(id=img_id, product=self.object).delete()
        
        # Handle additional images
        images = self.request.FILES.getlist('images')
        
        # If main image is missing (was deleted or never existed) and we have new uploads,
        # use the first new upload as main image
        if not self.object.image and images:
            self.object.image = images[0]
            self.object.save()
            images = images[1:]
            
        for img in images:
            ProductImage.objects.create(product=self.object, image=img)
                
        return response


class ProductDeleteView(LoginRequiredMixin, ProductOwnerRequiredMixin, DeleteView):
    model = Product
    template_name = "products/product_confirm_delete.html"
    success_url = reverse_lazy("products:product_list")

