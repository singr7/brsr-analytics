from __future__ import annotations

from api.app.services.plans import plan


def invoice_plan_sheet(tier: str, seats: int, term_months: int, billing_email: str) -> str:
    selected = plan(tier)
    features = "\n".join(f"- {feature}" for feature in selected["features"])
    return (
        "A customer requested a BRSR Lens invoice.\n\n"
        f"Plan: {selected['name']}\nSeats: {seats}\nTerm: {term_months} months\n"
        f"Billing contact: {billing_email}\nPublished price: {selected['price_label']}\n\n"
        f"Included workflows:\n{features}\n\n"
        "Confirm commercial terms and licence dates manually before activating access."
    )


class RazorpayAdapter:
    """Deliberately non-charging adapter boundary for a future payment implementation."""

    def create_payment_link(self) -> None:
        raise NotImplementedError("Razorpay is outside billing-lite; use manual invoicing")
