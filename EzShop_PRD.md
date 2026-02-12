# EzShop — Product Specification Document

## Overview

**EzShop** is a Thai e-commerce web application built with Django. It serves as a marketplace platform where users can buy and sell both regular products (marketplace) and auction items. The platform features escrow-based payments via Stripe, real-time chat between buyers and sellers, live streaming via Agora, shipment tracking via 17TRACK, and an admin approval workflow.

**Tech Stack:** Django 5.x, PostgreSQL, Stripe (payments), Agora (live stream), 17TRACK (shipment tracking), Django Channels (WebSocket for real-time chat & notifications)

**Base URL:** `http://localhost:8000`

---

## 1. User Authentication & Accounts

### 1.1 Registration
- **URL:** `/users/register/`
- Users register with **phone number** (used as username), **email**, **first name**, **last name**, and **password**
- Phone number must be unique
- Email must be unique
- After registration, redirect to login page

### 1.2 Login
- **URL:** `/users/login/`
- Login with **phone number** and **password**
- Redirect to homepage after successful login

### 1.3 Logout
- **URL:** `/users/logout/`
- Logs user out and redirects to homepage

### 1.4 Password Reset
- **URL:** `/users/password-reset/`
- Users can reset password via email

### 1.5 User Profile
- **URL:** `/users/profile/`
- Displays user information: name, email, phone, bio, profile picture, member since, member ID
- Shows user's **marketplace products** and **auction products** in separate tabs
- Shows reviews received by the user
- Profile can be edited at `/users/profile/edit/`

### 1.6 Profile Update
- **URL:** `/users/profile/edit/`
- Users can update: first name, last name, email, phone, bio, profile picture

---

## 2. Products (Marketplace)

### 2.1 Product Listing
- **URL:** `/products/`
- Displays all approved, unsold marketplace products (excludes auction products)
- Supports **search** by product name and category
- Supports **category filtering**
- Paginated (12 products per page)
- Categories: Electronics, Fashion, Home, Sports, Books, Toys, Beauty, Automotive, Pets, Other

### 2.2 Product Detail
- **URL:** `/products/<uuid:pk>/`
- Shows full product details: name, description, price, condition, category, seller info, images
- Product conditions: New, Used
- Admin/staff can view all products; regular users see only approved products or their own

### 2.3 Create Product
- **URL:** `/products/create/`
- Requires login
- Fields: name, category, price, description, condition, images (multiple upload supported)
- New products get status **"Pending"** and must be approved by admin
- If creator is admin/staff, product is auto-approved
- First uploaded image becomes the main product image; additional images are stored as gallery images

### 2.4 Update Product
- **URL:** `/products/<uuid:pk>/edit/`
- Only product owner or superuser can edit
- Editing resets product status back to **"Pending"** for re-approval (unless editor is admin)
- Supports deleting existing images and uploading new ones

### 2.5 Delete Product
- **URL:** `/products/<uuid:pk>/delete/`
- Only product owner or superuser can delete
- Shows confirmation page before deletion

---

## 3. Auctions

### 3.1 Auction List
- **URL:** `/auctions/`
- Displays all live auctions
- Only shows auctions where associated product is approved

### 3.2 Auction Detail
- **URL:** `/auctions/<uuid:pk>/`
- Shows auction details: product info, starting price, current highest bid, minimum increment, reserve price, time remaining
- Real-time bid updates via WebSocket
- Users can place bids (must exceed current highest bid + minimum increment)
- Seller cannot bid on their own auction

### 3.3 Create Auction
- **URL:** `/auctions/create/`
- Requires login
- Creates both a Product and an Auction simultaneously
- Fields: product details + starting price, minimum increment, reserve price (optional), duration in minutes
- Auction status: Live, Ended, Canceled

### 3.4 Auction Closing
- When auction timer expires, auction closes automatically
- Highest bidder wins (if bid meets reserve price, when set)
- Winner gets: email notification, in-app notification, auto-created Order, auto-created ChatRoom with seller
- If reserve price not met: auction ends with no winner

### 3.5 Bidding
- **URL:** `/auctions/<uuid:pk>/bid/` (POST)
- Validates: user is authenticated, auction is live, bid amount > current price + min increment, bidder ≠ seller
- Sends real-time WebSocket notification to outbid users

---

## 4. Orders & Payments

### 4.1 Create Order
- **URL:** `/orders/create/<uuid:product_id>/`
- Creates an order for a marketplace product
- Also creates a ChatRoom between buyer and seller
- Order status starts as **"Pending Payment"**

### 4.2 Order Detail
- **URL:** `/orders/<uuid:pk>/`
- Shows: product info, buyer/seller, amount, status, tracking info
- Buyer can see payment button when status is "Pending Payment"
- Seller can add tracking number when status is "Escrow Held"
- Shows tracking events when shipped

### 4.3 Payment (Stripe Checkout)
- **URL:** `/payments/create-payment-intent/<uuid:order_id>/`
- Creates Stripe Checkout Session
- Redirects user to Stripe hosted checkout page
- On success: order status changes to **"Escrow Held"**, product marked as sold
- Webhook endpoint: `/payments/webhook/` handles `checkout.session.completed` and `payment_intent.succeeded`

### 4.4 Order Tracking
- **URL:** `/orders/<uuid:pk>/tracking/`
- Seller submits tracking number and selects carrier (Thai Post, KEX, Flash Express, Ninja Van, DHL, Shopee Express, J&T Express, Best Express)
- Registers tracking with 17TRACK API
- Order status changes to **"Shipped"**

### 4.5 Order Status Flow
```
Pending Payment → Escrow Held → Shipped → Completed
                                       → Disputed
                → Cancelled
```

### 4.6 Confirm Receipt
- **URL:** `/orders/<uuid:pk>/confirm/`
- Buyer confirms they received the product
- Order status changes to **"Completed"**
- Buyer can then leave a review

---

## 5. Chat System

### 5.1 Chat Room List
- **URL:** `/chats/`
- Shows all chat rooms the user participates in
- Displays: other participant's name, last message, unread count
- Ordered by most recently updated

### 5.2 Chat Room Detail
- **URL:** `/chats/<uuid:pk>/`
- Real-time messaging via WebSocket (Django Channels)
- Shows message history
- Messages marked as read when viewed
- Displays which product/auction the chat is about

### 5.3 Start Chat
- **URL:** `/chats/start/<uuid:user_id>/`
- Creates a new chat room with specified user (or opens existing one)
- Can optionally be linked to a product

---

## 6. Reviews

### 6.1 Create Review
- **URL:** `/reviews/create/<uuid:order_id>/`
- Only buyer can review after order is completed
- One review per order (enforced by OneToOne relationship)
- Fields: rating (1-5 stars), comment (optional)
- Review is linked to: order, reviewer, seller, product

### 6.2 View Reviews
- Reviews displayed on seller's profile page
- Shows: reviewer name, rating, comment, date

---

## 7. Notifications

### 7.1 Notification List
- **URL:** `/notifications/`
- Shows all notifications for current user
- Ordered by newest first

### 7.2 Notification Types
- Auction Won, Auction Outbid, Auction Ending
- Order Created, Order Paid, Order Shipped
- New Message
- System notifications

### 7.3 Mark as Read
- **URL:** `/notifications/<uuid:pk>/read/` (POST)
- Mark individual notification as read
- Real-time update via WebSocket

### 7.4 Mark All as Read
- **URL:** `/notifications/mark-all-read/` (POST)
- Mark all notifications as read at once

---

## 8. Live Streaming

### 8.1 Stream List
- **URL:** `/live/`
- Shows all currently live streams
- Powered by **Agora** SDK

### 8.2 Start Live Stream
- **URL:** `/live/prepare/`
- Host enters stream title
- Creates stream with unique Agora channel name
- Redirects to stream detail page

### 8.3 Watch/Host Stream
- **URL:** `/live/<uuid:pk>/`
- Real-time video using Agora Web SDK
- Live chat via WebSocket (Django Channels)
- Host can end stream

### 8.4 End Stream
- **URL:** `/live/<uuid:pk>/end/` (POST)
- Only host can end their stream
- Sets status to "Ended"

### 8.5 My Streams
- **URL:** `/live/my-streams/`
- Lists all streams (live + ended) created by the user

---

## 9. Admin Dashboard

### 9.1 Dashboard
- **URL:** `/dashboard/`
- Requires staff/superuser access
- Shows statistics: total users, products, orders, revenue
- Quick actions for managing the platform

### 9.2 Admin Product Approval
- **URL:** `/users/admin/listings/`
- Admin reviews pending products (marketplace and auction separately)
- Can approve or reject products with reason
- Filter by status: Pending, Approved, Rejected, All
- Filter by type: Marketplace, Auction

### 9.3 Manage Listings
- **URL:** `/users/manage-listings/`
- User's listing management page
- Shows user's own marketplace products and auctions

---

## 10. Homepage

- **URL:** `/`
- Displays product sections:
  - **New Products** — latest 6 approved marketplace products
  - **Featured Products** — highest priced 6 products
  - **Spotlight Products** — recently updated 6 products
- Excludes auction products from homepage display
