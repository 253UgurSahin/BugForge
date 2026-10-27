# Payments with Stripe, including iDEAL

Read this before you write payment code in forge-build. Checked on 2026-10-27 against Stripe's docs, the Laravel
Cashier docs and the three official SDKs (sources at the bottom). When a call fails or this page disagrees with
the docs for the API version your SDK pins, the docs win. The general rules (test mode only, keys in `.env`, no
card data, the price from your own database) are in SKILL.md and `../forge/rules.md`.

## 1. First: whose money is it?

- **The user's own business** (their shop, their salon, their SaaS subscriptions): this page.
- **Other businesses, through the app** (salons taking deposits from their own clients): Stripe Connect, with a
  connected account per business, which this page does not cover. Collecting their money in the user's account
  and paying it on can also need a payment licence (not legal advice). Settle it with the user in plan.md ("Money
  goes to") before any payment code. Salons paying a subscription and their clients paying deposits: both, the
  subscriptions on this page, the deposits through Connect.

## 2. Setup in the Stripe Dashboard (test mode)

1. The user makes a Stripe account and a sandbox (you never sign up or type a password, a card or a live key).
   The test keys go in `.env` under the profile's `.env.example` names (laravel: Cashier's, with or without it):

   | Profile | Secret key | Publishable key | Webhook signing secret |
   |---|---|---|---|
   | laravel | `STRIPE_SECRET` | `STRIPE_KEY` | `STRIPE_WEBHOOK_SECRET` |
   | django | `STRIPE_SECRET_KEY` | `STRIPE_PUBLISHABLE_KEY` | `STRIPE_WEBHOOK_SECRET` |
   | next | `STRIPE_SECRET_KEY` | not needed for Checkout | `STRIPE_WEBHOOK_SECRET` |

2. Payment methods: Cards and iDEAL on; for subscriptions paid with iDEAL also "iDEAL recurring payments".
   The customer portal on, with what customers may do. Products and prices in EUR (or made with the API).

## 3. iDEAL and payment methods

- iDEAL is the Dutch bank redirect: the customer picks it on the Checkout page, approves in their banking app and
  comes back. One payment, one approval, **EUR only**: every line item in a session that offers it is in `eur`.
  Its result is known right away, but Checkout can also offer methods that settle days later (SEPA Direct Debit,
  bank transfers), so fulfilment handles both (section 4).
- **iDEAL becomes Wero.** It shows as "iDEAL | Wero" (co-branding was required from 29 January to 31 March 2026;
  hosted Checkout did it). Stripe plans Wero for Dutch businesses from Q4 2026 and expects iDEAL to stop in
  2027-2028. Wero is for Checkout's payment mode only; subscriptions that started with iDEAL renew by SEPA Direct
  Debit and are not affected. Tell the user to read Stripe's iDEAL to Wero migration page before going live.
- **No list of payment methods in code.** Turn them on in the Dashboard; Checkout shows the ones that fit
  ("dynamic payment methods"). To leave one out of a session, pass `excluded_payment_method_types`. The API
  version current SDKs pin (`2026-09-30.endive`) no longer accepts `payment_method_types` on a Checkout Session.

## 4. One-off payments: an order or a booking deposit

1. The payer posts what they buy (a product and a quantity, or a slot), logged in or as a guest on a public page.
   CSRF protection on, input validated.
2. The server reads the price from its own database and creates the row (`orders` or `bookings`): `amount_cents`,
   `currency` `eur`, `status` `pending`, the owner or the guest's name and email, and a `token` of 32 or more
   random characters with a unique index. A pending booking holds its slot.
3. It creates a Checkout Session with an idempotency key such as `checkout-booking-<id>`:
   - `mode` `payment`, `line_items` in `eur` with the database price, `client_reference_id` the row's ID,
     `customer_email` the guest's email
   - `success_url` the status page by token (`/pay/<token>`), built from the app's own address (laravel
     `APP_URL`, next `BETTER_AUTH_URL`, django `request.build_absolute_uri()`), and `cancel_url` the same way
   - holding a slot or stock: `expires_at` 30 minutes from now (Stripe allows 30 minutes to 24 hours; the
     default of 24 hours holds the slot for a day), and `excluded_payment_method_types` with methods that settle
     days later such as `sepa_debit`: a completed session cannot expire, so the slot would wait for the bank
4. Redirect to the session's `url` with HTTP 303. The status page needs no login: it finds the row by its token
   and shows only its status ("paid", "waiting for your bank", "expired: book again") and what was bought. A link
   a guest gets never carries a sequential ID; logged-in pages stay owner-checked.

The calls: laravel `$stripe->checkout->sessions->create($params, ['idempotency_key' => $key])`, django
`client.v1.checkout.sessions.create(params=params, options={"idempotency_key": key})`, next
`stripe().checkout.sessions.create(params, { idempotencyKey: key })`.

| Event | What to do |
|---|---|
| `checkout.session.completed`, `checkout.session.async_payment_succeeded` | `fulfil` |
| `checkout.session.async_payment_failed` | `pending` to `failed`, free the slot, queue an email to try again |
| `checkout.session.expired` | `pending` to `expired`, free the slot or stock (required when a row holds one) |
| `refund.updated`, `refund.failed` | section 6 |

**fulfil(session_id)** retrieves the session from the API (the event's copy can be stale). `payment_status`
`unpaid`: the money is on its way, so do nothing and wait for the async event. Otherwise one conditional update:
`UPDATE bookings SET status = 'paid', payment_intent = ? WHERE id = ? AND status = 'pending' AND amount_cents = ?`.
A row changed: queue the confirmation email. No row changed: read the row.

- `paid` already: the same event again. Done.
- `expired` or `failed`: money for something the app had let go. Log it with the session ID, then claim the slot
  again with a conditional update from that status; the no-overlap rule refuses when someone else has it.
  Refused: refund in full (section 6), set the row to `refunded` and email the payer.
- The amount differs (promo codes or Stripe Tax turned on later): log it and tell the user; never mark it paid.

Free a slot **only on Stripe's word**: the expired or failed event, or after you ended the open session yourself
with the expire call (`checkout.sessions.expire`), for example when the payer clicks cancel. Freed earlier, the
payer can still pay for a slot someone else then books. The no-overlap rule in `../forge-plan/profiles.md` must
count only rows that hold a slot (`pending`, `paid`): on PostgreSQL its `where` is `status in ('pending', 'paid')`;
on MariaDB `active` is NULL for every other status.

## 5. Webhooks and idempotency

- One endpoint, `POST /stripe/webhook`, without login or CSRF token (Stripe cannot send one; the signature check
  replaces it). Exempt exactly that path from CSRF.
- **Verify the signature first**, on the raw request body, with the SDK's helper (`constructEvent` /
  `construct_event`); a framework that parses the JSON first breaks it. Bad signature or payload: 400 and nothing
  else. Keep the default tolerance of 5 minutes; 0 turns the timestamp check off.
- **Duplicates and order.** Stripe can send an event more than once, in any order, and retries for up to 3 days in
  live mode. Change state with one conditional update and do side effects (email, refund) only when a row
  changed. Where that is not possible, store `event.id` with a unique index and skip events already seen.
- **Answer fast** with a 2xx; emails and PDFs go to a queued job. Unknown event types: 200, ignore them. Outgoing
  calls carry an idempotency key (`checkout-booking-<id>`, `refund-booking-<id>`), which Stripe keeps for at least
  24 hours; the same key with other parameters is an error.
- **Laravel with Cashier**: Cashier registers `POST /stripe/webhook` itself and checks the signature only when
  `STRIPE_WEBHOOK_SECRET` is set. Do not add your own route there, or one handler silently replaces the other:
  handle `checkout.session.*` and `refund.*` in a listener for `Laravel\Cashier\Events\WebhookReceived` (the event
  is in `$event->payload`) and exempt `stripe/*` from CSRF. Cashier 16 brings stripe-php 21 or older: do not
  require stripe-php yourself.

## 6. Refunds, cancellations and no-shows

The policy comes from plan.md ("Cancelling and refunds", "No-shows"): deadline, full or partial, who may start
it. Show it before the payer pays and in the confirmation email.

1. The payer (through their token link, within the deadline) or the business cancels, checked on the server. The
   server computes the refund from the policy and the stored `amount_cents`, never from the browser.
2. One conditional update first: `paid` to `cancelled` with `refund_cents`, which frees the slot. Only when it
   changed a row, create the refund with the stored `payment_intent`, the `amount` in cents (none for a full
   refund) and the key `refund-booking-<id>`, and store its ID and status. A double click refunds once. The call
   fails: the booking stays cancelled, the refund is marked failed, and the business gets a retry with the same key.
3. iDEAL and other bank payments go back to the bank account, which takes days, and can still fail later. iDEAL
   payments can be refunded up to 180 days after the payment. `refund.updated` and `refund.failed` arrive for
   every refund (API version 2024-10-28 and later): store the status, and tell the business when one fails.
4. A no-show keeps what the policy says (often the deposit): nothing to call at Stripe.

The calls: laravel `$stripe->refunds->create(['payment_intent' => $pi, 'amount' => $cents], ['idempotency_key' =>
$key])`; django `client.v1.refunds.create(params={...}, options={"idempotency_key": key})`; next
`stripe().refunds.create({ payment_intent: pi, amount: cents }, { idempotencyKey: key })`.

## 7. Subscriptions, also with iDEAL

- Checkout with `mode` `subscription`, a recurring price in `eur` and `customer` set to the user's Stripe customer
  ID (created once, stored as `stripe_customer_id`).
- With iDEAL the first payment goes through iDEAL; Stripe saves the IBAN as a SEPA Direct Debit payment method
  with a mandate and charges renewals that way ("iDEAL recurring payments" in section 2). A free trial with
  iDEAL charges 0.01 EUR to collect the bank details and refunds it at once.
- SEPA Direct Debit settles in days: give access on `invoice.paid`, not on the subscription status alone (it can
  be `active` while the first payment is still processing).
- Keep the subscription in your database (`stripe_subscription_id`, `status`, `cancel_at_period_end`, the period
  end), changed only by webhooks: `invoice.paid`, `invoice.payment_failed` (tell the user; Stripe retries by the
  Dashboard settings), `customer.subscription.updated`, `customer.subscription.deleted` (end access). Since API
  version 2025-03-31 the period end sits on the item (`items.data[0].current_period_end`).
- **Customer Portal**, so cancelling is as easy as subscribing: a portal session per click, then a redirect to its
  short-lived `url` (laravel `$stripe->billingPortal->sessions->create([...])` or Cashier's
  `$user->redirectToBillingPortal(route('account'))`, django `client.v1.billing_portal.sessions.create(...)`, next
  `stripe().billingPortal.sessions.create(...)`). It cancels at the period end by default:
  `customer.subscription.updated` comes now, `customer.subscription.deleted` at the end.
- Laravel: Cashier (`laravel/cashier`) does subscriptions, the portal and these webhooks (section 5 first).

## 8. Testing in test mode

- Card `4242 4242 4242 4242`, any future date, any CVC. iDEAL: pick "iDEAL | Wero"; Stripe's test page has
  **Authorize** and **Fail**. Try both. SEPA renewals after an iDEAL start: Stripe's iDEAL subscription guide
  lists test values that make the debits succeed or fail. Expiry without waiting: the expire call.
- Webhooks on your machine: the user runs the Stripe CLI (`stripe login`, then `stripe listen --forward-to
  localhost:8080/stripe/webhook`); the `whsec_` secret it prints goes in `.env` as `STRIPE_WEBHOOK_SECRET`.
- Automated tests, no network: sign a fake event the way the SDK does (stripe-node
  `webhooks.generateTestHeaderString`; PHP and Python `t=<time>,v1=<HMAC-SHA256 of "<time>.<body>">`) and mock the
  API calls. Cover: a bad signature gives 400; `completed` fulfils when `paid`, not when `unpaid`;
  `async_payment_succeeded` fulfils; the same event twice sends one email; `expired` frees the slot; a late payment
  for a taken slot is refunded; cancelling twice refunds once; a token link shows only its own booking.

## 9. Code sketches: the webhook side of a booking deposit

Short sketches, not complete apps; names follow plan.md, the checkout side is section 4. `latePayment` and
`late_payment` are the `expired` or `failed` branch of section 4. The static profile has no server, so no secret
key and no webhook: it uses Payment Links made in the Dashboard (test mode) and fulfils by hand.

### Laravel (stripe/stripe-php, MariaDB)

```php
// routes/web.php: no login; the signature check guards it. bootstrap/app.php, in withMiddleware():
// $middleware->preventRequestForgery(except: ['stripe/webhook']);  (Laravel 11 and 12: validateCsrfTokens)
Route::post('/stripe/webhook', [StripeWebhookController::class, 'handle']);
// config/services.php: 'stripe' => ['secret' => env('STRIPE_SECRET'), 'webhook_secret' => env('STRIPE_WEBHOOK_SECRET')]

public function handle(Request $request)
{
    try {
        $event = Webhook::constructEvent($request->getContent(),              // the raw body
            (string) $request->header('Stripe-Signature'), config('services.stripe.webhook_secret'));
    } catch (\UnexpectedValueException|SignatureVerificationException $e) {
        return response('Invalid payload or signature', 400);
    }
    $session = $event->data->object;
    $id = (int) $session->client_reference_id;
    match ($event->type) {
        'checkout.session.completed', 'checkout.session.async_payment_succeeded' => $this->fulfil($session->id),
        'checkout.session.async_payment_failed' => $this->release($id, 'failed'),
        'checkout.session.expired' => $this->release($id, 'expired'),
        default => null,                                                     // not ours: 200, ignore
    };
    return response('OK', 200);
}

private function release(int $id, string $status): void
{
    $changed = Booking::whereKey($id)->where('status', 'pending')
        ->update(['status' => $status, 'active' => null]);                  // NULL frees the slot
    if ($changed === 1 && $status === 'failed') {
        SendPaymentFailed::dispatch($id);                                    // queued: "please try again"
    }
}

private function fulfil(string $sessionId): void
{
    $stripe = new StripeClient(config('services.stripe.secret'));
    $session = $stripe->checkout->sessions->retrieve($sessionId);           // fresh, not the event's copy
    if ($session->payment_status === 'unpaid') {
        return;                                                              // wait for async_payment_succeeded
    }
    $id = (int) $session->client_reference_id;
    $changed = Booking::whereKey($id)->where('status', 'pending')->where('amount_cents', $session->amount_total)
        ->update(['status' => 'paid', 'active' => 1, 'payment_intent' => $session->payment_intent]);
    if ($changed === 1) {
        SendBookingConfirmation::dispatch($id);                              // queued, sent once
    } elseif (Booking::whereKey($id)->value('status') !== 'paid') {
        $this->latePayment($id, $session);                                  // section 4
    }
}
```

Imports: `Stripe\StripeClient`, `Stripe\Webhook`, `Stripe\Exception\SignatureVerificationException`. A slot
someone else took makes the claim in `latePayment` throw `Illuminate\Database\UniqueConstraintViolationException`.
With Cashier this `match` goes in the `WebhookReceived` listener, reading `$event->payload` (section 5).

### Django (stripe-python, PostgreSQL)

```python
# bookings/views.py. settings.py reads STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET from the environment.
client = stripe.StripeClient(settings.STRIPE_SECRET_KEY)


@csrf_exempt  # Stripe cannot send a CSRF token; the signature check below replaces it
@require_POST
def stripe_webhook(request):
    try:
        event = client.construct_event(request.body, request.headers.get("Stripe-Signature", ""),
                                       settings.STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.SignatureVerificationError):
        return HttpResponseBadRequest("Invalid payload or signature")
    session = event.data.object
    if event.type in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
        fulfil(session.id)
    elif event.type in ("checkout.session.async_payment_failed", "checkout.session.expired"):
        status = "failed" if event.type.endswith("failed") else "expired"  # the exclusion rule frees the slot
        changed = Booking.objects.filter(pk=session.client_reference_id, status="pending").update(status=status)
        if changed and status == "failed":
            send_payment_failed.enqueue(int(session.client_reference_id))  # a django.tasks task
    return HttpResponse("OK")


def fulfil(session_id):
    session = client.v1.checkout.sessions.retrieve(session_id)  # fresh, not the event's copy
    if session.payment_status == "unpaid":
        return  # wait for async_payment_succeeded
    booking_id = int(session.client_reference_id)
    changed = (Booking.objects.filter(pk=booking_id, status="pending", amount_cents=session.amount_total)
               .update(status="paid", payment_intent=session.payment_intent))
    if changed:
        send_booking_confirmation.enqueue(booking_id)  # queued, sent once
    elif not Booking.objects.filter(pk=booking_id, status="paid").exists():
        late_payment(booking_id, session)  # section 4; a taken slot raises django.db.IntegrityError
```

### Next.js (stripe-node, App Router, PostgreSQL)

```ts
// app/stripe/webhook/route.ts. lib/stripe.ts (server-only) makes the client lazily, so `next build` needs no key.
export async function POST(req: Request) {
  let event: Stripe.Event;
  try {
    event = stripe().webhooks.constructEvent(await req.text(),         // the raw body
      req.headers.get("stripe-signature") ?? "", process.env.STRIPE_WEBHOOK_SECRET as string);
  } catch {
    return new Response("Invalid payload or signature", { status: 400 });
  }
  switch (event.type) {
    case "checkout.session.completed":
    case "checkout.session.async_payment_succeeded":
      await fulfil(event.data.object.id);
      break;
    case "checkout.session.async_payment_failed":
    case "checkout.session.expired": {
      const status = event.type.endsWith("failed") ? "failed" : "expired";
      const id = Number(event.data.object.client_reference_id);
      const changed = await db.update(bookings).set({ status })
        .where(and(eq(bookings.id, id), eq(bookings.status, "pending"))).returning({ id: bookings.id });
      if (changed.length === 1 && status === "failed") await queueEmail("payment-failed", id);  // pg-boss
      break;
    }
  }
  return new Response("OK");
}

async function fulfil(sessionId: string) {
  const session = await stripe().checkout.sessions.retrieve(sessionId);  // fresh, not the event's copy
  if (session.payment_status === "unpaid") return;                      // wait for async_payment_succeeded
  const id = Number(session.client_reference_id);
  const changed = await db.update(bookings).set({ status: "paid", paymentIntent: session.payment_intent as string })
    .where(and(eq(bookings.id, id), eq(bookings.status, "pending"), eq(bookings.amountCents, session.amount_total ?? -1)))
    .returning({ id: bookings.id });
  if (changed.length === 1) await queueEmail("booking-confirmed", id);  // sent once
  else await latePayment(id, session);   // section 4: a repeat, a late payment (23P01 = slot taken) or a wrong amount
}
```

## Sources (read 2026-10-27)

The last check reached docs.stripe.com only through web search, plus the SDK changelogs and Laravel's own docs.

- iDEAL, Wero: https://docs.stripe.com/payments/ideal, https://support.stripe.com/questions/ideal-to-wero-migration
- Payment methods: https://docs.stripe.com/payments/payment-methods/dynamic-payment-methods,
  https://docs.stripe.com/changelog/endive, the CHANGELOG.md of stripe-php, stripe-python and stripe-node
- Fulfilment, expiry: https://docs.stripe.com/checkout/fulfillment, https://docs.stripe.com/payments/checkout/managing-limited-inventory
- Webhooks, idempotency: https://docs.stripe.com/webhooks/signature, https://docs.stripe.com/api/idempotent_requests
- Refunds: https://docs.stripe.com/refunds, https://docs.stripe.com/changelog/acacia/2024-10-28/refund-webhook-update
- Subscriptions: https://docs.stripe.com/billing/subscriptions/ideal,
  https://docs.stripe.com/changelog/basil/2025-03-31/deprecate-subscription-current-period-start-and-end
- Portal, testing, Connect: https://docs.stripe.com/customer-management/integrate-customer-portal,
  https://docs.stripe.com/testing, https://docs.stripe.com/connect
- Laravel Cashier and CSRF: https://laravel.com/docs/13.x/billing, https://laravel.com/docs/13.x/csrf,
  https://github.com/laravel/cashier-stripe/blob/16.x/composer.json
