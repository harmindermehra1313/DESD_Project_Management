# Bristol Regional Food Network Digital Marketplace



## 1. Project Overview

This project is a digital marketplace developed for local food producers, customers, business buyers, community groups, and platform administrators. It was built as part of the Distributed and Enterprise Software Development (DESD) group project.

The platform supports the full local food ordering process, including product browsing, customer registration and login, ordering, payments, receipt downloads, order history, reordering, product alternatives, subscriptions, reviews, notifications, and account management features such as password recovery and cookie handling.

For producers, the system provides tools for product management, batch management, inventory control, order management, sales overview, order statistics, surplus reductions, wholesale pricing for business and community customers, weekly payment summaries, future earnings tracking, certifications, allergens, seasonal availability, recipes, and farm stories. These features are designed to support producers with different levels of technical experience and reduce manual communication around orders, stock, and customer updates. 

For administrators, the platform includes financial reporting, product approval management, review moderation, user management, and AI model oversight.

The system also includes recommendation features to help customers discover relevant products, reorder frequently purchased items, and view suitable alternatives when products are unavailable.

Classifier Model Management allows the platform to manage an AI model that checks fruit and vegetable quality from uploaded images. The model can suggest a quality grade, support reduced-price decisions, flag uncertain predictions for manual review, and allow administrators to monitor model accuracy, confidence levels, prediction errors, and model versions. The AI is intended to support producer decisions rather than replace human judgement.

Overall, the platform is designed as a practical local food marketplace rather than a generic e-commerce system. It combines customer ordering, producer operations, administrative control, food-specific product information, transparent payments, sustainability features, and responsible AI support.

## 2. Stakeholder Summary

The platform provides value to three main stakeholder groups: customers, producers, and platform administrators.

### Customers

Customers can use the marketplace to browse local food products, place orders, make payments, download receipts, view order history, reorder previous purchases, leave reviews, manage subscriptions, and receive notifications.

Individual customers can browse products, place standard orders, view receipts, reorder frequently purchased items, and receive alternative product suggestions when selected items are unavailable.

Business and community group customers can access wholesale pricing where eligible, supporting larger or bulk orders from local producers.

Recommendation features help customers discover relevant products, quickly reorder previous purchases, and find suitable alternatives when products are unavailable.

### Producers

Producers can manage products, batches, inventory, orders, payments, reviews, customer feedback, surplus reductions, wholesale prices, recipes, farm stories, certifications, allergens, and seasonal availability.

The producer dashboard supports sales overviews, order statistics, weekly payment summaries, tax-year reporting, future earnings tracking, and downloadable records. These features reduce manual communication and make order, stock, and payment management easier for producers with varying levels of technical experience. 

Classifier Model Management also supports producers by allowing fruit and vegetable quality to be checked from uploaded images. The AI model can suggest a quality grade, support reduced-price decisions, and flag uncertain results for manual review. The AI is designed to support producer judgement rather than replace it.

### Platform Administrators

Platform administrators can manage producer approval requests, moderate reviews, monitor users, view financial reports, download administrative records, and oversee platform activity.

Administrators can also monitor AI classifier performance, including model accuracy, confidence levels, prediction errors, uncertain predictions, and model versions. This helps maintain responsible AI use, platform reliability, and trust between customers, producers, and administrators.

Overall, the platform supports customer ordering, producer operations, administrative control, food-specific product management, transparent payment reporting, sustainability features, and AI-assisted decision support.

## 3. Main System Features

The platform includes the following main features:

### Account Management
- Customer registration and login.
- Producer registration and approval.
- Business and community group account support.
- Forgot password and email verification.
- Cookie handling and account security.

### Product Browsing
- Product catalogue for local food items.
- Product search and filtering.
- Product details, including price, producer, category, allergens, certifications, and seasonal availability.
- Wholesale pricing for eligible business and community group customers.

### Shopping and Orders
- Shopping cart and checkout.
- Card and cash payment support.
- Multi-producer order splitting, allowing one customer order to be separated into producer-specific sections.
- Customer order history.
- Reorder system for previous purchases.
- Alternative product suggestions when items are unavailable.
- Receipt generation and receipt download.

### Producer Management
- Product management.
- Batch management.
- Inventory and stock control.
- Surplus reduction management.
- Producer order status management.
- Sales overview and order statistics.
- Weekly payment summary, including tax-year and future earnings information.
- Downloadable payment and sales records.

### Customer Engagement
- Product reviews.
- Review moderation.
- Customer, producer, and admin notifications.
- Customer subscriptions.
- Producer-created recipes.
- Producer-created farm stories.

### Payments, Cancellations, and Refunds
- Payment tracking.
- Platform commission and producer payout support.
- Order cancellation handling.
- Refund handling for cancelled or unavailable items.
- Financial reporting for administrators.

### AI and Recommendation Features
- AI product recommendations.
- Reorder support based on previous customer activity.
- Alternative product recommendations when selected products are unavailable.
- Classifier Model Management for fruit and vegetable quality checking from uploaded images.
- Quality grade suggestions, reduced-price decision support, uncertain prediction review, and admin monitoring of model accuracy, confidence, errors, and versions.

### Admin Tools
- Admin dashboard.
- Product approval request management.
- Review moderation.
- User management.
- Financial reports with downloadable options.
- AI classifier monitoring and model management.

These features support customers, producers, and administrators by combining marketplace ordering, food-specific stock control, transparent payment management, responsible AI support, and stakeholder-friendly workflows. 

## 4. User Roles and Permissions

The platform uses role-based access control to ensure each user can only access the features and data relevant to their account type. This protects customer, producer, and administrator information by preventing one role from managing another role’s private data or restricted actions. 

### Guest User

Guest users can access public areas of the marketplace, including product browsing, product details, producer information, recipes, farm stories, and general platform pages.

Guest users can also place orders without creating an account. During checkout, they can enter their contact details, delivery or collection information, and payment details. Guest orders can still be processed, cancelled, and refunded where applicable.

However, guest users have limited access compared with registered customers. They cannot leave reviews, manage subscriptions, view saved order history, use the reorder system, or access account-based features. Receipt and order access may also be more limited because there is no registered account linked to the purchase.

### Customer

Customers can create an account, browse products, add items to the cart, place orders, make payments, download receipts, view order history, reorder previous items, leave reviews, manage subscriptions, and receive notifications.

Business and community group customers may also access wholesale pricing where eligible.

Customers cannot manage producer products, producer inventory, producer orders, admin reports, user approvals, review moderation, or AI model management.

### Producer

Producers can manage their own products, batches, inventory, surplus reductions, order sections, payment summaries, sales overview, recipes, farm stories, certifications, allergens, and seasonal availability.

Producers can only view and manage the orders and products assigned to their own producer account. They cannot access another producer’s products, inventory, orders, payments, or customer records.

Producers cannot approve users, moderate platform-wide reviews, manage admin reports, or perform administrator-only actions.

### Admin

Admins can manage producer approval requests, product approval requests, review moderation, current users, financial reports, platform activity, and AI classifier model monitoring.

Admins have wider oversight permissions, but administrative actions are separated from customer and producer workflows to maintain clear responsibility and platform control.

### API Protection

The platform protects API endpoints using authentication and permission checks. Public APIs are limited to safe public data, such as approved product or marketplace information.

Private APIs require the correct logged-in role. For example, customers cannot access producer management APIs, producers cannot access another producer’s data, and non-admin users cannot access admin-only APIs.

This permission structure helps prevent unauthorised create, read, update, and delete operations across different user roles.

## 5. Customer Journey

The customer journey is designed to make local food ordering simple, clear, and accessible for both registered customers and guest users.

### Step 1: Register, Log In, or Browse as a Guest

Customers can either create an account, log in to an existing account, or browse the marketplace as a guest. Registered customers have access to additional features such as order history, receipt access, reordering, subscriptions, notifications, and product reviews.

Guest users can still browse products and place orders, but account-based features are limited.

### Step 2: Browse and Search Products

Customers can view the product catalogue, search for specific items, filter products, and open product detail pages. Product information includes price, producer, category, allergens, certifications, seasonal availability, surplus reductions, wholesale options, and stock availability.

### Step 3: Add Products to the Basket

Customers can add available products to the basket. The basket shows selected items, quantities, prices, producer information, and any relevant product availability details.

### Step 4: Review the Basket and Checkout

Before placing an order, customers can review basket contents, update quantities, remove items, and confirm order details. If the basket contains products from multiple producers, the system separates the order into producer-specific sections while keeping one customer checkout flow.

### Step 5: Choose Delivery or Collection

Customers can choose the available fulfilment option for their order, such as delivery or collection. Delivery and collection options may depend on producer settings, product availability, and order requirements.

### Step 6: Pay by Card or Cash Where Allowed

Customers can pay by card where online payment is supported. Cash payment may be available for eligible collection orders where allowed by the platform.

### Step 7: Track Order Status

Registered customers can track order progress through their account. Order status updates help customers understand whether an order is pending, being prepared, ready for collection, shipped, completed, cancelled, or partially cancelled.

Notifications keep customers informed about important order changes.

### Step 8: View or Download Receipt

Customers can view and download receipts for their orders. Receipts help customers confirm product details, prices, payment information, cancellations, refunds, and order records.

### Step 9: Reorder Previous Items

Registered customers can reorder items from previous purchases. If a previous item is unavailable, out of stock, discontinued, or has insufficient quantity, the system can suggest suitable alternatives.

### Step 10: Leave Product Reviews

After an eligible order, registered customers can leave product reviews. Reviews may be checked by the moderation system before appearing publicly, helping maintain trust and safety across the marketplace.

### Step 11: Receive Recommendations

The recommendation system can suggest relevant products based on customer activity, previous purchases, product similarity, and reorder behaviour. These recommendations help customers discover local products and repeat common purchases more easily.

This journey supports a clear customer experience from browsing to ordering, payment, fulfilment, receipts, reordering, reviews, and recommendations.

## 6. Producer Journey

The producer journey is designed to help local food producers manage products, stock, orders, payments, and customer feedback through a clear dashboard-based workflow.

### Step 1: Register as a Producer

Producers can register for a producer account by submitting the required business or farm details. This creates a producer profile that can later be used to manage products, orders, inventory, payments, recipes, farm stories, and customer-facing information.

### Step 2: Wait for Admin Approval

After registration, the producer account must be reviewed and approved by a platform administrator. This approval step helps ensure that only valid producers can sell products through the marketplace.

### Step 3: Add Products and Inventory

Once approved, producers can add products to the marketplace. Product details  include name, description, category, price, images, certifications, allergens, seasonal availability, and producer-specific information.

Producers can also manage inventory through batches, stock quantities, harvest dates, expiry dates, and product availability. This helps keep the product catalogue accurate and prevents customers from ordering unavailable items.

### Step 4: Manage Surplus and Wholesale Options

Producers can apply surplus reductions where stock needs to be sold at a reduced price, helping reduce food waste.

Wholesale pricing can also be managed for eligible business and community group customers, supporting larger or bulk orders where applicable.

### Step 5: Receive Incoming Orders

When customers place orders, the system separates multi-producer orders into producer-specific sections. Each producer only sees the items assigned to them, making order preparation clearer and reducing confusion.

Notifications can alert producers when new orders, customer updates, reviews, or important system events require attention.

### Step 6: Update Order Section Status

Producers can update the status of their own order sections as work progresses. Status updates help customers understand whether items are being prepared, packaged, ready for collection, shipped, completed, or cancelled.

This keeps customers informed and helps producers manage fulfilment responsibilities clearly.

### Step 7: Cancel Unavailable Items Where Needed

If an item cannot be fulfilled because of stock, batch, quality, or availability issues, producers can cancel the unavailable item or quantity where allowed.

The system can record the cancellation, update the customer-facing order information, and support refund handling where applicable.

### Step 8: View Payments, Payouts, and Summaries

Producers can view payment information, sales overview, order statistics, weekly payment summaries, tax-year information, future earnings, and downloadable payment records.

These tools help producers understand completed sales, expected payouts, and platform commission deductions.

### Step 9: Respond to Customer Reviews

Producers can view customer feedback and respond to reviews where permitted. This supports communication, trust, and service improvement between producers and customers.

Reviews may be moderated to protect the marketplace from inappropriate, harmful, or spam content.

### Step 10: Use AI-Assisted Quality Support

Where available, producers can upload fruit or vegetable images for AI-assisted quality checking. The classifier model can suggest a quality grade, support reduced-price decisions, and flag uncertain predictions for manual review.

The AI feature is intended to support producer judgement rather than replace human decision-making.

Overall, the producer workflow supports product management, stock accuracy, order fulfilment, customer communication, payment transparency, and producer-friendly operation for users with different levels of technical experience. 


## 7. Admin Journey

The admin journey is designed to help platform administrators manage user access, marketplace quality, content safety, financial oversight, and overall platform activity.

### Step 1: Approve or Reject Producer Accounts

Administrators review producer registration requests before producers can sell products on the marketplace. This approval process helps ensure that only suitable and verified producers can access producer tools, upload products, and receive customer orders.

### Step 2: Manage Users and Producers

Administrators can monitor and manage current users, including customers, producers, business accounts, community group accounts, and admin-level access where applicable.

This helps maintain platform security, role separation, and correct access control across the system.

### Step 3: Manage Product Approval Requests

Administrators can review product approval requests before products become publicly available. This supports quality control and helps ensure that product listings are appropriate, complete, and suitable for the local food marketplace.

### Step 4: Moderate Reviews and Producer Responses

Administrators can review customer reviews and producer responses to ensure that public content remains appropriate, respectful, and useful.

The moderation process helps protect the marketplace from harmful, offensive, misleading, or spam content.

### Step 5: Receive Flagged-Content Notifications

When a review or producer response is flagged by the moderation system, administrators can receive notifications and take action.

Flagged content can be reviewed manually, allowing administrators to decide whether the content should be approved, kept flagged, removed, or handled through another moderation action.

### Step 6: View Financial Reports

Administrators can view financial reports covering platform activity, payments, commission, producer payouts, refunds, and sales records.

Downloadable report options help support record keeping, financial transparency, and administrative review.

### Step 7: Monitor Platform Activity

Administrators can monitor wider platform activity, including user activity, orders, reviews, product approvals, notifications, and financial performance.

This oversight helps administrators identify issues, track marketplace performance, and maintain a reliable service for customers and producers.

### Step 8: Monitor AI Model Performance

Administrators can monitor both the Classifier Model Management system and the recommendation model.

For the classifier model, administrators can review model accuracy, confidence levels, prediction errors, uncertain predictions, and model versions. This helps ensure that AI-assisted fruit and vegetable quality checks remain transparent, reviewable, and supportive of producer decision-making rather than replacing human judgement.

For the recommender model, administrators can monitor recommendation activity, model performance, model versions, recommendation quality, and potential issues such as irrelevant suggestions or producer-bias risks. This helps ensure that product recommendations remain useful, fair, and aligned with customer needs.

Overall, the admin workflow supports platform governance, security, moderation, financial transparency, user management, product quality control, recommendation monitoring, classifier monitoring, and responsible AI oversight. These controls help keep the marketplace safe, organised, and trustworthy for all stakeholders. 

## 8. How Orders Work

The order system is designed to support local food orders that may involve more than one producer. A customer can place one order containing products from several producers, while the system separates that order into producer-specific sections behind the scenes.

For example, one customer order may contain vegetables from Producer A, eggs from Producer B, and fruit from Producer C. The customer sees one order, but each producer only manages the items assigned to their own section. This keeps the workflow clear and prevents producers from viewing or changing another producer’s part of the order.

### Multi-Producer Order Splitting

When an order contains items from multiple producers, the system creates separate producer order sections. Each section contains only the products, quantities, delivery or collection details, and fulfilment status relevant to that producer.

This supports:
- Clear producer responsibility.
- Separate preparation and fulfilment tracking.
- Accurate producer payout calculation.
- Partial cancellation and refund handling.
- Better customer visibility when only part of an order is affected.

### Producer Order Management

Each producer updates only their own section of the order. A producer can move their section through fulfilment stages such as:

- Pending
- Preparing
- Packaged
- Ready for collection, for collection orders
- Shipped, for delivery orders
- Completed

If a producer cannot fulfil an item or section because of stock, damage, expiry, or another valid issue, only that producer’s affected items are cancelled. In a multi-producer order, the rest of the order can continue if the other producer sections are still valid.

### Main Order Status

The main customer order status is calculated from the producer section statuses. This means the customer does not need to track several separate technical statuses.

For example:

| Producer section status | Main customer order status |
|---|---|
| All producer sections are pending | Pending |
| At least one producer has started preparing | In progress |
| Some sections are packaged but not all active sections are ready | In progress |
| All active collection sections are packaged | In progress |
| Delivery sections are shipped | In progress |
| All active sections are completed | Completed |
| All sections are cancelled | Cancelled |
| Some sections are cancelled but others continue | Active status remains with a partially cancelled note |

This is important because different producers may prepare or complete their sections at different times. The system keeps the order active if only one producer section is cancelled, and shows a clear partial cancellation message instead of incorrectly marking the whole order as cancelled.

### Payments, Commission, and Producer Payouts

Payment is handled at checkout. After a successful payment, the order becomes pending and producers can begin preparing their sections.

Producer payouts are based on completed producer sections. The platform commission is deducted from each producer’s subtotal, and the remaining amount becomes the producer payout. Cancelled producer sections are not eligible for payout.

### Cancellations and Refunds

The system supports full and partial cancellations.

A full cancellation applies when the whole order cannot continue, such as when all producer sections are cancelled.

A partial cancellation applies when only one producer section or item is cancelled. For example, if Producer B cannot supply eggs but Producer A can still supply vegetables, only Producer B’s items are cancelled and refunded. The rest of the order remains active.

Refund handling depends on the situation:

| Situation | Refund handling |
|---|---|
| Payment failed | No refund needed |
| Order cancelled before successful payment | No refund needed |
| Paid order cancelled before preparation starts | Full refund |
| Producer cancels their own section | Partial refund for affected items |
| All producer sections are cancelled | Full refund |
| Customer cancellation after preparation starts | Not automatic; support or refund review needed |
| Missing, wrong, damaged, unsafe, or materially different item | Refund or support process |
| Completed order | Refund or support process only |

This approach is suitable for fresh and perishable food because producers may already have harvested, packed, prepared, or dispatched items.

### Receipts

Receipts show the important financial and order details for the customer. They can include:

- Ordered items.
- Product quantities.
- Producer information.
- VAT.
- Payment information.
- Cancelled items or quantities.
- Refund amounts.
- Partial cancellation details where applicable.

This helps customers understand exactly what was ordered, what was fulfilled, what was cancelled, and what refund was recorded.

Overall, the order system supports one customer checkout while still giving each producer a clear and separate fulfilment workflow. This makes the marketplace easier to manage, more transparent for customers, and fairer for producers.

## 9. Payment and Commission Logic

The payment and commission logic is designed to make marketplace earnings clear for customers, producers, and administrators.

### Platform Commission

The platform takes a 5% commission from producer sales. This commission supports the operation of the digital marketplace, including ordering, payments, platform management, reporting, and administrative oversight.

### Producer Payout

Each producer receives 95% of their own producer subtotal after the platform commission is deducted.

For example:

| Producer | Producer subtotal | Platform commission | Producer payout |
|---|---:|---:|---:|
| Producer A | £100.00 | £5.00 | £95.00 |
| Producer B | £40.00 | £2.00 | £38.00 |

In a multi-producer order, each producer’s commission and payout are calculated separately. This means one customer order can create separate payout records for different producers.

### Card Payment Flow

Card payments are handled through the Stripe payment flow, or a Stripe/demo payment flow during testing and development.

The general card payment process is:

1. Customer pays at checkout.
2. The platform records the payment result.
3. If payment succeeds, the order becomes pending.
4. Producers can then prepare and fulfil their own sections of the order.
5. Completed producer sections become eligible for payout.
6. Producer payments are included in the weekly settlement or payout process.

This helps prevent producers from preparing orders where payment has not been successfully recorded.

### Cash Payment Flow

Cash payment is mainly suitable for collection orders. This is because payment can be made when the customer collects the order.

Cash payment is less suitable for delivery orders because the platform has less control over whether payment has been completed before fulfilment. For this reason, card payment is the clearer option for delivery-based orders.

### Refund Records

Refund records are created when eligible cancellations or refund events happen. This is important because a single customer order may contain products from more than one producer.

For example, if one producer cannot fulfil their section but the other producers can still complete their sections, only the affected producer’s items are cancelled and refunded. The full customer order does not need to be cancelled.

Refund records can store details such as:

- Refund amount.
- Refund type, such as full or partial refund.
- Refund reason.
- Related producer section.
- Refund status.
- Date created and completed.
- Stripe or demo refund reference where applicable.

### Refund Examples

| Situation | Business result |
|---|---|
| Payment failed | No refund is needed because no successful payment was taken. |
| Customer cancels before successful payment | No refund is needed. |
| Paid order is cancelled before preparation starts | Full refund is recorded. |
| One producer cannot supply their items | Partial refund is recorded for the affected producer section. |
| All producer sections are cancelled | Full refund is recorded. |
| Missing, wrong, damaged, unsafe, or significantly different item | Refund or support process is used. |
| Completed order | Cancellation is not used; refund or support process is used instead. |

### Why This Matters

This payment structure makes the marketplace financially transparent. Customers can see what was paid and refunded, producers can understand their expected payouts, and administrators can review commission, refunds, cancellations, and weekly settlement records.

Overall, the system supports clear payment handling, fair producer payouts, platform commission tracking, and refund records for both full and partial cancellations.

## 10. Inventory and Product Management

The inventory and product management system helps producers keep product availability accurate, reduce waste, and manage different selling options such as surplus and wholesale pricing.

### Product and Batch Management

Producers can add products to the marketplace and manage stock through product batches. A product can have more than one batch, allowing producers to record separate quantities, harvest dates, expiry dates, and availability details.

For example, one apple product may have two active batches:

| Batch | Expiry date | Selling priority |
|---|---|---|
| Batch 1 | 8 April | Used first |
| Batch 2 | 10 April | Used second |

The system prioritises active batches with the earliest expiry date first. This helps older stock sell before newer stock and reduces the risk of waste.

### Batch Availability

Batches can be active or deleted. Active batches are available for ordering, while deleted batches are not used for customer purchases.

If all batches for a product are deleted or unavailable, the product can be shown as no longer available. This prevents customers from ordering products that producers can no longer supply.

### Stock Reduction

Stock levels reduce when customers place orders. This helps keep inventory records up to date and prevents the same stock from being sold multiple times.

When stock is reduced, the system checks the available batch quantity. If the requested quantity is not available, the customer should receive a clear message instead of being allowed to order more than the available stock.

### Low-Stock Alerts

Low-stock alerts notify producers when a product or batch is close to running out. This helps producers decide whether to add more stock, update product availability, or prepare for the product to become unavailable.

These alerts support producers who may not check stock manually every day.

### Expired Batch Handling

Expired batches can be handled automatically by the system. When a batch passes its expiry date, it should no longer be treated as available stock.

This is important for fresh and perishable food because customers should only be able to order products that are safe, current, and available.

### Surplus Discounts

Producers can apply surplus discounts to suitable products or batches. This allows stock that may need to sell quickly to be offered at a reduced price.

Surplus discounts support waste reduction by helping producers sell products before they expire or become unsuitable for sale.

### Wholesale Visibility

Wholesale pricing is restricted to eligible organisation customers, such as business customers and community group customers.

This means ordinary individual customers see the standard product price, while eligible organisation accounts can see wholesale options where the producer has enabled them.

### Product Display Rules

The product catalogue should clearly show product availability and important product states. Examples include:

| Product state | Customer-facing behaviour |
|---|---|
| Active stock available | Product can be viewed and ordered |
| Low stock | Low-stock message or badge can be shown |
| Surplus active | Surplus discount badge can be shown |
| Wholesale active | Wholesale badge can be shown to eligible organisation customers |
| Out of stock | Product card should be disabled or marked unavailable |
| Discontinued or unavailable | Product should not be orderable |

### Why This Matters

This inventory structure helps producers manage fresh food more accurately. Customers receive clearer availability information, producers can reduce waste through expiry-based stock handling and surplus discounts, and organisation customers can access wholesale pricing only when eligible.

Overall, the inventory system supports accurate stock control, producer-friendly product management, waste reduction, and fair visibility rules for different customer types.

## 11. Review and Moderation System

The review and moderation system helps customers share product feedback while protecting the marketplace from harmful, abusive, misleading, or spam content.

### Customer Reviews

Customers can review products after eligible orders. This helps ensure that reviews are based on genuine purchase activity rather than unrelated public comments.

The review option is only available when the order or item has reached an eligible fulfilment stage. Products already reviewed by the same customer can be shown as reviewed, preventing repeated reviews for the same purchase.

### Producer Responses

Producers can respond to customer reviews where permitted. This allows producers to thank customers, clarify issues, respond to feedback, and maintain communication with buyers.

Producer responses are also part of the public marketplace experience, so they may be checked by the moderation system in the same way as customer reviews.

### Moderation Checks

Reviews and producer responses may be checked for harmful or spam content before being published or kept visible.

The moderation approach is based on meaning and risk, not only on banned words. For example, clean product criticism should be allowed, while hostile or abusive comments should be flagged.

| Content type | Example outcome |
|---|---|
| Clean product feedback | Published |
| Harmful or hostile criticism | Flagged for admin review |
| Spam links or promotional codes | Removed |
| Positive review with strong profanity | May be flagged depending on severity |
| Producer response with abusive wording | Flagged for admin review |

This allows fair criticism, such as late delivery or poor freshness, while still protecting users from abusive, harmful, or fraudulent content.

### Spam and Fraud Protection

The system can remove clear spam or fraud attempts automatically. This includes suspicious links, fake discount messages, promotional codes, or content designed to redirect users away from the marketplace.

For example:

| Review text | Expected result |
|---|---|
| “Good product” | Published |
| “Fresh apples, delivery was quick” | Published |
| “Only idiots would buy these apples” | Flagged |
| “Good product visit www.fake-discount.com” | Removed |
| “Best apples, use promo code FREE123” | Removed |

### Admin Moderation Page

Flagged reviews and producer responses appear in the admin moderation page. This gives administrators a central place to review content that may require action.

The moderation page supports platform safety by allowing administrators to check the content, understand why it was flagged, and decide the correct outcome.

### Admin Actions

Administrators can take moderation actions such as:

- Keep the content flagged for further review.
- Approve or publish acceptable content.
- Remove harmful, abusive, spam, or fraudulent content.
- Resolve the flagged notification after action has been completed.

These actions help ensure that the marketplace remains trustworthy, respectful, and useful for customers and producers.

### Why This Matters

Reviews help customers make informed decisions and help producers understand customer feedback. Moderation protects this process by allowing honest criticism while reducing abuse, spam, and misleading content.

Overall, the review and moderation system supports trust, product transparency, producer accountability, and safer communication across the marketplace.

## 12. Notification System

The notification system helps customers, producers, and administrators stay informed about important marketplace activity without needing to manually check every page.

### Customer Notifications

Customers can receive notifications about order and review-related updates. These may include order status changes, cancellation updates, refund updates, receipt availability, review status changes, and producer responses to reviews.

For example, a customer may be notified when an order moves from pending to in progress, when an item has been cancelled and refunded, or when a producer responds to a review.

### Producer Notifications

Producers can receive notifications about order, review, and stock-related activity. These may include new incoming orders, order section updates, customer reviews, review moderation outcomes, low-stock alerts, expired batch handling, and cancellation-related updates.

Stock notifications are especially useful because producers may not check inventory manually every day. Low-stock alerts help producers restock products, update availability, or prepare for an item to become unavailable.

### Admin Notifications

Administrators can receive notifications about moderation, approval, and platform management tasks. These may include flagged reviews, flagged producer responses, producer approval requests, product approval requests, and other admin actions that require review.

This helps administrators focus on items that need attention, such as unsafe content, spam, pending approvals, or unresolved moderation issues.

### Read and Unread Status

Notifications can be marked as read after they have been viewed or handled. This helps users separate new updates from older information.

Users may also be able to mark all notifications as read, which keeps the notification centre organised and easier to manage.

### Direct Links to Related Pages

Some notifications link directly to the relevant order, review, product, approval request, or moderation page.

For example:

| Notification type | Linked page |
|---|---|
| Order status update | Customer order detail page |
| Producer receives new order | Producer order detail page |
| Review received | Product review or producer review page |
| Review flagged | Admin moderation page |
| Product approval request | Admin product approval page |
| Low-stock alert | Producer inventory or product management page |

Direct links reduce confusion because users can open the exact page that needs attention instead of searching manually.

### Notification Resolution

Some notifications are informational, while others require action. For example, an order update may only need to be read, but a flagged review may require an admin decision.

After the required action is completed, the related notification can be resolved or marked as handled. This prevents old moderation or approval notifications from appearing as unresolved after the issue has already been reviewed.

### Why This Matters

The notification system supports clearer communication across the marketplace. Customers receive updates about orders and reviews, producers receive operational alerts about orders and stock, and administrators receive alerts about moderation and approval tasks.

Overall, notifications help keep the platform organised, reduce missed updates, and guide users directly to the pages where action may be needed.

## 13. AI Recommendation System

The AI recommendation system helps customers discover relevant products and reorder suitable items more easily.

### Product Suggestions

The system can suggest products that may be useful or relevant to customers while browsing the marketplace. Recommendations may appear on product pages, reorder pages, or other suitable customer-facing areas.

For example, if a customer views or reorders apples, the system may suggest similar apple products, related produce, or suitable alternatives from available producers.

### How Recommendations Are Chosen

Recommendations are based on two main types of information:

| Recommendation signal | Meaning |
|---|---|
| Product similarity | Products are compared using information such as name, category, description, product type, and other metadata. |
| Marketplace behaviour | Customer activity such as product views, basket activity, and completed purchases can help identify useful patterns. |

This means the system does not rely on only one method. It combines product information with previous marketplace interactions to produce more useful suggestions.

### Hybrid Recommendation Approach

The recommender uses a hybrid approach. This means it combines:

- Content-based recommendation, which compares products using product information.
- Behaviour-based recommendation, which learns from previous customer interactions.
- Product availability rules, which help prevent unavailable products from being recommended.

This approach is useful because a new marketplace may not have much customer activity at first. Product similarity can still provide early recommendations, while behaviour-based recommendations improve as more customers browse, add items to baskets, and place orders.

### Training From Database Activity

The model can be trained from marketplace database activity. Useful activity can include:

- Product views.
- Add-to-basket events.
- Completed orders.
- Previous purchases.
- Reorder behaviour.
- Product and category information.

The recommender system is scheduled to retrain weekly at night. Running the training process overnight helps avoid disruption during normal marketplace use, because model training can take longer than a normal customer request.

As more marketplace activity is collected, the recommender can be retrained using newer data so that suggestions become more relevant over time. This allows the system to improve gradually as customers browse, add products to baskets, place orders, and reorder previous items.

### Reorder and Alternative Suggestions

The recommendation system can also support reordering. If a previously ordered product is unavailable, the system can suggest suitable alternatives.

For example, if a customer previously ordered apples from one producer but that item is no longer available, the system can suggest similar apple products from the same producer where possible, or from another producer where needed.

### Availability and Relevance Rules

Recommendations should only be shown when they are useful, relevant, and available.

Products should not be recommended if they are:

- Out of stock.
- Expired.
- Deleted or unavailable.
- Discontinued.
- Not visible to the customer’s account type.
- Not appropriate for the current product or reorder context.


### Admin Monitoring

Administrators can monitor recommender activity and model performance. This helps check whether recommendations are useful, fair, and not repeatedly favouring only the most popular products or producers.

Monitoring can help identify issues such as irrelevant recommendations, popularity bias, producer over-exposure, or poor recommendation quality.

### Why This Matters

The AI recommendation system improves the customer experience by reducing search effort, supporting repeat purchases, and helping customers find suitable alternatives when products are unavailable.

It also supports producers by increasing product visibility and helping relevant products appear in front of customers at the right time.

Overall, the recommender is designed to support customer choice, improve product discovery, and make the marketplace easier to use without replacing normal browsing or search.


## 14. Automation and Scheduled Tasks

The platform uses scheduled tasks to keep stock, surplus discounts, producer alerts, and AI recommendations up to date automatically. These tasks reduce manual administration and help the marketplace handle time-sensitive food products more reliably.

### Scheduled Job Summary

| Schedule | Task | Purpose |
|---|---|---|
| Every day at 06:00 | Expire old product batches | Checks product batches and marks expired stock as unavailable. |
| Every day at 06:30 | Start surplus reductions | Activates scheduled surplus discounts when the reduction period begins. |
| Every day at 06:45 | End surplus reductions | Deactivates surplus discounts when the reduction period ends. |
| Every day at 07:00 | Send low-stock emails | Sends email alerts to producers when stock levels are low. |
| Every Sunday at 02:00 | Train AI recommender | Retrains the recommendation model using marketplace database activity. |

### Expire Old Product Batches

Expired product batches are checked automatically every morning. If a batch has passed its expiry date, the system can mark it as unavailable so customers cannot order outdated stock.

This supports food safety, stock accuracy, and better product availability management.


### Start Surplus Reductions

Surplus discounts can start automatically at the scheduled time. This allows reduced pricing to be applied without requiring producers or administrators to manually activate the discount.

This is useful for products that need to sell quickly before expiry.


### End Surplus Reductions

Surplus discounts can also end automatically. This prevents reduced prices from staying active longer than intended.



### Send Low-Stock Emails

Low-stock emails are sent to producers when product or batch quantities fall below the defined threshold. This helps producers restock items, update availability, or prepare for a product to become unavailable.



### Train the AI Recommender Weekly

The AI recommender is trained weekly at night. The training task can use database activity such as product views, add-to-basket events, completed orders, previous purchases, and reorder behaviour.

Running this task overnight helps reduce disruption during normal marketplace use, because model training may take longer than a standard customer request.


### Why This Matters

Scheduled automation helps the marketplace stay accurate and reliable without constant manual checks. It supports fresh food management, expiry handling, surplus discount control, stock communication, and regular recommender improvement.

Overall, these tasks help producers manage stock more easily, help customers see more accurate product information, and help administrators maintain a more organised marketplace.

## 15. System Architecture

The platform uses a web-based architecture built around a Django backend, a PostgreSQL database, and a Bootstrap-based frontend.

### Main Architecture Components

| Component | Purpose |
|---|---|
| Django backend | Handles business logic, user roles, orders, payments, inventory, reviews, notifications, and admin workflows. |
| PostgreSQL NeonDB database | Stores platform data such as users, products, batches, orders, payments, reviews, refunds, and notifications. |
| Bootstrap, HTML, CSS, and JavaScript frontend | Provides the user interface for customers, producers, and administrators. |
| Django REST Framework APIs | Supports structured backend API endpoints for frontend features and system integrations. |
| Docker-based local setup | Allows the project to run consistently in a local development environment. |
| Cron service | Runs scheduled tasks such as batch expiry, surplus reduction updates, low-stock emails, and weekly recommender training. |
| Q Cluster | Handles background tasks such as email notifications where asynchronous processing is needed. |
| Stripe integration | Supports card payment and refund flows where configured. |
| Firebase integration | Supports configured Firebase services such as image hosting/storage and authentication. |
| Detoxify | Supports local review and response moderation by detecting toxic or harmful content. |
| Implicit ALS and TF-IDF | Support the hybrid AI recommender system using marketplace behaviour and product information. |

### Backend Layer

The Django backend controls the main platform rules. This includes account permissions, customer checkout, producer order sections, inventory updates, cancellations, refunds, review moderation, notifications, and admin reporting.

Django REST Framework is used where API-based communication is needed between the frontend and backend.

### Database Layer

PostgreSQL NeonDB stores the main marketplace data. This includes customer accounts, producer accounts, product records, inventory batches, orders, producer order summaries, payments, refunds, reviews, and notification records.

### Frontend Layer

The frontend is built with HTML, CSS, Bootstrap, and JavaScript. Bootstrap supports responsive layouts so that customers, producers, and administrators can use the platform across different screen sizes.

JavaScript supports interactive features such as dynamic updates, modals, form handling, notification actions, and API-based page behaviour.

### Background and Scheduled Processing

The system uses scheduled cron jobs for time-based automation. These jobs manage batch expiry, surplus discount start and end times, low-stock email alerts, and weekly recommender retraining.

Q Cluster supports background processing, especially for tasks such as email notifications that should not block normal page requests.

### External Integrations

Stripe is used for card payment and refund processing where configured. Firebase services are used where configured for image hosting/storage and authentication-related functionality.

### AI and Moderation Components

Detoxify is used to support review moderation by detecting toxic or harmful content in customer reviews and producer responses.

The recommendation system uses TF-IDF for product similarity and Implicit ALS for behaviour-based recommendations. Together, these support hybrid product recommendations based on both product information and marketplace activity.

### Simple Architecture Summary

In simple terms, the frontend displays the marketplace, Django manages the business rules, PostgreSQL NeonDB stores the data, scheduled services keep time-sensitive tasks updated, and external integrations support payments, authentication, images, moderation, and AI recommendations.



## 16. Local Setup Guide

This section explains how developers or markers can run the Bristol Regional Food Network Digital Marketplace locally.

### Requirements

The project requires:

- Docker Desktop.
- Git.
- Access to the project repository.
- Internet access for downloading Docker images and Python packages.
- Access to the shared PostgreSQL NeonDB database credentials.
- Required environment variables for Django, database, Stripe, Firebase, email, and storage configuration.

The Python dependencies are listed in `requirements.txt`, including Django, Django REST Framework, PostgreSQL support, Stripe, Firebase Admin, Django Q2, Detoxify, Torch CPU, Implicit, NumPy, SciPy, scikit-learn, and joblib. 

### Environment Variables

The application should be configured through environment variables or a local `.env` file. Secret values should not be written into the report or committed to a public repository.

Typical variables include:

```env
DEBUG=True
SECRET_KEY=replace-with-local-secret-key

DB_NAME=replace-with-database-name
DB_USER=replace-with-database-user
DB_PASSWORD=replace-with-database-password
DB_HOST=replace-with-neondb-host
DB_PORT=5432

STRIPE_SECRET_KEY=replace-with-stripe-secret-key
STRIPE_PUBLIC_KEY=replace-with-stripe-public-key
STRIPE_WEBHOOK_SECRET=replace-with-webhook-secret-if-used

EMAIL_HOST_USER=replace-with-email-address
EMAIL_HOST_PASSWORD=replace-with-email-password-or-app-password

GOOGLE_APPLICATION_CREDENTIALS=path-to-firebase-service-account-json
FIREBASE_AUTH_CONFIG=path-to-firebase-auth-config-json
````

Firebase service account files contain private credentials and should be protected carefully. If a private Firebase key has been committed or shared outside the intended team environment, it should be rotated in Firebase/Google Cloud.

### Database Setup

The project was first tested with a local PostgreSQL database and later configured to use a shared PostgreSQL NeonDB database.

For the marker/developer setup, the shared NeonDB database can be used by adding the correct database credentials to the environment variables. This avoids requiring every marker to create and seed a separate local database.

### Docker Setup

The local setup is Docker-based. The main command is:

```bash
docker compose up --build
```

This command builds the containers and starts the application services. In the current setup, the database wait script checks whether the database is reachable, runs migrations automatically, and then starts the Django development server on `0.0.0.0:8000`. 

After the containers start successfully, the application should be available at:

```text
http://localhost:8000
```

### Docker Setup and Optimisation

The project uses Docker to make the local setup easier for developers and markers. Instead of requiring each person to install Python packages, configure services, and run commands manually, Docker provides a consistent environment for running the application.

The setup is optimised for local development and marking rather than full production deployment. This means the focus is on making the project easy to build, run, test, and review.

#### Why the Docker Setup Is Optimised

The Docker setup helps by:

- Using one main command to build and run the application.
- Keeping the Django application environment consistent across different machines.
- Installing the required backend, database, payment, Firebase, moderation, and recommendation dependencies inside the container.
- Connecting to the shared NeonDB database instead of requiring every developer to create a separate local database.
- Running database migrations automatically during startup.
- Separating the main web application from background and scheduled tasks.
- Supporting scheduled jobs such as batch expiry, surplus reduction updates, low-stock emails, and weekly recommender training.

### Development Benefit

The main benefit is simplicity. The project can be started with:

```bash
docker compose up --build

### Database Migration Commands

Migrations are normally handled automatically when running:

```bash
docker compose up --build
```

The wait script runs:

```bash
python manage.py migrate --noinput
```

before starting the Django server. 

If migrations need to be run manually, use:

```bash
docker compose exec web python manage.py makemigrations
docker compose exec web python manage.py migrate
```

A superuser can be created with:

```bash
docker compose exec web python manage.py createsuperuser
```

The Django command entry point uses the project settings module `BRFN.settings`. 

### Running the Application

The normal local running command is:

```bash
docker compose up --build
```

This should:

1. Build the Docker image.
2. Install Python dependencies.
3. Connect to the configured PostgreSQL NeonDB database.
4. Run database migrations.
5. Start the Django development server.
6. Start configured supporting services such as cron and background workers, where included in the Docker Compose setup.

### Scheduled Services

The local Docker setup also supports scheduled jobs through the cron service. These jobs handle batch expiry, surplus reduction start/end logic, low-stock emails, and weekly recommender training.

The recommender training job is scheduled to run weekly at night so that model retraining does not interrupt normal marketplace usage.

### Notes 

The simplest setup path is:

```bash
git clone <repository-url>
cd <project-folder>
create or add the required environment variables
docker compose up --build
```

No separate manual migration step should be required during the normal Docker setup because migrations are handled by the startup script.

Overall, the local setup is designed so that one Docker command can build the project, connect to the shared NeonDB database, apply migrations, and run the marketplace for testing and marking.

## 17. Security and Access Control

The platform uses security and access control rules to protect customer data, producer data, admin features, payment records, and system configuration files.

### Role-Based Access Control

The system uses role-based access control so that each account type can only access the features relevant to that role.

| Role | Access level |
|---|---|
| Guest user | Can access public marketplace pages only. |
| Customer | Can browse products, place orders, view own order history, view receipts, reorder items, and leave eligible reviews. |
| Producer | Can manage own products, batches, inventory, order sections, reviews, and payment summaries. |
| Admin | Can access restricted admin tools such as user management, producer approval, product approval, review moderation, financial reports, and AI monitoring. |

This prevents users from accessing pages, records, or actions outside their permission level.

### Producer Access Control

Producers can only manage their own marketplace data. This means a producer should only be able to:

- Create and edit their own products.
- Manage their own product batches.
- View and update their own producer order sections.
- Cancel only their own unavailable items or sections where allowed.
- View their own payment summaries and sales records.
- Respond to reviews on their own products.

A producer must not be able to view, edit, delete, or update another producer’s products, inventory, orders, payouts, or customer records.

### Admin Page Restrictions

Admin pages are restricted to authorised admin users only. These pages include:

- Producer approval pages.
- Product approval pages.
- Review moderation pages.
- User management pages.
- Financial report pages.
- AI classifier and recommender monitoring pages.
- Platform activity dashboards.

Non-admin users should be redirected or shown an appropriate error page if they try to access restricted admin areas.

### API Endpoint Protection

API endpoints should use appropriate authentication and permission checks. Public APIs should only expose safe public data, such as approved product information.

Private APIs should require the correct role before allowing access.

Examples:

| API area | Required protection |
|---|---|
| Customer order APIs | Customer must only access their own orders. |
| Producer product APIs | Producer must only manage their own products. |
| Producer order APIs | Producer must only manage their own order sections. |
| Admin APIs | Admin role required. |
| Review moderation APIs | Admin role required. |
| Financial report APIs | Admin role required. |

This helps prevent unauthorised create, read, update, and delete operations.

### Sensitive File Protection

Sensitive files must not be shared publicly or committed to a public repository. These files may contain credentials, private keys, database access details, or trained model data.

Examples of sensitive files include:

- `.env` files.
- Firebase service account keys.
- Firebase authentication configuration where private values are present.
- Stripe secret keys.
- Email credentials.
- Database connection strings.
- Private API keys.
- Trained recommender artefacts.
- Local logs containing secrets or customer data.

These files should be added to `.gitignore` where appropriate.

### Recommended `.gitignore` Entries

```gitignore
.env
*.env

firebase-key.json
firebase_auth.json
*firebase*.json

*.sqlite3
db.sqlite3

media/
staticfiles/

logs/
*.log

ai_recommendations/artifacts/
*.pkl
*.joblib
*.pth
*.pt
*.onnx

```

## 18. Contributors

The project was completed as a group development project. Each team member contributed to planning, development, testing, and system improvement.

| Team member | Main responsibilities |
|---|---|
| Hannah | Project manager, planning, task organisation, testing, and development support. |
| Harminder | Git branch merging, development, testing, and integration support. |
| Joe | Development, testing, debugging, and feature implementation. |
| Adam | Development, testing, debugging, and feature implementation. |
| Oishik | Development, testing, debugging, documentation support, and feature implementation. |

### Contribution Summary

- Project management and planning were supported through Jira task management, task organisation, group coordination, and development planning.
- Development work included customer, producer, admin, order, inventory, payment, review, notification, recommendation, and AI-related features.
- Testing work included manual testing, edge-case testing, workflow checks, bug fixing, and validation of implemented features.
- Git and integration work helped combine individual branches and maintain a working shared project version.
- Documentation work helped explain the system clearly for developers.


Overall, the team contributed across project management, planning, development, testing, Git integration, and documentation to deliver the Bristol Regional Food Network Digital Marketplace.


