"""Simulated payment gateway (TEST MODE – no real money moves).

Rules mimic what real gateways such as Razorpay / Stripe do in test mode:
  UPI          any valid id like  name@okhdfcbank        (fail@upi  -> declined)
  Card         must pass the Luhn check, expiry in the future, valid CVV
               4111 1111 1111 1111 -> success      4000 0000 0000 0002 -> declined
               4000 0000 0000 9995 -> insufficient funds
  Net banking  choose a bank (State Bank of India fails in test mode)
Full card numbers / CVV are never stored – only brand + last 4 digits.
"""
import re
import secrets
from datetime import datetime

BANKS = ["HDFC Bank", "ICICI Bank", "Axis Bank", "Kotak Mahindra Bank", "Punjab National Bank", "State Bank of India"]
DECLINES = {
    "4000000000000002": "Your card was declined by the bank.",
    "4000000000009995": "Insufficient funds in the account.",
}
UPI_RE = re.compile(r"^[a-z0-9][a-z0-9.\-_]{1,}@[a-z][a-z0-9]{1,}$")


def luhn_ok(number):
    total, flip = 0, False
    for ch in reversed(number):
        n = int(ch)
        if flip:
            n = n * 2 - 9 if n * 2 > 9 else n * 2
        total += n
        flip = not flip
    return total % 10 == 0


def card_brand(n):
    if n.startswith("4"):
        return "Visa"
    if re.match(r"^(5[1-5]|2[2-7])", n):
        return "Mastercard"
    if n[:2] in ("34", "37"):
        return "Amex"
    if re.match(r"^(60|65|81|82|508)", n):
        return "RuPay"
    return "Card"


def _txn():
    return "TXN" + secrets.token_hex(6).upper()


def _result(ok=True, status=200, ref=None, detail="", error=None):
    return {"ok": ok, "status": status, "ref": ref, "detail": detail, "error": error}


def charge(method, amount, p):
    """Returns dict(ok, status, ref, detail, error). status 400 = bad input, 402 = declined."""
    p = p or {}
    if method == "COD":
        return _result(detail="Pay on delivery")

    if method == "UPI":
        upi = str(p.get("upi_id") or "").strip().lower()
        if not UPI_RE.match(upi):
            return _result(False, 400, error="Enter a valid UPI ID (for example name@okhdfcbank)")
        masked = upi[0] + "***@" + upi.split("@")[1]
        if upi.startswith("fail@"):
            return _result(False, 402, detail=f"UPI {masked}", error="UPI payment failed or was declined. Please try again.")
        return _result(ref=_txn(), detail=f"UPI {masked}")

    if method == "CARD":
        number = re.sub(r"[\s-]", "", str(p.get("card_number") or ""))
        if not number.isdigit() or not 13 <= len(number) <= 19 or not luhn_ok(number):
            return _result(False, 400, error="Enter a valid card number")
        if not str(p.get("card_name") or "").strip():
            return _result(False, 400, error="Enter the name on the card")
        m = re.fullmatch(r"(\d{2})\s*/\s*(\d{2})", str(p.get("expiry") or "").strip())
        if not m or not 1 <= int(m.group(1)) <= 12:
            return _result(False, 400, error="Enter the expiry date as MM/YY")
        now = datetime.now()
        if (2000 + int(m.group(2)), int(m.group(1))) < (now.year, now.month):
            return _result(False, 400, error="This card has expired")
        brand = card_brand(number)
        cvv_len = 4 if brand == "Amex" else 3
        if not re.fullmatch(rf"\d{{{cvv_len}}}", str(p.get("cvv") or "")):
            return _result(False, 400, error=f"Enter the {cvv_len}-digit CVV")
        detail = f"{brand} •••• {number[-4:]}"
        if number in DECLINES:
            return _result(False, 402, detail=detail, error=DECLINES[number])
        return _result(ref=_txn(), detail=detail)

    if method == "NETBANKING":
        bank = p.get("bank")
        if bank not in BANKS:
            return _result(False, 400, error="Please choose your bank")
        if bank == "State Bank of India":
            return _result(False, 402, detail=bank, error="The bank server did not respond. Please try again or use another method.")
        return _result(ref=_txn(), detail=bank)

    return _result(False, 400, error="Please select a payment method")
