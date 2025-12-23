from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.views.generic import (
    TemplateView,
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)
from django.db.models import Q

from .forms import ProductForm
from .models import Product, ProductImage

class HomePageView(TemplateView):
    template_name = "home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Exclude products that have an associated auction (auction__isnull=False means has auction)
        products = Product.objects.exclude(auction__isnull=False)
        ctx["new_products"] = products.order_by("-created_at")[:6]  # 1 row (6 items in xl)
        ctx["featured_products"] = products.order_by("-price")[:6]
        ctx["spotlight_products"] = products.order_by("-updated_at")[:6]
        return ctx

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
        # Base queryset excludes auction products
        qs = Product.objects.exclude(auction__isnull=False)
        
        # Search functionality (search in name and category only)
        search_query = self.request.GET.get('q', '').strip()
        if search_query:
            qs = qs.filter(
                Q(name__icontains=search_query) |
                Q(category__icontains=search_query)
            )
        
        # Filter by category if provided
        category = self.request.GET.get('category')
        if category:
            qs = qs.filter(category=category)
        
        return qs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['selected_category'] = self.request.GET.get('category', '')
        context['search_query'] = self.request.GET.get('q', '')
        context['categories'] = Product.Category.choices
        return context


class ProductDetailView(DetailView):
    model = Product
    template_name = "products/product_detail.html"
    context_object_name = "product"


class ProductCreateView(LoginRequiredMixin, CreateView):
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

