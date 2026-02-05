import uuid

from django.conf import settings
from django.db import models


class Product(models.Model):
    """Simple listing that any user can create and manage."""

    class Status(models.TextChoices):
        PENDING = "pending", "รออนุมัติ"
        APPROVED = "approved", "อนุมัติ"
        REJECTED = "rejected", "ปฏิเสธ"

    class Condition(models.TextChoices):
        NEW = "new", "ใหม่"
        USED = "used", "มือสอง"
    
    class Category(models.TextChoices):
        ELECTRONICS = "electronics", "อิเล็กทรอนิกส์"
        FASHION = "fashion", "แฟชั่นและเครื่องแต่งกาย"
        HOME = "home", "บ้านและสวน"
        SPORTS = "sports", "กีฬาและกิจกรรมกลางแจ้ง"
        BOOKS = "books", "หนังสือ"
        TOYS = "toys", "ของเล่นและงานอดิเรก"
        BEAUTY = "beauty", "ความงาม"
        AUTOMOTIVE = "automotive", "ยานยนต์"
        PETS = "pets", "สัตว์เลี้ยง"
        OTHER = "other", "อื่นๆ"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="products",
    )
    name = models.CharField(max_length=150)
    category = models.CharField(max_length=80, choices=Category.choices, default=Category.OTHER)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True)
    condition = models.CharField(
        max_length=10,
        choices=Condition.choices,
        default=Condition.NEW,
    )
    image = models.ImageField(upload_to="products/", blank=True, null=True)
    is_sold = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_products",
    )
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rejected_products",
    )
    rejection_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        from django.urls import reverse

        return reverse("products:product_detail", args=[str(self.pk)])


class ProductImage(models.Model):
    """Additional images for a product."""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/gallery/')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for {self.product.name}"

