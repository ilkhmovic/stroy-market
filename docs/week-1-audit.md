# Week 1 repository audit

**Scope/date:** Static review of the public `main` branch and targeted source files on 2026-10-23. No local checkout or executable repository environment was available through this session; findings below distinguish directly observed code from items that require runtime verification. No claim is made that tests or Django checks were executed here.

## Architecture observed

- Django project: `config/settings.py`, `config/urls.py`, `manage.py`.
- Pinned framework/dependencies: `requirements.txt` pins Django 6.0.4 and django-allauth 65.20.0; Django 6 requires Python 3.12+.
- Apps: `main` (custom `main.User`, marketplace, products, stores, cart, orders, reviews, notifications, AI helper/estimator) and `installments` (wallet-card metadata/ledger and installment partners/plans).
- Database: SQLite `db.sqlite3` by default; optional `DATABASE_URL` parsing supports PostgreSQL/MySQL/SQLite. PostgreSQL driver is not in the pinned requirements, per README.
- Authentication: custom `main.User(AbstractUser)`, Django `ModelBackend` and allauth; mandatory email verification configured. Role flags include `is_seller` and `is_buyer`.
- Static/media: WhiteNoise static storage; uploaded media served by Django only in DEBUG mode, requiring separate production media hosting/configuration.
- Integrations: Gemini and optional Telegram/email; README explicitly says Click/Payme/Uzum and real installment provider integrations are not connected. Wallet cards store metadata/last four digits rather than acting as a live payment processor.
- Tests: `main/tests.py` has an extensive Django `TestCase` suite (823 lines at review); no pytest configuration observed in the root listing.

## Prioritized findings

### Critical
- **No confirmed critical exploit from the limited static review.** A complete security audit cannot be claimed without running tests, reviewing every endpoint and admin action, inspecting deployment configuration and verifying historical secret exposure.

### High
1. **Order cancellation was callable through GET.** `main/views.py: cancel_order, cancel_order_item`; URLs are `order/<order_id>/cancel/` and `order/item/<item_id>/cancel/` in `main/urls.py`. Both handlers restore stock/change order state and can apply penalties. Changed to require POST; related regression-test calls were changed to POST. Verify template forms use POST and include CSRF tokens. This does not by itself prove all sensitive endpoints use safe methods.
2. **Order/inventory concurrency and cancellation require deeper transaction review.** Checkout in `main/views.py: checkout` uses `transaction.atomic()`, `select_for_update()`, and conditional stock decrement. Cancellation functions call `restore_item_stock_once`, but the full helper implementation and backend-specific behavior need runtime/concurrency tests. SQLite does not provide PostgreSQL-equivalent row locking; test on the intended production database.
3. **Historical secret exposure is explicitly mentioned in README.** `README.md` warns that previously committed SSH keys may remain in old commits even after removal from the current tree. A full Git-history secret scan was not executable in this session. Treat any historical credential as compromised, rotate it, and run a history scan before launch. Do not publish secret values in reports.
4. **Production security depends on environment and proxy correctness.** `config/settings.py` requires `SECRET_KEY` when `DEBUG=False`, enables secure cookies and HTTPS redirect in non-debug mode, and derives host/origin values from environment variables. However, an empty `ALLOWED_HOSTS` remains possible when no hosts are configured, and `SECURE_PROXY_SSL_HEADER` trusts `X-Forwarded-Proto`; only use it behind a proxy that overwrites this header. Verify all production hosts and CSRF origins before deployment.

### Medium
1. **Product price/stock model validation is not fully enforced at the model/database layer.** `main/models.py: Product.price, Product.stock; CartItem.quantity; OrderItem.quantity`. Price uses DecimalField (good), but stock and quantity are integer fields without visible database check constraints in the reviewed definitions. Form/view validation exists in some cart/checkout paths; add database constraints and validation tests after auditing existing data and migrations.
2. **Order item purchase snapshots exist.** `OrderItem.product_name` and `OrderItem.price` preserve the product name and price at order time. No explicit discount snapshot was observed in the inspected model. Do not add discount fields until current discount/business rules are confirmed.
3. **Wallet ledger transaction uses row locks and atomic transaction.** `installments/services.py: top_up, pay_order`. Payment is internal wallet accounting, not live card processing. Verify state transitions, refunds/cancellations after wallet payment, and ledger consistency; do not describe this as merchant payment integration.
4. **Upload handling needs an end-to-end review.** `main/models.py: PathAndRename, User.avatar, Store.logo, Product.image`; README says estimator uploads are checked by byte-level file type. Confirm size limits, actual content decoding, image re-encoding, storage isolation, and serving headers.
5. **Seller data boundaries need endpoint-by-endpoint tests.** `installments/views.py: seller_export, _seller_applications` scopes export rows through products belonging to the seller's store, and `card_history` scopes cards to the requesting user. Review every seller order/product/review/export endpoint and admin custom views, including suspended/pending stores.
6. **Dependency supply-chain status is unknown.** Pinned requirements are present, but no vulnerability audit was executed in this environment. CI will run `pip-audit` so advisories are visible rather than silently ignored.

### Low / maintainability
1. `main/models.py: Product.avg_rating` checks a related manager with `if not reviews` and then uses `len(reviews)`; this may not behave as intended for a QuerySet and can issue extra queries. Prefer aggregate/count when safely refactoring.
2. Settings and tests contain environment-specific behavior (for example cache backend selection when `test` is in `sys.argv`). Verify it under both `manage.py test` and deployment settings.
3. README documents setup and env variables in Uzbek and clarifies payment limitations; add explicit CI/test instructions and database-driver guidance as deployment support evolves.

## Existing workflows inspected

- Public product browsing and product detail routes in `main/urls.py`.
- Cart add/update/remove handlers in `main/views.py`; mutating cart handlers use `require_POST`.
- Checkout validates payment method/address and nasiya form, locks products, checks stock, creates order-item snapshots, decrements inventory, and clears the cart inside an atomic block.
- Buyer order detail is filtered by `user=request.user`.
- Order cancellation is now POST-only and is buyer-scoped by `order__user=request.user`.
- Wallet payment service scopes order and card to the requesting user and uses atomic row locks.
- Installment seller export is store-scoped by product ownership in the reviewed query.
- Notifications, AI/Gemini, Telegram, email and upload workflows need runtime tests/mocks and full endpoint review.

## Git history and secrets

The repository is public and README notes historical SSH-key exposure. Current `.gitignore` excludes `.env`, private-key patterns, media, database files and cache directories. This review did **not** retrieve or print secret values and did **not** complete a history-wide scan. Run the commands below in a trusted local checkout; treat matches as sensitive and never paste values into tickets or logs:

```bash
git log --all --name-only --pretty=format: | sort -u
git log --all -S'BEGIN OPENSSH PRIVATE KEY' --oneline -- .
git log --all -S'AIza' --oneline -- .
# Use a trusted secret scanner (e.g. gitleaks) against all refs; inspect findings locally.
```

Rotate exposed credentials first. History rewriting is a separate coordinated operation and must not be performed casually on a shared repository.

## Verification commands

Run locally or in CI after installing dependencies:

```bash
python --version
python -m pip install -r requirements.txt
python manage.py check
python manage.py check --deploy
python manage.py makemigrations --check --dry-run
python manage.py migrate --check
python manage.py test
python -m pip install pip-audit
python -m pip_audit -r requirements.txt
```

This session had no local repository filesystem or Django runtime, so none of these commands were executed here. CI configuration is added separately to execute checks on GitHub Actions.

## Assumptions and limitations

- No live payment processing should be added during Week 1; README confirms current payment-provider onboarding is incomplete.
- Existing cancellation policy permits cancellation of pending items, with cash-order penalties; policy was preserved.
- Avoid schema changes until test-server data and the intended production DB are backed up and inspected.
- A passing CI run is necessary but not sufficient for a public-launch security sign-off.
- Before public launch: rotate any historically exposed credentials, verify HTTPS/proxy/host/CSRF config, inspect media hosting, test seller/buyer object authorization, and run concurrency/inventory tests against PostgreSQL if that is the intended production database.

## Week 2 backlog (priority order)

1. Add atomic service-layer order creation/cancellation and explicit valid status-transition rules; preserve current business policy.
2. Add database constraints for nonnegative stock and positive quantities after validating existing rows; prepare reversible migrations.
3. Add concurrency tests for two checkouts competing for final stock, repeat cancellation, and wallet debit/ledger idempotency on PostgreSQL.
4. Verify wallet-paid order cancellation/refund semantics before allowing cancellation or stock restoration.
5. Expand buyer/seller/admin authorization tests across every order/product/export/status endpoint.
6. Complete upload limits/content validation, production media hosting, and historical-secret remediation.
7. Set up PostgreSQL CI/service job and documented backup/restore/migration rehearsal.
