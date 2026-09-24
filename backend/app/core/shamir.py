"""
Shamir's Secret Sharing (SSS) — implemented from scratch. Pure math,
no DB or policy dependency.
"""
import secrets
from typing import List, Tuple

_PRIME = (1 << 521) - 1


def _eval_polynomial(coefficients: List[int], x: int, prime: int) -> int:
    result = 0
    for coeff in reversed(coefficients):
        result = (result * x + coeff) % prime
    return result


def split_secret(secret_int: int, n: int, t: int, prime: int = _PRIME) -> List[Tuple[int, int]]:
    if t > n:
        raise ValueError("threshold cannot exceed number of shares")
    if secret_int >= prime:
        raise ValueError("secret too large for field — use a larger prime")

    coefficients = [secret_int] + [secrets.randbelow(prime) for _ in range(t - 1)]
    shares = []
    for x in range(1, n + 1):
        y = _eval_polynomial(coefficients, x, prime)
        shares.append((x, y))
    return shares


def _lagrange_interpolate(x: int, points: List[Tuple[int, int]], prime: int) -> int:
    total = 0
    n = len(points)
    for i in range(n):
        xi, yi = points[i]
        num, den = 1, 1
        for j in range(n):
            if i == j:
                continue
            xj, _ = points[j]
            num = (num * (x - xj)) % prime
            den = (den * (xi - xj)) % prime
        inv_den = pow(den, prime - 2, prime)
        term = (yi * num * inv_den) % prime
        total = (total + term) % prime
    return total


def reconstruct_secret(shares: List[Tuple[int, int]], prime: int = _PRIME) -> int:
    if len(shares) < 2:
        raise ValueError("need at least 2 shares to interpolate")
    return _lagrange_interpolate(0, shares, prime)


def bytes_to_int(b: bytes) -> int:
    return int.from_bytes(b, byteorder="big")


def int_to_bytes(i: int, length: int) -> bytes:
    return i.to_bytes(length, byteorder="big")