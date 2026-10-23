# Stage 3 — Quoted delivery (not a payment acceptance)

The FÌLÀ checkout is a WhatsApp enquiry flow. A signed-in customer's
order request starts in the `draft` state and carries their city/state.
No payment gateway is enabled and no quote is an accepted order.

## New staff-only API

`PUT /api/v1/admin/orders/{order_id}/delivery-quote`

Requires the real admin's Bearer token; ordinary customers get 403.
Body: `{"shipping_amount_ngn":2500}` — a **quote entered by staff**, never
calculated from unverified assumptions.

The endpoint only quotes an active draft with a destination. Successful
updates persist the price in kobo and audit every *changed* quote with
admin ID, prior amount and timestamp. Repeating an unchanged amount is
idempotent. Cancelled, expired and destinationless selections cannot be quoted.

Authenticated customers see `shipping_quote_ngn`,
`estimated_total_ngn`, and `shipping_quoted_at` in their own
`GET /api/v1/orders` response; unauthorized users cannot see other
customers' quotes. The website's account history shows a **Confirm quote
on WhatsApp** link. The quote remains unpaid and is never final until
the seller and customer agree.

The existing order subtotal (`total_ngn`) is unchanged. Inventory is
not changed, no shipping fee is assumed, and no payment is collected.

## Online payment gateway still requires

1. Verified business Paystack or Flutterwave merchant account.
2. Seller-approved delivery fees, policy for remote areas, and final price.
3. Payment attempt storage and unique references.
4. Initialization from the backend using the merchant secret.
5. Paystack/Flutterwave signed webhook verification and server-to-server
   amount, currency, reference, and payment status checks.
6. Atomic inventory and order-state transitions, handling late/duplicate
   webhook delivery, refunds, expiring holds and exceptional cases.
7. Test-mode end-to-end verification before the operator enables live payments.
8. Working Vercel production deployment for the frontend.

**Never enter payment secret keys in chat or commit them to GitHub.**
Set them only in Render secret environment variables once the gated
payment integration exists and has passed security review.

See:
- https://paystack.com/docs/payments/accept-payments/
- https://paystack.com/docs/payments/webhooks/
- https://paystack.com/docs/payments/verify-payments/

The project currently has Vercel team-auth restrictions on manual
deployments. The repository commit alone does **not** prove the
production frontend received this update.
